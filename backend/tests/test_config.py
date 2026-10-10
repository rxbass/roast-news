"""Settings parsing helpers and app-level error rendering."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.core.security import hash_ip
from app.exceptions import AppError, RateLimitError, UpstreamError


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "DATABASE_URL": "postgresql://u:p@h:5432/db_test",
        "SECRET_KEY": "x" * 32,
        "IP_HASH_SALT": "salt",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type,call-arg]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg2://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_sqlalchemy_database_url(raw: str, expected: str) -> None:
    assert make_settings(DATABASE_URL=raw).sqlalchemy_database_url == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://a.com, https://b.com/ ,", ["https://a.com", "https://b.com/"]),
        ('["https://a.com", "https://b.com"]', ["https://a.com", "https://b.com"]),
    ],
)
def test_cors_origins_parsing(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)
    parsed = make_settings().CORS_ORIGINS
    assert parsed == expected


def test_allowed_origins_dedupes_and_includes_frontend() -> None:
    s = make_settings(
        CORS_ORIGINS=["https://a.com/", "https://a.com"], FRONTEND_URL="https://app.example.com/"
    )
    assert s.allowed_origins == ["https://a.com", "https://app.example.com"]


PROD_OK: dict[str, object] = {
    "ENVIRONMENT": "Production",
    "SECRET_KEY": "k" * 48,
    "IP_HASH_SALT": "s" * 24,
    "FRONTEND_URL": "https://roastnews.example",
}


def test_is_production() -> None:
    assert make_settings(**PROD_OK).is_production is True
    assert make_settings(ENVIRONMENT="development").is_production is False


@pytest.mark.parametrize(
    ("override", "problem"),
    [
        ({"SECRET_KEY": "change-me-generate-a-long-random-secret-please"}, "SECRET_KEY"),
        ({"SECRET_KEY": "too-short"}, "SECRET_KEY"),
        ({"IP_HASH_SALT": "change-me-generate-a-random-salt"}, "IP_HASH_SALT"),
        ({"IP_HASH_SALT": "salt"}, "IP_HASH_SALT"),
        ({"ALGORITHM": "none"}, "ALGORITHM"),
        ({"FRONTEND_URL": "http://localhost:5173"}, "FRONTEND_URL"),
    ],
)
def test_production_rejects_unsafe_settings(override: dict[str, object], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        make_settings(**{**PROD_OK, **override})


def test_development_allows_placeholder_secrets() -> None:
    dev = make_settings(SECRET_KEY="change-me", IP_HASH_SALT="salt", ENVIRONMENT="development")
    assert dev.is_production is False


def test_settings_point_at_test_database() -> None:
    assert settings.sqlalchemy_database_url.endswith("_test")
    assert len(settings.SECRET_KEY) >= 32


def test_hash_ip_is_salted() -> None:
    assert hash_ip("1.2.3.4") == hash_ip("1.2.3.4")
    assert hash_ip("1.2.3.4") != hash_ip("1.2.3.5")
    assert "1.2.3.4" not in hash_ip("1.2.3.4")
    assert len(hash_ip("1.2.3.4")) == 64


def test_exception_defaults() -> None:
    err = UpstreamError()
    assert err.status_code == 502
    assert err.detail == "Upstream service error"
    assert err.message
    custom = AppError("boom", "", status_code=418)
    assert custom.status_code == 418
    assert custom.message == ""
    assert RateLimitError(retry_after=5).retry_after == 5


def test_cors_preflight_allows_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/roasts",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/roasts",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
