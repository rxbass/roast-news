"""``GET /api/v1/movies/search`` (TMDB replaced by ``FakeTMDB``)."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.exceptions import UpstreamError
from tests.conftest import MOVIE, MOVIE_ID, FakeTMDB

SEARCH = "/api/v1/movies/search"


def test_search_returns_results(client: TestClient, fake_tmdb: FakeTMDB) -> None:
    response = client.get(SEARCH, params={"q": "thunder"})
    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "tmdb_id": MOVIE_ID,
                "title": MOVIE.title,
                "year": MOVIE.year,
                "original_language": "ta",
                "poster_url": "https://image.tmdb.org/t/p/w342/thunder.jpg",
                "overview": MOVIE.overview,
            }
        ]
    }
    assert fake_tmdb.search_calls == ["thunder"]


def test_search_with_no_matches(client: TestClient) -> None:
    assert client.get(SEARCH, params={"q": "zzz"}).json() == {"results": []}


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "x" * 101}])
def test_search_validation(client: TestClient, fake_tmdb: FakeTMDB, params: dict[str, str]) -> None:
    assert client.get(SEARCH, params=params).status_code == 422
    assert fake_tmdb.search_calls == []


def test_search_upstream_error_is_502(client: TestClient, fake_tmdb: FakeTMDB) -> None:
    fake_tmdb.error = UpstreamError("Movie database is unreachable")
    response = client.get(SEARCH, params={"q": "leo"})
    assert response.status_code == 502
    assert response.json()["message"]


def test_search_is_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_SEARCH", "2/minute")
    assert client.get(SEARCH, params={"q": "a"}).status_code == 200
    assert client.get(SEARCH, params={"q": "b"}).status_code == 200
    response = client.get(SEARCH, params={"q": "c"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
