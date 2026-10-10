"""Content safety: sensitive-film check, output moderation, and playful Tanglish refusal lines."""

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum

from app.services import llm_client
from app.services.tmdb_client import MovieDetails, movie_context

logger = logging.getLogger(__name__)


class RefusalReason(StrEnum):
    """Values stored in ``Roast.refusal_reason``."""

    sensitive_topic = "sensitive_topic"
    moderation_flagged = "moderation_flagged"
    output_flagged = "output_flagged"


REFUSAL_LINES: tuple[str, ...] = (
    "Idhu roast panna vendiya padam illa machan 🙏",
    "Ayyo, indha padathukku kalaai panna manasu varala machan. Vera padam sollu 🙏",
    "Sila padathukku roast illa, respect dhaan. Next movie try pannunga 🙏",
    "Machan, idhu real-life pain pathi padam. Back-row comedy-ku set aagadhu 🙏",
    "Indha kadhai-la joke adikka koodadhu machan. Vera edhavadhu kudu 🙏",
    "Paavam da, idhula comedy illa. Oru mass masala padam paathu varalaam 🙏",
)

FAILURE_LINE = "Server konjam tired, try again machan."


@dataclass(frozen=True)
class SafetyVerdict:
    """Outcome of the pre-generation movie check."""

    allowed: bool
    reason: RefusalReason | None = None
    category: str | None = None


async def check_movie(movie: MovieDetails) -> SafetyVerdict:
    """Ask the classifier whether this film is off-limits for jokes.

    The movie facts come from TMDB, not from the user, so there is no input moderation pass;
    the generated roast is still moderated by ``check_output``. Raises ``UpstreamError`` if
    OpenAI fails.
    """
    result = await llm_client.classify_sensitive(movie.title, movie_context(movie))
    if result.sensitive:
        logger.info("Movie %s refused: sensitive (%s)", movie.tmdb_id, result.category)
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
    # Also catch our own Tanglish refusal line, in case the model paraphrases the rule.
    return llm_client.REFUSAL_SENTINEL in text or "roast panna vendiya padam illa" in text.lower()


def refusal_message(reason: str | None, seed: str) -> str:
    """Pick a refusal line deterministically from ``(reason, seed)`` (e.g. the roast id)."""
    digest = hashlib.sha256(f"{reason or ''}:{seed}".encode()).digest()
    return REFUSAL_LINES[int.from_bytes(digest[:4], "big") % len(REFUSAL_LINES)]
