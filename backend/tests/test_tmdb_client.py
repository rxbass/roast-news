"""``tmdb_client`` against a mocked TMDB (respx): parsing, ranking, auth, caching, errors."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from app.config import settings
from app.exceptions import NotFoundError, UpstreamError
from app.services import tmdb_client
from tests.conftest import MOVIE

pytestmark = pytest.mark.real_tmdb

SEARCH = f"{tmdb_client.TMDB_API_BASE}/search/movie"
DETAILS = f"{tmdb_client.TMDB_API_BASE}/movie/4242"


@pytest.fixture
def tmdb() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def result(tmdb_id: int, title: str, lang: str = "en", **extra: Any) -> dict[str, Any]:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "original_language": lang,
        "release_date": "2023-10-19",
        "poster_path": f"/p{tmdb_id}.jpg",
        "overview": f"About {title}",
        "adult": False,
        **extra,
    }


def details(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": 4242,
        "title": "Thunder Raja",
        "original_title": "இடி ராஜா",
        "original_language": "ta",
        "release_date": "2019-01-14",
        "poster_path": "/thunder.jpg",
        "overview": "A village man takes on a mining baron.",
        "tagline": "One man. One village.",
        "genres": [{"id": 1, "name": "Action"}, {"id": 2, "name": "Drama"}, "junk"],
        "runtime": 172,
        "vote_average": 6.4,
        "vote_count": 120,
        "adult": False,
        "credits": {
            "cast": [{"name": f"Actor {i}"} for i in range(10)],
            "crew": [
                {"name": "K. Director", "job": "Director"},
                {"name": "Someone", "job": "Editor"},
            ],
        },
    }
    body.update(overrides)
    return body


# --- search ------------------------------------------------------------------------------------
async def test_search_ranks_exact_title_then_tamil(tmdb: respx.MockRouter) -> None:
    route = tmdb.get(SEARCH).respond(
        json={
            "results": [
                result(1, "Leo", "en"),
                result(2, "Leo and the Lions", "ta"),
                result(3, "Leo", "ta"),
                result(4, "The Leo Story", "hi"),
                result(5, "Leo", "te"),
            ]
        }
    )
    movies = await tmdb_client.search_movies("  leo ")
    assert [m.tmdb_id for m in movies] == [3, 5, 1, 2, 4]
    params = route.calls.last.request.url.params
    assert params["query"] == "leo"
    assert params["include_adult"] == "false"
    assert params["api_key"] == "test-tmdb-key"


async def test_search_loose_match_never_beats_exact_title(tmdb: respx.MockRouter) -> None:
    tmdb.get(SEARCH).respond(
        json={"results": [result(9, "Insha Allah", "ta"), result(7, "Inception", "en")]}
    )
    movies = await tmdb_client.search_movies("Inception")
    assert [m.tmdb_id for m in movies] == [7, 9]


async def test_search_drops_adult_and_malformed_rows_and_caps(tmdb: respx.MockRouter) -> None:
    rows: list[Any] = [result(i, f"Film {i}") for i in range(1, 12)]
    rows += [
        result(50, "Adult", adult=True),
        {"id": "x", "title": "Bad id"},
        {"id": 60},
        "junk",
        result(70, "Bad poster", poster_path="javascript:alert(1)", release_date="soon"),
    ]
    tmdb.get(SEARCH).respond(json={"results": rows})
    movies = await tmdb_client.search_movies("film")
    assert len(movies) == tmdb_client.SEARCH_LIMIT
    assert all(m.tmdb_id < 50 for m in movies)


async def test_search_parses_fields(tmdb: respx.MockRouter) -> None:
    tmdb.get(SEARCH).respond(
        json={"results": [result(70, "Odd", poster_path="javascript:alert(1)", release_date="")]}
    )
    [movie] = await tmdb_client.search_movies("odd")
    assert movie.poster_path is None
    assert movie.year is None
    assert tmdb_client.poster_url(movie.poster_path) is None
    assert tmdb_client.poster_url("/a.jpg") == "https://image.tmdb.org/t/p/w342/a.jpg"


async def test_search_is_cached(tmdb: respx.MockRouter) -> None:
    route = tmdb.get(SEARCH).respond(json={"results": [result(1, "Leo")]})
    first = await tmdb_client.search_movies("Leo")
    second = await tmdb_client.search_movies("LEO")
    assert first == second
    assert route.call_count == 1


async def test_blank_search_makes_no_call(tmdb: respx.MockRouter) -> None:
    route = tmdb.get(SEARCH)
    assert await tmdb_client.search_movies("   ") == []
    assert route.call_count == 0


async def test_search_with_no_results_list(tmdb: respx.MockRouter) -> None:
    tmdb.get(SEARCH).respond(json={"page": 1})
    assert await tmdb_client.search_movies("nothing") == []


# --- details -----------------------------------------------------------------------------------
async def test_get_movie_parses_details(tmdb: respx.MockRouter) -> None:
    route = tmdb.get(DETAILS).respond(json=details())
    movie = await tmdb_client.get_movie(4242)
    assert movie.title == "Thunder Raja"
    assert movie.original_title == "இடி ராஜா"
    assert movie.year == 2019
    assert movie.genres == ("Action", "Drama")
    assert movie.runtime_minutes == 172
    assert movie.rating == 6.4
    assert movie.directors == ("K. Director",)
    assert movie.cast == tuple(f"Actor {i}" for i in range(tmdb_client.CAST_LIMIT))
    assert route.calls.last.request.url.params["append_to_response"] == "credits"


async def test_get_movie_tolerates_missing_fields(tmdb: respx.MockRouter) -> None:
    tmdb.get(DETAILS).respond(
        json=details(
            runtime=0, vote_average=0, vote_count=None, credits="nope", genres=None, tagline=None
        )
    )
    movie = await tmdb_client.get_movie(4242)
    assert movie.runtime_minutes is None
    assert movie.rating is None
    assert movie.vote_count == 0
    assert movie.cast == ()
    assert movie.directors == ()
    assert movie.genres == ()
    assert movie.tagline == ""


async def test_get_movie_is_cached(tmdb: respx.MockRouter) -> None:
    route = tmdb.get(DETAILS).respond(json=details())
    await tmdb_client.get_movie(4242)
    await tmdb_client.get_movie(4242)
    assert route.call_count == 1


@pytest.mark.parametrize(
    "body", [details(adult=True), details(id=1), details(title=""), details(title=None)]
)
async def test_get_movie_rejects_adult_or_mismatched(
    tmdb: respx.MockRouter, body: dict[str, Any]
) -> None:
    tmdb.get(DETAILS).respond(json=body)
    with pytest.raises(NotFoundError):
        await tmdb_client.get_movie(4242)


async def test_get_movie_404(tmdb: respx.MockRouter) -> None:
    tmdb.get(DETAILS).respond(status_code=404, json={"status_message": "not found"})
    with pytest.raises(NotFoundError) as exc_info:
        await tmdb_client.get_movie(4242)
    assert exc_info.value.message == tmdb_client.NOT_FOUND_MESSAGE


# --- auth + errors -----------------------------------------------------------------------------
async def test_v4_read_token_goes_in_header(
    tmdb: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TMDB_API_KEY", "eyJhbGciOiJIUzI1NiJ9.token")
    route = tmdb.get(SEARCH).respond(json={"results": []})
    await tmdb_client.search_movies("x")
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.token"
    assert "api_key" not in request.url.params


async def test_missing_key_is_upstream_error(
    tmdb: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TMDB_API_KEY", " ")
    with pytest.raises(UpstreamError, match="not configured"):
        await tmdb_client.search_movies("x")


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (httpx.Response(500, json={}), "HTTP 500"),
        (httpx.Response(401, json={}), "HTTP 401"),
        (httpx.Response(200, text="<html>"), "invalid JSON"),
        (httpx.Response(200, json=[1, 2]), "unexpected response"),
    ],
)
async def test_bad_responses_are_upstream_errors(
    tmdb: respx.MockRouter, response: httpx.Response, match: str
) -> None:
    tmdb.get(SEARCH).mock(return_value=response)
    with pytest.raises(UpstreamError, match=match):
        await tmdb_client.search_movies("x")


async def test_network_error_is_upstream_error(tmdb: respx.MockRouter) -> None:
    tmdb.get(SEARCH).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(UpstreamError, match="unreachable"):
        await tmdb_client.search_movies("x")


# --- helpers -----------------------------------------------------------------------------------
def test_movie_context_lists_known_facts() -> None:
    context = tmdb_client.movie_context(MOVIE)
    assert "Year: 2019" in context
    assert "Runtime: 172 minutes" in context
    assert "Director: K. Director" in context
    assert "Starring: Hero Actor, Heroine Actor" in context
    assert "TMDB rating: 6.4/10 from 120 votes" in context
    assert context.endswith(f"Plot: {MOVIE.overview}")
    assert "Original title" not in context  # same as the title


def test_movie_context_skips_unknowns() -> None:
    import dataclasses

    sparse = dataclasses.replace(
        MOVIE, year=None, genres=(), runtime_minutes=None, rating=None, cast=(), tagline=""
    )
    context = tmdb_client.movie_context(sparse)
    assert "Year" not in context
    assert "rating" not in context


def test_has_enough_to_roast() -> None:
    import dataclasses

    assert tmdb_client.has_enough_to_roast(MOVIE)
    assert tmdb_client.has_enough_to_roast(dataclasses.replace(MOVIE, overview=""))
    assert not tmdb_client.has_enough_to_roast(dataclasses.replace(MOVIE, overview="", cast=()))


def test_cache_evicts_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tmdb_client, "CACHE_MAX_ENTRIES", 2)
    tmdb_client._cache_put("a", 1, 10)
    tmdb_client._cache_put("b", 2, 20)
    tmdb_client._cache_put("c", 3, 30)
    assert tmdb_client._cache_get("a") is None
    assert tmdb_client._cache_get("c") == 3


def test_cache_expiry() -> None:
    tmdb_client._cache_put("old", 1, -1)
    assert tmdb_client._cache_get("old") is None
