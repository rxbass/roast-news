"""Roast API: create / cache / safety / failures / ownership / rate limits."""

import dataclasses
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_ip
from app.exceptions import NotFoundError, UpstreamError
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import llm_client
from app.services.safety_service import FAILURE_LINE, REFUSAL_LINES
from tests.conftest import (
    FAKE_GIF,
    FAKE_ROAST_TEXT,
    MOVIE,
    MOVIE_ID,
    FakeGifs,
    FakeLLM,
    FakeTMDB,
    make_auth_headers,
)

ROASTS = "/api/v1/roasts"

RESPONSE_FIELDS = {
    "id",
    "movie",
    "spice_level",
    "roast_text",
    "gif",
    "status",
    "refusal_reason",
    "message",
    "cached",
    "created_at",
}
MOVIE_FIELDS = {"tmdb_id", "title", "year", "original_language", "poster_url"}


def count_roasts(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count(Roast.id))) or 0


def all_roasts(db: Session) -> list[Roast]:
    db.expire_all()
    return list(db.scalars(select(Roast).order_by(Roast.created_at)).all())


def add_movies(fake_tmdb: FakeTMDB, count: int) -> list[int]:
    """Register ``count`` extra roastable movies with the fake TMDB; return their ids."""
    ids = []
    for i in range(count):
        tmdb_id = MOVIE_ID + 1 + i
        fake_tmdb.movies[tmdb_id] = dataclasses.replace(
            MOVIE, tmdb_id=tmdb_id, title=f"{MOVIE.title} {i + 2}"
        )
        ids.append(tmdb_id)
    return ids


# --- create ------------------------------------------------------------------------------------
def test_create_roast_completed(
    client: TestClient, db: Session, fake_llm: FakeLLM, fake_tmdb: FakeTMDB, fake_gifs: FakeGifs
) -> None:
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID, "spice_level": "extra_spicy"})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert set(body["movie"]) == MOVIE_FIELDS
    assert body["status"] == "completed"
    assert body["roast_text"] == FAKE_ROAST_TEXT
    assert body["cached"] is False
    assert body["message"] is None
    assert body["refusal_reason"] is None
    assert body["spice_level"] == "extra_spicy"
    assert body["movie"] == {
        "tmdb_id": MOVIE_ID,
        "title": MOVIE.title,
        "year": MOVIE.year,
        "original_language": "ta",
        "poster_url": "https://image.tmdb.org/t/p/w342/thunder.jpg",
    }
    assert body["gif"] == {"url": FAKE_GIF.url, "page_url": FAKE_GIF.page_url}
    uuid.UUID(body["id"])
    datetime.fromisoformat(body["created_at"])

    assert fake_tmdb.get_calls == [MOVIE_ID]
    assert fake_gifs.calls == [("facepalm", body["id"])]  # seeded by the roast id
    assert fake_llm.classify_calls == 1
    assert fake_llm.generate_calls == 1
    assert fake_llm.moderate_calls == [FAKE_ROAST_TEXT]  # output moderation only

    [row] = all_roasts(db)
    assert str(row.id) == body["id"]
    assert row.user_id is None
    assert row.status is RoastStatus.completed
    assert row.tmdb_id == MOVIE_ID
    assert row.movie_title == MOVIE.title
    assert row.poster_path == "/thunder.jpg"
    assert row.gif_url == FAKE_GIF.url
    assert row.gif_page_url == FAKE_GIF.page_url
    assert row.client_ip_hash == hash_ip("testclient")
    assert row.client_ip_hash != "testclient"
    assert row.model == settings.OPENAI_MODEL


def test_default_spice_is_medium(client: TestClient) -> None:
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 201
    assert response.json()["spice_level"] == "medium"


def test_movie_without_poster_has_null_poster_url(client: TestClient, fake_tmdb: FakeTMDB) -> None:
    fake_tmdb.movies[MOVIE_ID] = dataclasses.replace(MOVIE, poster_path=None)
    body = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).json()
    assert body["movie"]["poster_url"] is None


def test_roast_without_gif(client: TestClient, db: Session, fake_gifs: FakeGifs) -> None:
    fake_gifs.gif = None
    body = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).json()
    assert body["status"] == "completed"
    assert body["gif"] is None
    [row] = all_roasts(db)
    assert row.gif_url is None


def test_cache_hit_returns_200_without_llm_call(
    client: TestClient, db: Session, fake_llm: FakeLLM, fake_tmdb: FakeTMDB
) -> None:
    first = client.post(ROASTS, json={"tmdb_id": MOVIE_ID, "spice_level": "mild"})
    assert first.status_code == 201
    second = client.post(ROASTS, json={"tmdb_id": MOVIE_ID, "spice_level": "mild"})
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["roast_text"] == first.json()["roast_text"]
    assert fake_llm.generate_calls == 1
    assert len(fake_tmdb.get_calls) == 1  # cache hits don't even ask TMDB
    assert count_roasts(db) == 1


def test_different_spice_is_a_new_roast(client: TestClient, db: Session, fake_llm: FakeLLM) -> None:
    a = client.post(ROASTS, json={"tmdb_id": MOVIE_ID, "spice_level": "mild"})
    b = client.post(ROASTS, json={"tmdb_id": MOVIE_ID, "spice_level": "extra_spicy"})
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    assert fake_llm.generate_calls == 2
    assert count_roasts(db) == 2


def test_stale_cache_entry_is_not_reused(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(created_at=datetime.now(UTC) - timedelta(hours=settings.ROAST_CACHE_HOURS + 1))
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 201
    assert fake_llm.generate_calls == 1


def test_refused_roast_is_not_a_cache_hit(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(status=RoastStatus.refused, refusal_reason="sensitive_topic")
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 201
    assert fake_llm.generate_calls == 1


def test_failed_roast_is_not_a_cache_hit(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(status=RoastStatus.failed)
    assert client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).status_code == 201
    assert fake_llm.generate_calls == 1


# --- safety ------------------------------------------------------------------------------------
def test_sensitive_movie_is_refused(client: TestClient, db: Session, fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    fake_llm.category = "real_tragedy"
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "sensitive_topic"
    assert body["roast_text"] is None
    assert body["gif"] is None
    assert body["message"] in REFUSAL_LINES
    assert body["movie"]["title"] == MOVIE.title
    assert fake_llm.generate_calls == 0
    [row] = all_roasts(db)
    assert row.status is RoastStatus.refused
    assert row.roast_text is None


def test_refused_message_is_stable_for_permalink(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    created = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).json()
    fetched = client.get(f"{ROASTS}/{created['id']}").json()
    assert fetched["message"] == created["message"]


def test_output_flagged_roast_is_refused(
    client: TestClient, db: Session, fake_llm: FakeLLM
) -> None:
    fake_llm.flag_output = True
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "output_flagged"
    assert body["roast_text"] is None
    assert body["gif"] is None
    [row] = all_roasts(db)
    assert row.roast_text is None  # flagged text is never stored
    assert row.gif_url is None


def test_model_self_refusal_is_refused(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.roast_text = REFUSAL_LINES[0]
    body = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "sensitive_topic"
    assert body["roast_text"] is None


# --- failures ----------------------------------------------------------------------------------
def test_llm_failure_is_502_and_persists_failed_row(
    client: TestClient, db: Session, fake_llm: FakeLLM
) -> None:
    fake_llm.generate_error = UpstreamError(detail="OpenAI generation failed: APITimeoutError")
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == "OpenAI generation failed: APITimeoutError"
    assert body["message"]
    [row] = all_roasts(db)
    assert row.status is RoastStatus.failed
    assert row.roast_text is None


def test_failed_roast_permalink_shows_failure_line(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(text: str) -> bool:
        raise UpstreamError("down")

    monkeypatch.setattr(llm_client, "moderate", boom)
    assert client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).status_code == 502
    [row] = all_roasts(db)
    body = client.get(f"{ROASTS}/{row.id}").json()
    assert body["status"] == "failed"
    assert body["message"] == FAILURE_LINE
    assert body["roast_text"] is None


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (NotFoundError("Movie not found"), 404),
        (UpstreamError("Movie database is unreachable"), 502),
    ],
)
def test_tmdb_errors_propagate_and_persist_nothing(
    client: TestClient,
    db: Session,
    fake_tmdb: FakeTMDB,
    fake_llm: FakeLLM,
    error: NotFoundError,
    status: int,
) -> None:
    fake_tmdb.error = error
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == status
    assert response.json()["detail"] == str(error)
    assert set(response.json()) == {"detail", "message"}
    assert count_roasts(db) == 0
    assert fake_llm.classify_calls == 0


def test_unknown_movie_is_404(client: TestClient, db: Session) -> None:
    response = client.post(ROASTS, json={"tmdb_id": 999})
    assert response.status_code == 404
    assert count_roasts(db) == 0


def test_movie_with_too_little_info_is_422(
    client: TestClient, db: Session, fake_tmdb: FakeTMDB, fake_llm: FakeLLM
) -> None:
    fake_tmdb.movies[MOVIE_ID] = dataclasses.replace(MOVIE, overview="", cast=())
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert response.status_code == 422
    assert response.json()["message"]
    assert count_roasts(db) == 0
    assert fake_llm.classify_calls == 0


# --- validation --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload",
    [
        {"tmdb_id": 0},
        {"tmdb_id": -5},
        {"tmdb_id": 3_000_000_000},
        {"tmdb_id": "abc"},
        {"tmdb_id": 1.5},
        {"tmdb_id": MOVIE_ID, "spice_level": "nuclear"},
        {"tmdb_id": MOVIE_ID, "spice_level": "MILD"},
        {"url": "https://news.example.com/story"},
        {"spice_level": "mild"},
        {},
    ],
)
def test_validation_errors(
    client: TestClient, db: Session, fake_tmdb: FakeTMDB, payload: dict[str, object]
) -> None:
    response = client.post(ROASTS, json=payload)
    assert response.status_code == 422
    assert fake_tmdb.get_calls == []
    assert count_roasts(db) == 0


# --- ownership ---------------------------------------------------------------------------------
def test_signed_in_create_links_user(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}, headers=auth_headers)
    assert response.status_code == 201
    [row] = all_roasts(db)
    assert row.user_id == user.id


def test_signed_in_cache_hit_of_other_roast_creates_copy(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    fake_llm: FakeLLM,
) -> None:
    anon = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).json()
    response = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is True
    assert body["id"] != anon["id"]
    assert body["roast_text"] == anon["roast_text"]
    assert body["gif"] == anon["gif"]
    assert body["movie"] == anon["movie"]
    assert fake_llm.generate_calls == 1

    rows = all_roasts(db)
    assert len(rows) == 2
    copy = next(r for r in rows if str(r.id) == body["id"])
    assert copy.user_id == user.id

    # Asking again returns the user's own copy instead of creating another one.
    again = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}, headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
    assert count_roasts(db) == 2

    listed = client.get(f"{ROASTS}/me", headers=auth_headers).json()
    assert [item["id"] for item in listed["items"]] == [body["id"]]


def test_signed_in_cache_hit_of_own_roast_returns_it(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    first = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}, headers=auth_headers).json()
    second = client.post(ROASTS, json={"tmdb_id": MOVIE_ID}, headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert count_roasts(db) == 1


def test_invalid_token_on_create_is_401(client: TestClient, db: Session) -> None:
    response = client.post(
        ROASTS, json={"tmdb_id": MOVIE_ID}, headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401
    assert count_roasts(db) == 0


# --- get ---------------------------------------------------------------------------------------
def test_get_roast_by_id(client: TestClient, roast_factory: Callable[..., Roast]) -> None:
    roast = roast_factory()
    response = client.get(f"{ROASTS}/{roast.id}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["id"] == str(roast.id)
    assert body["cached"] is False
    assert body["roast_text"] == FAKE_ROAST_TEXT
    assert body["movie"]["title"] == MOVIE.title


@pytest.mark.parametrize("roast_id", ["not-a-uuid", "123", str(uuid.uuid4())])
def test_get_roast_not_found(client: TestClient, roast_id: str) -> None:
    response = client.get(f"{ROASTS}/{roast_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Roast not found"


def test_xss_roast_text_is_returned_verbatim_as_json(client: TestClient, fake_llm: FakeLLM) -> None:
    payload = '<script>alert("x")</script><img src=x onerror=alert(1)> machan'
    fake_llm.roast_text = payload
    created = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert created.status_code == 201
    assert created.headers["content-type"].startswith("application/json")
    assert created.json()["roast_text"] == payload
    fetched = client.get(f"{ROASTS}/{created.json()['id']}")
    assert fetched.headers["content-type"].startswith("application/json")
    assert fetched.json()["roast_text"] == payload


# --- /me ---------------------------------------------------------------------------------------
def test_my_roasts_requires_auth(client: TestClient) -> None:
    assert client.get(f"{ROASTS}/me").status_code == 401


def test_my_roasts_pagination_newest_first_and_only_own(
    client: TestClient,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: dict[str, str],
    roast_factory: Callable[..., Roast],
) -> None:
    other = user_factory("other@example.com")
    base = datetime.now(UTC) - timedelta(hours=1)
    mine = [
        roast_factory(user=user, tmdb_id=100 + i, created_at=base + timedelta(minutes=i))
        for i in range(5)
    ]
    roast_factory(user=other, tmdb_id=200)
    roast_factory(tmdb_id=300)

    page1 = client.get(f"{ROASTS}/me?page=1&size=2", headers=auth_headers)
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["size"] == 2
    expected = [str(r.id) for r in reversed(mine)]
    assert [item["id"] for item in body["items"]] == expected[:2]

    page3 = client.get(f"{ROASTS}/me?page=3&size=2", headers=auth_headers).json()
    assert [item["id"] for item in page3["items"]] == expected[4:]

    default = client.get(f"{ROASTS}/me", headers=auth_headers).json()
    assert default["size"] == 20
    assert [item["id"] for item in default["items"]] == expected

    empty = client.get(f"{ROASTS}/me?page=9", headers=auth_headers).json()
    assert empty["items"] == []
    assert empty["total"] == 5


@pytest.mark.parametrize("query", ["page=0", "size=0", "size=51", "page=abc"])
def test_my_roasts_bad_pagination(
    client: TestClient, auth_headers: dict[str, str], query: str
) -> None:
    assert client.get(f"{ROASTS}/me?{query}", headers=auth_headers).status_code == 422


# --- delete ------------------------------------------------------------------------------------
def test_delete_own_roast(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    roast_factory: Callable[..., Roast],
) -> None:
    roast_id = roast_factory(user=user).id
    response = client.delete(f"{ROASTS}/{roast_id}", headers=auth_headers)
    assert response.status_code == 204
    assert response.content == b""
    assert count_roasts(db) == 0
    assert client.get(f"{ROASTS}/{roast_id}").status_code == 404


def test_delete_other_users_roast_is_404(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    auth_headers: dict[str, str],
    roast_factory: Callable[..., Roast],
) -> None:
    roast = roast_factory(user=user_factory("owner@example.com"))
    assert client.delete(f"{ROASTS}/{roast.id}", headers=auth_headers).status_code == 404
    assert count_roasts(db) == 1


def test_delete_anonymous_roast_is_404(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    roast_factory: Callable[..., Roast],
) -> None:
    roast = roast_factory(user=None)
    assert client.delete(f"{ROASTS}/{roast.id}", headers=auth_headers).status_code == 404
    assert count_roasts(db) == 1


@pytest.mark.parametrize("roast_id", ["garbage", str(uuid.uuid4())])
def test_delete_missing_is_404(
    client: TestClient, auth_headers: dict[str, str], roast_id: str
) -> None:
    assert client.delete(f"{ROASTS}/{roast_id}", headers=auth_headers).status_code == 404


def test_delete_requires_auth(
    client: TestClient, db: Session, user: User, roast_factory: Callable[..., Roast]
) -> None:
    roast = roast_factory(user=user)
    assert client.delete(f"{ROASTS}/{roast.id}").status_code == 401
    assert count_roasts(db) == 1


def test_deleting_user_keeps_roasts_anonymous(
    db: Session, user: User, roast_factory: Callable[..., Roast]
) -> None:
    roast_id = roast_factory(user=user).id
    db.delete(user)
    db.commit()
    db.expire_all()
    roast = db.get(Roast, roast_id)
    assert roast is not None
    assert roast.user_id is None


# --- rate limits -------------------------------------------------------------------------------
def test_anonymous_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLM, fake_tmdb: FakeTMDB
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "2/hour")
    ids = add_movies(fake_tmdb, 3)
    for tmdb_id in ids[:2]:
        assert client.post(ROASTS, json={"tmdb_id": tmdb_id}).status_code == 201
    response = client.post(ROASTS, json={"tmdb_id": ids[2]})
    assert response.status_code == 429
    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= 3600
    body = response.json()
    assert body["detail"].startswith("Rate limit exceeded")
    assert body["message"]
    assert fake_llm.generate_calls == 2


def test_spoofed_forwarded_for_does_not_bypass_anon_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_tmdb: FakeTMDB
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    a, b = add_movies(fake_tmdb, 2)
    first = client.post(ROASTS, json={"tmdb_id": a}, headers={"X-Forwarded-For": "203.0.113.1"})
    assert first.status_code == 201
    spoofed = client.post(ROASTS, json={"tmdb_id": b}, headers={"X-Forwarded-For": "203.0.113.2"})
    assert spoofed.status_code == 429


def test_user_limit_is_separate_from_ip(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: dict[str, str],
    fake_tmdb: FakeTMDB,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    monkeypatch.setattr(settings, "RATE_LIMIT_USER", "2/hour")
    ids = add_movies(fake_tmdb, 6)
    assert client.post(ROASTS, json={"tmdb_id": ids[0]}).status_code == 201
    assert client.post(ROASTS, json={"tmdb_id": ids[1]}).status_code == 429
    # Same IP, but signed in -> counted against the user bucket.
    for tmdb_id in ids[2:4]:
        assert (
            client.post(ROASTS, json={"tmdb_id": tmdb_id}, headers=auth_headers).status_code == 201
        )
    assert client.post(ROASTS, json={"tmdb_id": ids[4]}, headers=auth_headers).status_code == 429
    # Another user has their own bucket.
    other = make_auth_headers(user_factory("second@example.com"))
    assert client.post(ROASTS, json={"tmdb_id": ids[5]}, headers=other).status_code == 201


def test_daily_cap_blocks_new_roasts_but_serves_cache(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fake_tmdb: FakeTMDB
) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 1)
    [other] = add_movies(fake_tmdb, 1)
    assert client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).status_code == 201

    cached = client.post(ROASTS, json={"tmdb_id": MOVIE_ID})
    assert cached.status_code == 200
    assert cached.json()["cached"] is True

    blocked = client.post(ROASTS, json={"tmdb_id": other})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Daily roast limit reached"
    assert 0 < int(blocked.headers["Retry-After"]) <= 86400
    # The cap is checked after the (cheap) TMDB lookup, right before any OpenAI call.
    assert fake_tmdb.get_calls == [MOVIE_ID, other]
    assert count_roasts(db) == 1


def test_unknown_movies_do_not_consume_daily_cap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 1)
    for junk_id in (991, 992, 993):
        assert client.post(ROASTS, json={"tmdb_id": junk_id}).status_code == 404
    assert client.post(ROASTS, json={"tmdb_id": MOVIE_ID}).status_code == 201


def test_get_is_not_rate_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    roast_factory: Callable[..., Roast],
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    roast = roast_factory(spice=SpiceLevel.mild)
    for _ in range(3):
        assert client.get(f"{ROASTS}/{roast.id}").status_code == 200
