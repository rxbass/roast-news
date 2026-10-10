"""Roast orchestration: cache -> TMDB -> daily cap -> safety -> generate -> safety -> persist."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.rate_limit import check_daily_limit
from app.core.security import hash_ip
from app.exceptions import NotFoundError, UnprocessableError, UpstreamError
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import gif_client, llm_client, safety_service, tmdb_client
from app.services.safety_service import RefusalReason
from app.services.tmdb_client import MovieDetails

logger = logging.getLogger(__name__)

THIN_MOVIE_MESSAGE = "Indha padathu pathi info romba kammi machan. Vera padam try pannunga."


@dataclass(frozen=True)
class RoastResult:
    """A roast row plus whether it came from the cache."""

    roast: Roast
    cached: bool


def _find_cached(db: Session, tmdb_id: int, spice: SpiceLevel, user: User | None) -> Roast | None:
    """Newest completed roast for (tmdb_id, spice) within the cache window.

    A signed-in user's own row is preferred so repeat requests don't create duplicate copies.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=settings.ROAST_CACHE_HOURS)
    base = (
        select(Roast)
        .where(
            Roast.tmdb_id == tmdb_id,
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
    tmdb_id: int,
    spice: SpiceLevel,
    user: User | None,
    client_ip: str,
) -> RoastResult:
    """Create (or return a cached) roast for the TMDB movie ``tmdb_id``.

    Raises:
        NotFoundError: unknown or adult title (not persisted).
        UnprocessableError: TMDB has too little about the film to roast (not persisted).
        RateLimitError: global daily cap reached (only when a new generation is needed).
        UpstreamError: TMDB failure (not persisted) or OpenAI failure (a ``failed`` row is
            persisted first).
    """
    ip_hash = hash_ip(client_ip)
    user_id = user.id if user is not None else None

    cached = _find_cached(db, tmdb_id, spice, user)
    if cached is None:
        # End the read transaction so its pooled connection isn't held across the TMDB and
        # OpenAI calls (tens of seconds); the session reconnects for the final INSERT.
        db.rollback()
    if cached is not None:
        logger.info("Cache hit for roast %s (movie %s)", cached.id, tmdb_id)
        if user_id is not None and cached.user_id != user_id:
            copy = Roast(
                user_id=user_id,
                tmdb_id=cached.tmdb_id,
                movie_title=cached.movie_title,
                release_year=cached.release_year,
                original_language=cached.original_language,
                poster_path=cached.poster_path,
                spice_level=spice,
                roast_text=cached.roast_text,
                gif_url=cached.gif_url,
                gif_page_url=cached.gif_page_url,
                status=RoastStatus.completed,
                refusal_reason=None,
                model=cached.model,
                client_ip_hash=ip_hash,
            )
            return RoastResult(roast=_save(db, copy), cached=True)
        return RoastResult(roast=cached, cached=True)

    movie = await tmdb_client.get_movie(tmdb_id)
    if not tmdb_client.has_enough_to_roast(movie):
        raise UnprocessableError(
            detail="Not enough movie details to roast", message=THIN_MOVIE_MESSAGE
        )
    # Counted only once the movie is real and roastable: bogus ids are rejected above without
    # spending the global budget, so they can't be used to exhaust it for everyone.
    check_daily_limit()

    roast_id = uuid.uuid4()

    def build(
        status: RoastStatus,
        *,
        text: str | None = None,
        reason: str | None = None,
        gif: gif_client.Gif | None = None,
    ) -> Roast:
        return Roast(
            id=roast_id,
            user_id=user_id,
            tmdb_id=movie.tmdb_id,
            movie_title=movie.title[:300],
            release_year=movie.year,
            original_language=movie.original_language[:8],
            poster_path=movie.poster_path,
            spice_level=spice,
            roast_text=text,
            gif_url=gif.url if gif else None,
            gif_page_url=gif.page_url if gif else None,
            status=status,
            refusal_reason=reason,
            model=settings.OPENAI_MODEL[:64],
            client_ip_hash=ip_hash,
        )

    try:
        status, generated, reason = await _generate(movie, spice)
    except UpstreamError:
        failed = _save(db, build(RoastStatus.failed))
        logger.warning("Roast %s failed: OpenAI upstream error", failed.id)
        raise

    gif = await gif_client.pick_gif(generated.gif_mood, str(roast_id)) if generated else None
    text = generated.text if generated else None
    roast = _save(db, build(status, text=text, reason=reason, gif=gif))
    logger.info("Roast %s %s (movie %s, %s)", roast.id, roast.status.value, tmdb_id, spice.value)
    return RoastResult(roast=roast, cached=False)


async def _generate(
    movie: MovieDetails, spice: SpiceLevel
) -> tuple[RoastStatus, llm_client.GeneratedRoast | None, str | None]:
    """Run the safety checks and the generation; return (status, roast, refusal_reason)."""
    verdict = await safety_service.check_movie(movie)
    if not verdict.allowed:
        reason = verdict.reason or RefusalReason.sensitive_topic
        return RoastStatus.refused, None, reason.value

    generated = await llm_client.generate_roast(
        movie.title, tmdb_client.movie_context(movie), spice
    )
    if safety_service.is_model_refusal(generated.text):
        return RoastStatus.refused, None, RefusalReason.sensitive_topic.value
    if await safety_service.check_output(generated.text):
        return RoastStatus.refused, None, RefusalReason.output_flagged.value
    return RoastStatus.completed, generated, None


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
