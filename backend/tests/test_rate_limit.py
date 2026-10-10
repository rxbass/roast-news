"""Rate-limit helpers (key function, client IP, dynamic limits, daily cap) and 429 rendering."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.auth.jwt import create_access_token
from app.config import settings
from app.core import rate_limit
from app.core.rate_limit import (
    check_daily_limit,
    dynamic_limit,
    get_client_ip,
    get_user_id_from_request,
    rate_limit_key,
    reset_daily_limit,
)
from app.exceptions import RateLimitError
from app.main import _retry_after_seconds


def make_request(
    headers: dict[str, str] | None = None, client: tuple[str, int] | None = ("198.51.100.7", 1234)
) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/roasts",
        "headers": raw,
        "client": client,
        "query_string": b"",
    }
    return Request(scope)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- client ip ---------------------------------------------------------------------------------
def test_client_ip_from_socket() -> None:
    assert get_client_ip(make_request()) == "198.51.100.7"


def test_client_ip_ignores_forwarded_for_without_trusted_proxy() -> None:
    # Exposed directly: X-Forwarded-For is client-controlled, so the socket peer wins.
    request = make_request({"X-Forwarded-For": "203.0.113.9"})
    assert get_client_ip(request) == "198.51.100.7"


@pytest.mark.parametrize(
    ("proxies", "header", "expected"),
    [
        # One trusted proxy: it appended the real peer last; earlier hops may be forged.
        (1, "6.6.6.6, 203.0.113.9", "203.0.113.9"),
        (2, "6.6.6.6, 203.0.113.9, 10.0.0.5", "203.0.113.9"),
        (1, " 203.0.113.9 ", "203.0.113.9"),
        # Fewer hops than trusted proxies (misconfigured / direct hit): fall back to the peer.
        (2, "203.0.113.9", "198.51.100.7"),
        (1, " , ", "198.51.100.7"),
    ],
)
def test_client_ip_with_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch, proxies: int, header: str, expected: str
) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", proxies)
    assert get_client_ip(make_request({"X-Forwarded-For": header})) == expected


def test_client_ip_unknown_without_peer() -> None:
    assert get_client_ip(make_request(client=None)) == "unknown"


# --- key function ------------------------------------------------------------------------------
def test_key_for_signed_in_user() -> None:
    request = make_request(bearer(create_access_token(7)))
    assert get_user_id_from_request(request) == "7"
    assert rate_limit_key(request) == "user:7"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer not-a-jwt"},
    ],
)
def test_key_falls_back_to_ip(headers: dict[str, str]) -> None:
    request = make_request(headers)
    assert get_user_id_from_request(request) is None
    assert rate_limit_key(request) == "ip:198.51.100.7"


def test_refresh_type_or_subjectless_tokens_fall_back_to_ip() -> None:
    import jwt

    exp = datetime.now(UTC) + timedelta(minutes=5)
    for payload in ({"sub": "1", "type": "refresh", "exp": exp}, {"type": "access", "exp": exp}):
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        assert rate_limit_key(make_request(bearer(token))) == "ip:198.51.100.7"


def test_dynamic_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "5/hour")
    monkeypatch.setattr(settings, "RATE_LIMIT_USER", "20/hour")
    assert dynamic_limit("user:1") == "20/hour"
    assert dynamic_limit("ip:1.2.3.4") == "5/hour"
    assert dynamic_limit("anything-else") == "5/hour"


# --- daily cap ---------------------------------------------------------------------------------
def test_daily_limit_counts_and_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 2)
    assert check_daily_limit() == 1
    assert check_daily_limit(increment=False) == 1
    assert check_daily_limit() == 2
    with pytest.raises(RateLimitError) as exc_info:
        check_daily_limit()
    assert exc_info.value.status_code == 429
    assert 0 < (exc_info.value.retry_after or 0) <= 86400
    reset_daily_limit()
    assert check_daily_limit() == 1


def test_daily_limit_rolls_over_at_utc_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 1)
    check_daily_limit()
    with pytest.raises(RateLimitError):
        check_daily_limit()
    rate_limit._daily.day = rate_limit._daily.day - timedelta(days=1)
    assert check_daily_limit() == 1


def test_seconds_until_utc_midnight() -> None:
    assert (
        rate_limit._seconds_until_utc_midnight(datetime(2026, 1, 1, 23, 59, 30, tzinfo=UTC)) == 30
    )
    assert rate_limit._seconds_until_utc_midnight(datetime(2026, 1, 1, 0, 0, tzinfo=UTC)) == 86400
    assert (
        rate_limit._seconds_until_utc_midnight(datetime(2026, 1, 1, 23, 59, 59, 999999, tzinfo=UTC))
        == 1
    )


# --- 429 Retry-After fallback ------------------------------------------------------------------
def test_retry_after_falls_back_to_limit_expiry() -> None:
    limit = SimpleNamespace(limit=SimpleNamespace(get_expiry=lambda: 3600))
    exc = SimpleNamespace(limit=limit)
    assert _retry_after_seconds(make_request(), exc) == 3600  # type: ignore[arg-type]


def test_retry_after_defaults_to_60_without_limit() -> None:
    exc = SimpleNamespace(limit=None)
    assert _retry_after_seconds(make_request(), exc) == 60  # type: ignore[arg-type]
