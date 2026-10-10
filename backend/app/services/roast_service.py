"""Roast orchestration: cache -> daily cap -> scrape -> safety -> generate -> safety -> persist."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.rate_limit import check_daily_limit
from app.core.security import hash_ip
from app.exceptions import NotFoundError, UpstreamError
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import llm_client, safety_service
from app.services.safety_service import RefusalReason
from app.services.scraper_service import Article, fetch_article
from app.services.url_utils import normalize_url, url_hash

logger = logging.getLogger(__name__)

EXCERPT_CHARS = 300


@dataclass(frozen=True)
class RoastResult:
    """A roast row plus whether it came from the cache."""

    roast: Roast
    cached: bool


def _find_cached(db: Session, hashed: str, spice: SpiceLevel, user: User | None) -> Roast | None:
    """Newest completed roast for (url_hash, spice) within the cache window.

    A signed-in user's own row is preferred so repeat requests don't create duplicate copies.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=settings.ROAST_CACHE_HOURS)
    base = (
        select(Roast)
        .where(
            Roast.url_hash == hashed,
            Roast.spice_level == spice,
            Roast.status == RoastStatus.completed,
            Roast.created_at >= cutoff,
        )
        .order_by(Roast.created_at.desc())
        .limit(1)
    )
    if user is not None:
        own = db.scalars(base.where(Roast.user_id == user.id)).first()
        if own is not None:
            return own
    return db.scalars(base).first()


def _save(db: Session, roast: Roast) -> Roast:
    db.add(roast)
    db.commit()
    db.refresh(roast)
    return roast


async def create_roast(
    db: Session,
    *,
    url: str,
    spice: SpiceLevel,
    user: User | None,
    client_ip: str,
) -> RoastResult:
    """Create (or return a cached) roast for ``url``.

    Raises:
        RateLimitError: global daily cap reached (only when a new generation is needed).
        BadRequestError / UnprocessableError / UpstreamError: from the scraper (not persisted).
        UpstreamError: OpenAI failure after scraping (a ``failed`` row is persisted first).
    """
    hashed = url_hash(normalize_url(url))
    ip_hash = hash_ip(client_ip)
    user_id = user.id if user is not None else None

    cached = _find_cached(db, hashed, spice, user)
    if cached is None:
        # End the read transaction so its pooled connection isn't held across the scrape and
        # the OpenAI calls (tens of seconds); the session reconnects for the final INSERT.
        db.rollback()
    if cached is not None:
        logger.info("Cache hit for roast %s (%s)", cached.id, cached.source_domain)
        if user_id is not None and cached.user_id != user_id:
            copy = Roast(
                user_id=user_id,
                source_url=url,
                url_hash=hashed,
                source_domain=cached.source_domain,
                article_title=cached.article_title,
                article_excerpt=cached.article_excerpt,
                spice_level=spice,
                roast_text=cached.roast_text,
                status=RoastStatus.completed,
                refusal_reason=None,
                model=cached.model,
                client_ip_hash=ip_hash,
            )
            return RoastResult(roast=_save(db, copy), cached=True)
        return RoastResult(roast=cached, cached=True)

    article = await fetch_article(url)
    # Counted only once the URL is real and fetchable: junk/blocked URLs are rejected above
    # without spending the global budget, so they can't be used to exhaust it for everyone.
    check_daily_limit()

    def build(status: RoastStatus, *, text: str | None = None, reason: str | None = None) -> Roast:
        return Roast(
            id=uuid.uuid4(),
            user_id=user_id,
            source_url=url,
            url_hash=hashed,
            source_domain=article.domain[:255],
            article_title=article.title[:500],
            article_excerpt=article.text[:EXCERPT_CHARS],
            spice_level=spice,
            roast_text=text,
            status=status,
            refusal_reason=reason,
            model=settings.OPENAI_MODEL[:64],
            client_ip_hash=ip_hash,
        )

    try:
        status, roast_text, reason = await _generate(article, spice)
    except UpstreamError:
        failed = _save(db, build(RoastStatus.failed))
        logger.warning("Roast %s failed: OpenAI upstream error", failed.id)
        raise

    roast = _save(db, build(status, text=roast_text, reason=reason))
    logger.info(
        "Roast %s %s (%s, %s)", roast.id, roast.status.value, roast.source_domain, spice.value
    )
    return RoastResult(roast=roast, cached=False)


async def _generate(
    article: Article, spice: SpiceLevel
) -> tuple[RoastStatus, str | None, str | None]:
    """Run the safety checks and the generation; return (status, roast_text, refusal_reason)."""
    verdict = await safety_service.check_article(article)
    if not verdict.allowed:
        reason = verdict.reason or RefusalReason.sensitive_topic
        return RoastStatus.refused, None, reason.value

    roast_text = await llm_client.generate_roast(article.title, article.text, spice)
    if safety_service.is_model_refusal(roast_text):
        return RoastStatus.refused, None, RefusalReason.sensitive_topic.value
    if await safety_service.check_output(roast_text):
        return RoastStatus.refused, None, RefusalReason.output_flagged.value
    return RoastStatus.completed, roast_text, None


def parse_roast_id(raw: str) -> uuid.UUID:
    """Parse a permalink id; invalid UUIDs are reported as 404 (not 422)."""
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise NotFoundError(detail="Roast not found") from exc


def get_roast(db: Session, roast_id: str) -> Roast:
    """Return a roast by id (any status) or raise ``NotFoundError``."""
    roast = db.get(Roast, parse_roast_id(roast_id))
    if roast is None:
        raise NotFoundError(detail="Roast not found")
    return roast


def list_user_roasts(db: Session, user: User, *, page: int, size: int) -> tuple[list[Roast], int]:
    """Return one page of the user's roasts (newest first) and the total count."""
    total = db.scalar(select(func.count(Roast.id)).where(Roast.user_id == user.id)) or 0
    rows = db.scalars(
        select(Roast)
        .where(Roast.user_id == user.id)
        .order_by(Roast.created_at.desc(), Roast.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(rows), int(total)


def delete_user_roast(db: Session, user: User, roast_id: str) -> None:
    """Delete a roast owned by ``user``; missing or not-owned both raise ``NotFoundError``."""
    roast = db.get(Roast, parse_roast_id(roast_id))
    if roast is None or roast.user_id is None or roast.user_id != user.id:
        raise NotFoundError(detail="Roast not found")
    db.delete(roast)
    db.commit()
    logger.info("Roast %s deleted by user %s", roast.id, user.id)
