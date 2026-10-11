"""The ONLY module that talks to TMDB (The Movie Database).

``search_movies`` powers the search box; ``get_movie`` loads the facts a roast is built from.
Both keep a small in-process TTL cache so popular titles cost no extra TMDB calls. Any TMDB
failure (network, timeout, 5xx, bad JSON, missing key) is raised as ``UpstreamError`` (502); an
unknown or adult title is ``NotFoundError`` (404).
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.exceptions import NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

# TMDB's alternate API host: some Indian ISPs reset connections to api.themoviedb.org.
TMDB_API_BASE = "https://api.tmdb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w342"
SEARCH_LIMIT = 8
CAST_LIMIT = 6
SEARCH_CACHE_SECONDS = 10 * 60
MOVIE_CACHE_SECONDS = 6 * 60 * 60
CACHE_MAX_ENTRIES = 512

# Ranking: how well the title matches the query first, then Tamil, then other Indian
# languages, then TMDB's own relevance order. So "Leo" puts the Tamil Leo first, while
# "Inception" never lets a loosely matching Indian film jump ahead of Inception itself.
LANGUAGE_RANK: dict[str, int] = {"ta": 0, "te": 1, "ml": 1, "kn": 1, "hi": 1}
OTHER_LANGUAGE_RANK = 2

_POSTER_PATH_RE = re.compile(r"^/[A-Za-z0-9_.-]{1,200}$")

NOT_FOUND_MESSAGE = "Indha padam engalukku theriyala machan. Vera padam try pannunga."


@dataclass(frozen=True)
class MovieSummary:
    """One search result."""

    tmdb_id: int
    title: str
    year: int | None
    original_language: str
    poster_path: str | None
    overview: str


@dataclass(frozen=True)
class MovieDetails:
    """The facts a roast is built from."""

    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    original_language: str
    poster_path: str | None
    overview: str
    tagline: str
    genres: tuple[str, ...]
    runtime_minutes: int | None
    rating: float | None
    vote_count: int
    directors: tuple[str, ...]
    cast: tuple[str, ...]


def poster_url(poster_path: str | None) -> str | None:
    """Absolute poster URL for a stored ``poster_path`` (None when there is no poster)."""
    return f"{POSTER_BASE_URL}{poster_path}" if poster_path else None


# --------------------------------------------------------------------------------------------
# Tiny TTL cache (per process)
# --------------------------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    hit = _cache.get(key)
    if hit is None:
        return None
    expires_at, value = hit
    if expires_at < time.monotonic():
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: Any, ttl: float) -> None:
    if len(_cache) >= CACHE_MAX_ENTRIES:
        # Drop the entry closest to expiry; good enough for a few hundred keys.
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    _cache[key] = (time.monotonic() + ttl, value)


def clear_cache() -> None:
    """Empty the TTL cache (used by tests)."""
    _cache.clear()


# --------------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------------
def _auth() -> tuple[dict[str, str], dict[str, str]]:
    """(headers, params) for TMDB: v4 read tokens go in a header, v3 keys in the query."""
    key = settings.TMDB_API_KEY.strip()
    if not key:
        logger.error("TMDB_API_KEY is not configured; cannot call TMDB")
        raise UpstreamError(detail="TMDB API key is not configured")
    if key.startswith("eyJ"):
        return {"Authorization": f"Bearer {key}"}, {}
    return {}, {"api_key": key}


async def _get(path: str, params: dict[str, str]) -> dict[str, Any]:
    headers, auth_params = _auth()
    try:
        async with httpx.AsyncClient(
            base_url=TMDB_API_BASE,
            timeout=float(settings.TMDB_TIMEOUT_SECONDS),
            headers={"Accept": "application/json", **headers},
        ) as client:
            response = await client.get(path, params={**params, **auth_params})
    except httpx.HTTPError as exc:
        logger.warning("TMDB request failed: %s", type(exc).__name__)
        raise UpstreamError(detail="Movie database is unreachable") from exc

    if response.status_code == 404:
        raise NotFoundError(detail="Movie not found", message=NOT_FOUND_MESSAGE)
    if response.status_code != 200:
        logger.warning("TMDB %s returned HTTP %s", path, response.status_code)
        raise UpstreamError(detail=f"Movie database returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError(detail="Movie database returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise UpstreamError(detail="Movie database returned an unexpected response")
    return data


# --------------------------------------------------------------------------------------------
# Parsing helpers (TMDB data is crowd-edited: treat every field as optional and untrusted)
# --------------------------------------------------------------------------------------------
def _str(value: object, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _year(release_date: object) -> int | None:
    text = _str(release_date, 10)
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def _poster(value: object) -> str | None:
    text = _str(value, 201)
    return text if _POSTER_PATH_RE.match(text) else None


def _names(items: object, limit: int) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    names = [_str(item.get("name"), 100) for item in items if isinstance(item, dict)]
    return tuple(n for n in names if n)[:limit]


def _summary(raw: dict[str, Any]) -> MovieSummary | None:
    tmdb_id = raw.get("id")
    title = _str(raw.get("title"), 300)
    if not isinstance(tmdb_id, int) or not title or raw.get("adult") is True:
        return None
    return MovieSummary(
        tmdb_id=tmdb_id,
        title=title,
        year=_year(raw.get("release_date")),
        original_language=_str(raw.get("original_language"), 8),
        poster_path=_poster(raw.get("poster_path")),
        overview=_str(raw.get("overview"), 300),
    )


def _normalise(text: str) -> str:
    return " ".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def _match_tier(query: str, raw: dict[str, Any]) -> int:
    """0 = exact title, 1 = title starts with the query, 2 = anything else TMDB matched."""
    titles = {_normalise(_str(raw.get(k), 300)) for k in ("title", "original_title")}
    if query in titles:
        return 0
    if any(t.startswith(query) for t in titles):
        return 1
    return 2


def _rank(query: str, raw: dict[str, Any]) -> tuple[int, int]:
    language = LANGUAGE_RANK.get(_str(raw.get("original_language"), 8), OTHER_LANGUAGE_RANK)
    return _match_tier(query, raw), language


# --------------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------------
async def search_movies(query: str) -> list[MovieSummary]:
    """Search TMDB by title; Tamil (then Indian) films first, adult titles excluded."""
    query = " ".join(query.split())[:100]
    if not query:
        return []
    key = f"search:{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return list(cached)

    data = await _get(
        "/search/movie",
        {"query": query, "include_adult": "false", "language": "en-US", "page": "1"},
    )
    raw_results = data.get("results")
    rows = [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []
    normalised = _normalise(query)
    rows.sort(key=lambda r: _rank(normalised, r))  # stable: TMDB order breaks ties
    results = [s for s in (_summary(r) for r in rows) if s is not None][:SEARCH_LIMIT]
    _cache_put(key, tuple(results), SEARCH_CACHE_SECONDS)
    return results


async def get_movie(tmdb_id: int) -> MovieDetails:
    """Load one movie with credits. Unknown or adult titles raise ``NotFoundError``."""
    key = f"movie:{tmdb_id}"
    cached = _cache_get(key)
    if isinstance(cached, MovieDetails):
        return cached

    raw = await _get(f"/movie/{tmdb_id}", {"append_to_response": "credits", "language": "en-US"})
    title = _str(raw.get("title"), 300)
    if raw.get("id") != tmdb_id or not title or raw.get("adult") is True:
        raise NotFoundError(detail="Movie not found", message=NOT_FOUND_MESSAGE)

    credits = raw.get("credits") if isinstance(raw.get("credits"), dict) else {}
    crew = credits.get("crew") if isinstance(credits, dict) else None
    directors = _names(
        [c for c in crew if isinstance(c, dict) and c.get("job") == "Director"]
        if isinstance(crew, list)
        else [],
        3,
    )
    runtime = raw.get("runtime")
    rating = raw.get("vote_average")
    vote_count = raw.get("vote_count")
    movie = MovieDetails(
        tmdb_id=tmdb_id,
        title=title,
        original_title=_str(raw.get("original_title"), 300),
        year=_year(raw.get("release_date")),
        original_language=_str(raw.get("original_language"), 8),
        poster_path=_poster(raw.get("poster_path")),
        overview=_str(raw.get("overview"), 2000),
        tagline=_str(raw.get("tagline"), 300),
        genres=_names(raw.get("genres"), 5),
        runtime_minutes=runtime if isinstance(runtime, int) and runtime > 0 else None,
        rating=float(rating) if isinstance(rating, int | float) and rating > 0 else None,
        vote_count=vote_count if isinstance(vote_count, int) else 0,
        directors=directors,
        cast=_names(credits.get("cast") if isinstance(credits, dict) else None, CAST_LIMIT),
    )
    _cache_put(key, movie, MOVIE_CACHE_SECONDS)
    return movie


def movie_context(movie: MovieDetails) -> str:
    """Plain-text fact sheet sent to the model (inside <movie> delimiters by ``llm_client``)."""
    lines = [
        f"Year: {movie.year}" if movie.year else "",
        f"Original title: {movie.original_title}" if movie.original_title != movie.title else "",
        f"Language: {movie.original_language}" if movie.original_language else "",
        f"Genres: {', '.join(movie.genres)}" if movie.genres else "",
        f"Runtime: {movie.runtime_minutes} minutes" if movie.runtime_minutes else "",
        f"Director: {', '.join(movie.directors)}" if movie.directors else "",
        f"Starring: {', '.join(movie.cast)}" if movie.cast else "",
        f"Tagline: {movie.tagline}" if movie.tagline else "",
        (
            f"TMDB rating: {movie.rating:.1f}/10 from {movie.vote_count} votes"
            if movie.rating is not None and movie.vote_count >= 10
            else ""
        ),
        f"Plot: {movie.overview}" if movie.overview else "",
    ]
    return "\n".join(line for line in lines if line)


def has_enough_to_roast(movie: MovieDetails) -> bool:
    """A roast needs at least a plot summary, or genres plus cast to riff on."""
    return bool(movie.overview) or bool(movie.genres and movie.cast)
