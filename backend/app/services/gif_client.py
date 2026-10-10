"""Reaction GIFs from GIPHY for a roast's mood (the ONLY module that talks to GIPHY).

GIFs are decoration: ``pick_gif`` never raises. With no ``GIPHY_API_KEY``, or when GIPHY is
down or returns nothing, the roast simply has no GIF. Searches use GIPHY's ``g`` rating and a
small per-process cache, so each mood costs about one GIPHY call per cache window.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
GIPHY_RATING = "g"
SEARCH_LIMIT = 25
CACHE_SECONDS = 12 * 60 * 60

# Mood (from llm_client.GIF_MOODS) -> GIPHY queries, tried in order until one has results.
# Tamil-cinema reactions first; generic reactions as the fallback.
MOOD_QUERIES: dict[str, tuple[str, ...]] = {
    "facepalm": ("vadivelu facepalm", "facepalm"),
    "slow_clap": ("tamil clapping", "slow clap"),
    "mind_blown": ("tamil shocked", "mind blown"),
    "bored": ("vadivelu bored", "bored sleeping"),
    "laughing": ("vadivelu laughing", "laughing hard"),
    "eye_roll": ("eye roll",),
    "popcorn": ("eating popcorn", "popcorn"),
    "cringe": ("cringe",),
    "mass_swag": ("rajinikanth style", "swag"),
    "shocked": ("vadivelu shocked", "shocked"),
    "crying": ("vadivelu crying", "crying"),
}


@dataclass(frozen=True)
class Gif:
    """A GIF to show next to a roast, plus the GIPHY page for attribution."""

    url: str
    page_url: str


_cache: dict[str, tuple[float, tuple[Gif, ...]]] = {}


def clear_cache() -> None:
    """Empty the search cache (used by tests)."""
    _cache.clear()


def _is_giphy_https(url: object) -> bool:
    if not isinstance(url, str) or len(url) > 500:
        return False
    parts = urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and (host == "giphy.com" or host.endswith(".giphy.com"))


def _parse(item: object) -> Gif | None:
    if not isinstance(item, dict):
        return None
    images = item.get("images")
    image = images.get("fixed_height") if isinstance(images, dict) else None
    url = image.get("url") if isinstance(image, dict) else None
    page_url = item.get("url")
    if not (_is_giphy_https(url) and _is_giphy_https(page_url)):
        return None
    return Gif(url=str(url), page_url=str(page_url))


async def _search(query: str) -> tuple[Gif, ...]:
    cached = _cache.get(query)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]
    params = {
        "api_key": settings.GIPHY_API_KEY,
        "q": query,
        "limit": str(SEARCH_LIMIT),
        "rating": GIPHY_RATING,
        "lang": "en",
    }
    async with httpx.AsyncClient(timeout=float(settings.GIPHY_TIMEOUT_SECONDS)) as client:
        response = await client.get(GIPHY_SEARCH_URL, params=params)
    response.raise_for_status()
    data = response.json().get("data")
    gifs = tuple(g for g in (_parse(i) for i in data) if g) if isinstance(data, list) else ()
    _cache[query] = (time.monotonic() + CACHE_SECONDS, gifs)
    return gifs


async def pick_gif(mood: str | None, seed: str) -> Gif | None:
    """A GIF for ``mood``, chosen deterministically from ``seed`` (e.g. the roast id)."""
    if not mood or mood not in MOOD_QUERIES or not settings.GIPHY_API_KEY:
        return None
    for query in MOOD_QUERIES[mood]:
        try:
            gifs = await _search(query)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("GIPHY search failed: %s", type(exc).__name__)
            return None
        if gifs:
            index = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "big")
            return gifs[index % len(gifs)]
    return None
