"""Roast API: create / cache / safety / failures / ownership / rate limits."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_ip
from app.exceptions import BadRequestError, UnprocessableError, UpstreamError
from app.main import app
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import llm_client
from app.services.safety_service import FAILURE_LINE, REFUSAL_LINES
from tests.conftest import FAKE_ROAST_TEXT, FakeLLM, FakeScraper, make_auth_headers

ROASTS = "/api/v1/roasts"
URL = "https://news.example.com/2026/10/road-repairs"

RESPONSE_FIELDS = {
    "id",
    "source_url",
    "source_domain",
    "article_title",
    "spice_level",
    "roast_text",
    "status",
    "refusal_reason",
    "message",
    "cached",
    "created_at",
}


def count_roasts(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count(Roast.id))) or 0


def all_roasts(db: Session) -> list[Roast]:
    db.expire_all()
    return list(db.scalars(select(Roast).order_by(Roast.created_at)).all())


# --- create ------------------------------------------------------------------------------------
def test_create_roast_completed(
    client: TestClient, db: Session, fake_llm: FakeLLM, fake_scraper: FakeScraper
) -> None:
    response = client.post(ROASTS, json={"url": URL, "spice_level": "extra_spicy"})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["status"] == "completed"
    assert body["roast_text"] == FAKE_ROAST_TEXT
    assert body["cached"] is False
    assert body["message"] is None
    assert body["refusal_reason"] is None
    assert body["spice_level"] == "extra_spicy"
    assert body["source_url"] == URL
    assert body["source_domain"] == "news.example.com"
    assert body["article_title"] == fake_scraper.title
    uuid.UUID(body["id"])
    datetime.fromisoformat(body["created_at"])

    assert fake_scraper.calls == [URL]
    assert fake_llm.generate_calls == 1
    assert len(fake_llm.moderate_calls) == 2  # article moderation + output moderation

    [row] = all_roasts(db)
    assert str(row.id) == body["id"]
    assert row.user_id is None
    assert row.status is RoastStatus.completed
    assert row.client_ip_hash == hash_ip("testclient")
    assert row.client_ip_hash != "testclient"
    assert row.article_excerpt == fake_scraper.text[:300]
    assert row.model == settings.OPENAI_MODEL


def test_default_spice_is_medium(client: TestClient) -> None:
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    assert response.json()["spice_level"] == "medium"


def test_cache_hit_returns_200_without_llm_call(
    client: TestClient, db: Session, fake_llm: FakeLLM, fake_scraper: FakeScraper
) -> None:
    first = client.post(ROASTS, json={"url": URL, "spice_level": "mild"})
    assert first.status_code == 201
    second = client.post(ROASTS, json={"url": URL, "spice_level": "mild"})
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["roast_text"] == first.json()["roast_text"]
    assert fake_llm.generate_calls == 1
    assert len(fake_scraper.calls) == 1
    assert count_roasts(db) == 1


def test_tracking_variant_url_hits_cache(client: TestClient, fake_llm: FakeLLM) -> None:
    client.post(ROASTS, json={"url": URL})
    variant = URL.replace("news.example.com", "NEWS.example.com:443") + "/?utm_source=wa#top"
    response = client.post(ROASTS, json={"url": variant})
    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert fake_llm.generate_calls == 1


def test_different_spice_is_a_new_roast(client: TestClient, db: Session, fake_llm: FakeLLM) -> None:
    a = client.post(ROASTS, json={"url": URL, "spice_level": "mild"})
    b = client.post(ROASTS, json={"url": URL, "spice_level": "extra_spicy"})
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    assert fake_llm.generate_calls == 2
    assert count_roasts(db) == 2


def test_stale_cache_entry_is_not_reused(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(
        url=URL,
        created_at=datetime.now(UTC) - timedelta(hours=settings.ROAST_CACHE_HOURS + 1),
    )
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    assert fake_llm.generate_calls == 1


def test_refused_roast_is_not_a_cache_hit(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(url=URL, status=RoastStatus.refused, refusal_reason="sensitive_topic")
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    assert fake_llm.generate_calls == 1


def test_failed_roast_is_not_a_cache_hit(
    client: TestClient, roast_factory: Callable[..., Roast], fake_llm: FakeLLM
) -> None:
    roast_factory(url=URL, status=RoastStatus.failed)
    assert client.post(ROASTS, json={"url": URL}).status_code == 201
    assert fake_llm.generate_calls == 1


# --- safety ------------------------------------------------------------------------------------
def test_sensitive_article_is_refused(client: TestClient, db: Session, fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    fake_llm.category = "death"
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "sensitive_topic"
    assert body["roast_text"] is None
    assert body["message"] in REFUSAL_LINES
    assert fake_llm.generate_calls == 0
    [row] = all_roasts(db)
    assert row.status is RoastStatus.refused
    assert row.roast_text is None


def test_refused_message_is_stable_for_permalink(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    created = client.post(ROASTS, json={"url": URL}).json()
    fetched = client.get(f"{ROASTS}/{created['id']}").json()
    assert fetched["message"] == created["message"]


def test_moderation_flagged_article_is_refused(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.flag_everything = True
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "moderation_flagged"
    assert body["roast_text"] is None
    assert fake_llm.classify_calls == 1  # runs concurrently with moderation
    assert fake_llm.generate_calls == 0


def test_output_flagged_roast_is_refused(
    client: TestClient, db: Session, fake_llm: FakeLLM
) -> None:
    fake_llm.flag_output = True
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "output_flagged"
    assert body["roast_text"] is None
    [row] = all_roasts(db)
    assert row.roast_text is None  # flagged text is never stored


def test_model_self_refusal_is_refused(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.roast_text = REFUSAL_LINES[0]
    body = client.post(ROASTS, json={"url": URL}).json()
    assert body["status"] == "refused"
    assert body["refusal_reason"] == "sensitive_topic"
    assert body["roast_text"] is None


# --- failures ----------------------------------------------------------------------------------
def test_llm_failure_is_502_and_persists_failed_row(
    client: TestClient, db: Session, fake_llm: FakeLLM
) -> None:
    fake_llm.generate_error = UpstreamError(detail="OpenAI generation failed: APITimeoutError")
    response = client.post(ROASTS, json={"url": URL})
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
    assert client.post(ROASTS, json={"url": URL}).status_code == 502
    [row] = all_roasts(db)
    body = client.get(f"{ROASTS}/{row.id}").json()
    assert body["status"] == "failed"
    assert body["message"] == FAILURE_LINE
    assert body["roast_text"] is None


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (BadRequestError("Host resolves to a non-public address"), 400),
        (UnprocessableError("No usable article text found"), 422),
        (UpstreamError("Source site returned HTTP 500"), 502),
    ],
)
def test_scraper_errors_propagate_and_persist_nothing(
    client: TestClient,
    db: Session,
    fake_scraper: FakeScraper,
    fake_llm: FakeLLM,
    error: BadRequestError,
    status: int,
) -> None:
    fake_scraper.error = error
    response = client.post(ROASTS, json={"url": URL})
    assert response.status_code == status
    assert response.json()["detail"] == str(error)
    assert set(response.json()) == {"detail", "message"}
    assert count_roasts(db) == 0
    assert fake_llm.moderate_calls == []


# --- validation --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload",
    [
        {"url": "not a url"},
        {"url": ""},
        {"url": "ftp://news.example.com/file"},
        {"url": "javascript:alert(1)"},
        {"url": "https://news.example.com/" + "a" * 2048},
        {"url": URL, "spice_level": "nuclear"},
        {"url": URL, "spice_level": "MILD"},
        {"spice_level": "mild"},
        {},
    ],
)
def test_validation_errors(
    client: TestClient, db: Session, fake_scraper: FakeScraper, payload: dict[str, str]
) -> None:
    response = client.post(ROASTS, json=payload)
    assert response.status_code == 422
    assert fake_scraper.calls == []
    assert count_roasts(db) == 0


def test_non_ascii_url_that_expands_past_column_limit_is_rejected(
    db: Session, fake_scraper: FakeScraper
) -> None:
    # Regression: the 2048 limit is checked after percent-encoding (Tamil letter -> 9 chars).
    url = "https://news.example.com/" + "த" * 400
    assert len(url) < 2048
    with TestClient(app, raise_server_exceptions=False) as raw_client:
        response = raw_client.post(ROASTS, json={"url": url})
    assert response.status_code == 422
    assert fake_scraper.calls == []
    assert count_roasts(db) == 0


def test_short_tamil_slug_url_is_accepted(client: TestClient) -> None:
    response = client.post(ROASTS, json={"url": "https://news.example.com/" + "த" * 20})
    assert response.status_code == 201


# --- ownership ---------------------------------------------------------------------------------
def test_signed_in_create_links_user(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.post(ROASTS, json={"url": URL}, headers=auth_headers)
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
    anon = client.post(ROASTS, json={"url": URL}).json()
    variant = URL + "?utm_campaign=share"
    response = client.post(ROASTS, json={"url": variant}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is True
    assert body["id"] != anon["id"]
    assert body["roast_text"] == anon["roast_text"]
    assert body["source_url"] == variant
    assert fake_llm.generate_calls == 1

    rows = all_roasts(db)
    assert len(rows) == 2
    copy = next(r for r in rows if str(r.id) == body["id"])
    assert copy.user_id == user.id

    # Asking again returns the user's own copy instead of creating another one.
    again = client.post(ROASTS, json={"url": URL}, headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
    assert count_roasts(db) == 2

    listed = client.get(f"{ROASTS}/me", headers=auth_headers).json()
    assert [item["id"] for item in listed["items"]] == [body["id"]]


def test_signed_in_cache_hit_of_own_roast_returns_it(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    first = client.post(ROASTS, json={"url": URL}, headers=auth_headers).json()
    second = client.post(ROASTS, json={"url": URL}, headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert count_roasts(db) == 1


def test_invalid_token_on_create_is_401(client: TestClient, db: Session) -> None:
    response = client.post(ROASTS, json={"url": URL}, headers={"Authorization": "Bearer not-a-jwt"})
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


@pytest.mark.parametrize("roast_id", ["not-a-uuid", "123", str(uuid.uuid4())])
def test_get_roast_not_found(client: TestClient, roast_id: str) -> None:
    response = client.get(f"{ROASTS}/{roast_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Roast not found"


def test_xss_roast_text_is_returned_verbatim_as_json(client: TestClient, fake_llm: FakeLLM) -> None:
    payload = '<script>alert("x")</script><img src=x onerror=alert(1)> machan'
    fake_llm.roast_text = payload
    created = client.post(ROASTS, json={"url": URL})
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
        roast_factory(user=user, url=f"https://e.com/{i}", created_at=base + timedelta(minutes=i))
        for i in range(5)
    ]
    roast_factory(user=other, url="https://e.com/other")
    roast_factory(url="https://e.com/anon")

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
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLM
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "2/hour")
    for i in range(2):
        assert client.post(ROASTS, json={"url": f"{URL}/{i}"}).status_code == 201
    response = client.post(ROASTS, json={"url": f"{URL}/3"})
    assert response.status_code == 429
    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= 3600
    body = response.json()
    assert body["detail"].startswith("Rate limit exceeded")
    assert body["message"]
    assert fake_llm.generate_calls == 2


def test_spoofed_forwarded_for_does_not_bypass_anon_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    first = client.post(
        ROASTS, json={"url": f"{URL}/a"}, headers={"X-Forwarded-For": "203.0.113.1"}
    )
    assert first.status_code == 201
    spoofed = client.post(
        ROASTS, json={"url": f"{URL}/b"}, headers={"X-Forwarded-For": "203.0.113.2"}
    )
    assert spoofed.status_code == 429


def test_user_limit_is_separate_from_ip(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    monkeypatch.setattr(settings, "RATE_LIMIT_USER", "2/hour")
    assert client.post(ROASTS, json={"url": f"{URL}/0"}).status_code == 201
    assert client.post(ROASTS, json={"url": f"{URL}/1"}).status_code == 429
    # Same IP, but signed in -> counted against the user bucket.
    assert client.post(ROASTS, json={"url": f"{URL}/2"}, headers=auth_headers).status_code == 201
    assert client.post(ROASTS, json={"url": f"{URL}/3"}, headers=auth_headers).status_code == 201
    assert client.post(ROASTS, json={"url": f"{URL}/4"}, headers=auth_headers).status_code == 429
    # Another user has their own bucket.
    other = make_auth_headers(user_factory("second@example.com"))
    assert client.post(ROASTS, json={"url": f"{URL}/5"}, headers=other).status_code == 201


def test_daily_cap_blocks_new_roasts_but_serves_cache(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fake_scraper: FakeScraper
) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 1)
    assert client.post(ROASTS, json={"url": URL}).status_code == 201

    cached = client.post(ROASTS, json={"url": URL})
    assert cached.status_code == 200
    assert cached.json()["cached"] is True

    blocked = client.post(ROASTS, json={"url": f"{URL}/new"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Daily roast limit reached"
    assert 0 < int(blocked.headers["Retry-After"]) <= 86400
    # The cap is checked after the (cheap) fetch, right before any OpenAI call.
    assert len(fake_scraper.calls) == 2
    assert count_roasts(db) == 1


def test_unfetchable_urls_do_not_consume_daily_cap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_scraper: FakeScraper
) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 1)
    fake_scraper.error = BadRequestError(detail="URL not allowed")
    for i in range(3):
        assert client.post(ROASTS, json={"url": f"{URL}/junk{i}"}).status_code == 400
    fake_scraper.error = None
    assert client.post(ROASTS, json={"url": f"{URL}/real"}).status_code == 201


def test_get_is_not_rate_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    roast_factory: Callable[..., Roast],
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1/hour")
    roast = roast_factory(spice=SpiceLevel.mild)
    for _ in range(3):
        assert client.get(f"{ROASTS}/{roast.id}").status_code == 200
