"""Content safety: moderation + sensitive-topic checks, and playful Tanglish refusal lines."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum

from app.services import llm_client
from app.services.scraper_service import Article

logger = logging.getLogger(__name__)

CHECK_CHAR_LIMIT = 4000


class RefusalReason(StrEnum):
    """Values stored in ``Roast.refusal_reason``."""

    sensitive_topic = "sensitive_topic"
    moderation_flagged = "moderation_flagged"
    output_flagged = "output_flagged"


REFUSAL_LINES: tuple[str, ...] = (
    "Idhu roast panna vendiya news illa machan 🙏",
    "Ayyo, indha news-ku kalaai panna manasu varala machan. Vera link kudu 🙏",
    "Sila news-ku roast illa, respect dhaan. Next article try pannunga 🙏",
    "Machan, idhu serious matter. Tea-shop comedy-ku idhu set aagadhu 🙏",
    "Indha scene-u la joke adikka koodadhu machan. Vera edhavadhu kudu 🙏",
    "Paavam da, idhula comedy illa. Oru jolly news paathu varalaam 🙏",
)

FAILURE_LINE = "Server konjam tired, try again machan."


@dataclass(frozen=True)
class SafetyVerdict:
    """Outcome of the pre-generation article check."""

    allowed: bool
    reason: RefusalReason | None = None
    category: str | None = None


async def check_article(article: Article) -> SafetyVerdict:
    """Moderate the article, then run the sensitive-topic classifier.

    Raises ``UpstreamError`` if OpenAI fails.
    """
    sample = f"{article.title}\n\n{article.text}"[:CHECK_CHAR_LIMIT]
    # Independent checks: run them concurrently to save a round trip.
    flagged, result = await asyncio.gather(
        llm_client.moderate(sample),
        llm_client.classify_sensitive(article.title, article.text[:CHECK_CHAR_LIMIT]),
    )
    if flagged:
        logger.info("Article from %s refused: moderation flagged", article.domain)
        return SafetyVerdict(allowed=False, reason=RefusalReason.moderation_flagged)

    if result.sensitive:
        logger.info(
            "Article from %s refused: sensitive topic (%s)", article.domain, result.category
        )
        return SafetyVerdict(
            allowed=False, reason=RefusalReason.sensitive_topic, category=result.category
        )
    return SafetyVerdict(allowed=True)


async def check_output(roast_text: str) -> bool:
    """Moderate the generated roast; return True when it is flagged (must not be shown)."""
    flagged = await llm_client.moderate(roast_text)
    if flagged:
        logger.info("Generated roast flagged by output moderation")
    return flagged


def is_model_refusal(roast_text: str) -> bool:
    """True when the model itself declined (the prompt tells it to emit ``[[REFUSE]]``)."""
    text = roast_text.strip()
    # Also catch the older Tanglish refusal line, in case the model paraphrases the rule.
    return llm_client.REFUSAL_SENTINEL in text or "roast panna vendiya news illa" in text.lower()


def refusal_message(reason: str | None, seed: str) -> str:
    """Pick a refusal line deterministically from ``(reason, seed)`` (e.g. the roast id)."""
    digest = hashlib.sha256(f"{reason or ''}:{seed}".encode()).digest()
    return REFUSAL_LINES[int.from_bytes(digest[:4], "big") % len(REFUSAL_LINES)]
