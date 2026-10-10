"""Auth: JWT helpers, dependencies, refresh rotation, logout and the Google OAuth flow."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import google
from app.auth.jwt import create_access_token, decode_access_token, hash_token
from app.config import settings
from app.exceptions import UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import auth_service
from tests.conftest import MOVIE_ID, make_auth_headers

AUTH = "/api/v1/auth"
CALLBACK_PREFIX = "http://localhost:5173/auth/callback#"


def encode(payload: dict[str, object], key: str | None = None) -> str:
    return jwt.encode(payload, key or settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def now() -> datetime:
    return datetime.now(UTC)


# --- JWT ---------------------------------------------------------------------------------------
def test_access_token_roundtrip() -> None:
    token = create_access_token(42)
    assert decode_access_token(token) == 42
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["type"] == "access"
    assert payload["sub"] == "42"
    assert payload["exp"] - payload["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.parametrize(
    ("token_factory", "detail"),
    [
        (lambda: "garbage", "Invalid token"),
        (lambda: create_access_token(1) + "x", "Invalid token"),
        (
            lambda: encode(
                {"sub": "1", "type": "access", "iat": now(), "exp": now() + timedelta(minutes=5)},
                key="another-secret-key-that-is-long-enough-123",
            ),
            "Invalid token",
        ),
        (
            lambda: encode(
                {
                    "sub": "1",
                    "type": "access",
                    "iat": now() - timedelta(hours=2),
                    "exp": now() - timedelta(hours=1),
                }
            ),
            "Token expired",
        ),
        (
            lambda: encode(
                {"sub": "1", "type": "refresh", "iat": now(), "exp": now() + timedelta(minutes=5)}
            ),
            "Invalid token type",
        ),
        (
            lambda: encode(
                {"sub": "abc", "type": "access", "iat": now(), "exp": now() + timedelta(minutes=5)}
            ),
            "Invalid token subject",
        ),
        (
            lambda: encode({"sub": "1", "type": "access", "exp": now() + timedelta(minutes=5)}),
            "Invalid token",
        ),
    ],
)
def test_decode_access_token_rejects(token_factory: Callable[[], str], detail: str) -> None:
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(token_factory())
    assert exc_info.value.detail == detail
    assert exc_info.value.status_code == 401


def test_hash_token_is_sha256() -> None:
    assert len(hash_token("abc")) == 64
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")


# --- /me + dependencies ------------------------------------------------------------------------
def test_me_returns_profile(client: TestClient, user: User, auth_headers: dict[str, str]) -> None:
    response = client.get(f"{AUTH}/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "email", "full_name", "avatar_url", "created_at"}
    assert body["id"] == user.id
    assert body["email"] == "machan@example.com"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer garbage"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
    ],
)
def test_me_unauthorized(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(f"{AUTH}/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["message"]


def test_me_unknown_or_inactive_user_is_401(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    assert client.get(f"{AUTH}/me", headers=make_auth_headers_for_id(999_999)).status_code == 401
    inactive = user_factory("off@example.com", is_active=False)
    assert client.get(f"{AUTH}/me", headers=make_auth_headers(inactive)).status_code == 401


def make_auth_headers_for_id(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_optional_user_anonymous_and_invalid(client: TestClient) -> None:
    body = {"tmdb_id": MOVIE_ID}
    assert client.post("/api/v1/roasts", json=body).status_code == 201
    expired = encode(
        {
            "sub": "1",
            "type": "access",
            "iat": now() - timedelta(hours=2),
            "exp": now() - timedelta(hours=1),
        }
    )
    response = client.post(
        "/api/v1/roasts", json=body, headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


# --- refresh / logout --------------------------------------------------------------------------
def issue(db: Session, user: User) -> tuple[str, str]:
    pair = auth_service.issue_token_pair(db, user)
    return pair.access_token, pair.refresh_token


def stored_tokens(db: Session, user: User) -> list[RefreshToken]:
    db.expire_all()
    return list(
        db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id).order_by("id"))
    )


def test_refresh_rotation(client: TestClient, db: Session, user: User) -> None:
    _, refresh = issue(db, user)
    response = client.post(f"{AUTH}/refresh", json={"refresh_token": refresh})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["refresh_token"] != refresh
    assert decode_access_token(body["access_token"]) == user.id

    tokens = stored_tokens(db, user)
    assert [t.revoked for t in tokens] == [True, False]
    assert tokens[1].token_hash == hash_token(body["refresh_token"])
    assert all(t.token_hash != refresh for t in tokens)  # only hashes are stored

    # The new access token works.
    me = client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_reusing_revoked_refresh_token_revokes_family(
    client: TestClient, db: Session, user: User
) -> None:
    _, refresh = issue(db, user)
    _, other_session = issue(db, user)
    rotated = client.post(f"{AUTH}/refresh", json={"refresh_token": refresh}).json()

    reuse = client.post(f"{AUTH}/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == "Refresh token reused"
    assert all(t.revoked for t in stored_tokens(db, user))

    for token in (rotated["refresh_token"], other_session):
        assert client.post(f"{AUTH}/refresh", json={"refresh_token": token}).status_code == 401


def test_unknown_refresh_token_is_401(client: TestClient) -> None:
    response = client.post(f"{AUTH}/refresh", json={"refresh_token": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


@pytest.mark.parametrize("body", [{}, {"refresh_token": ""}, {"refresh_token": "x" * 513}])
def test_refresh_validation(client: TestClient, body: dict[str, str]) -> None:
    assert client.post(f"{AUTH}/refresh", json=body).status_code == 422


def test_expired_refresh_token_is_401(client: TestClient, db: Session, user: User) -> None:
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token("old-token"),
            expires_at=now() - timedelta(seconds=1),
        )
    )
    db.commit()
    response = client.post(f"{AUTH}/refresh", json={"refresh_token": "old-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token expired"


def test_refresh_for_inactive_user_is_401(client: TestClient, db: Session, user: User) -> None:
    _, refresh = issue(db, user)
    user.is_active = False
    db.commit()
    response = client.post(f"{AUTH}/refresh", json={"refresh_token": refresh})
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found or inactive"
    assert all(t.revoked for t in stored_tokens(db, user))


def test_logout_revokes_token(client: TestClient, db: Session, user: User) -> None:
    _, refresh = issue(db, user)
    response = client.post(f"{AUTH}/logout", json={"refresh_token": refresh})
    assert response.status_code == 204
    assert response.content == b""
    assert stored_tokens(db, user)[0].revoked is True
    assert client.post(f"{AUTH}/refresh", json={"refresh_token": refresh}).status_code == 401


def test_logout_unknown_token_is_204(client: TestClient) -> None:
    assert client.post(f"{AUTH}/logout", json={"refresh_token": "unknown"}).status_code == 204


# --- Google OAuth ------------------------------------------------------------------------------
@pytest.fixture
def google_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")


@pytest.fixture
def google_api() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def mock_google(
    router: respx.MockRouter,
    *,
    sub: str = "google-sub-1",
    email: str = "New.User@Example.com",
    verified: object = True,
    token_status: int = 200,
) -> None:
    router.post(google.GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(token_status, json={"access_token": "g-access"})
    )
    router.get(google.GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "sub": sub,
                "email": email,
                "email_verified": verified,
                "name": "New User",
                "picture": "https://lh3.googleusercontent.com/a/pic",
            },
        )
    )


def callback(
    client: TestClient,
    *,
    state: str = "the-state",
    cookie_state: str | None = "the-state",
    **params: str,
) -> httpx.Response:
    headers = {}
    if cookie_state is not None:
        headers["Cookie"] = f"{google.STATE_COOKIE_NAME}={google.sign_state(cookie_state, NONCE)}"
    query = {"state": state, **params}
    return client.get(f"{AUTH}/google/callback", params=query, headers=headers)


NONCE = "spa-nonce-0123456789abcdef"


def fragment(response: httpx.Response) -> dict[str, str]:
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(CALLBACK_PREFIX)
    return {k: v[0] for k, v in parse_qs(urlsplit(location).fragment).items()}


def test_google_login_unconfigured_is_503(client: TestClient) -> None:
    response = client.get(f"{AUTH}/google", params={"nonce": NONCE})
    assert response.status_code == 503
    assert response.json()["detail"] == "Google OAuth not configured"


def test_google_login_redirects_with_state_cookie(
    client: TestClient, google_configured: None
) -> None:
    response = client.get(f"{AUTH}/google", params={"nonce": NONCE})
    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == google.GOOGLE_AUTH_URL
    query = {k: v[0] for k, v in parse_qs(location.query).items()}
    assert query["client_id"] == settings.GOOGLE_CLIENT_ID
    assert query["redirect_uri"] == settings.GOOGLE_REDIRECT_URI
    assert query["response_type"] == "code"
    assert query["scope"] == "openid email profile"

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{google.STATE_COOKIE_NAME}=")
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "path=/api/v1/auth" in lowered
    assert "max-age=600" in lowered
    assert "secure" not in lowered  # not production
    signed = cookie.split(";", 1)[0].split("=", 1)[1]
    assert google.verify_state(signed, query["state"]) == NONCE


def test_google_login_cookie_is_secure_in_production(
    client: TestClient, google_configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = client.get(f"{AUTH}/google", params={"nonce": NONCE})
    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    ("state", "cookie_state"),
    [("the-state", None), ("other-state", "the-state"), ("", "the-state")],
)
def test_callback_state_mismatch(
    client: TestClient, google_configured: None, state: str, cookie_state: str | None
) -> None:
    response = callback(client, state=state, cookie_state=cookie_state, code="c")
    assert fragment(response) == {"error": "state_mismatch"}
    # The state cookie is always cleared.
    assert f'{google.STATE_COOKIE_NAME}=""' in response.headers["set-cookie"]


def test_callback_tampered_cookie_is_state_mismatch(
    client: TestClient, google_configured: None
) -> None:
    response = client.get(
        f"{AUTH}/google/callback",
        params={"state": "s", "code": "c"},
        headers={"Cookie": f"{google.STATE_COOKIE_NAME}=forged.value.sig"},
    )
    assert fragment(response) == {"error": "state_mismatch"}


@pytest.mark.parametrize(
    ("error", "code"), [("access_denied", "access_denied"), ("x", "oauth_failed")]
)
def test_callback_google_error(
    client: TestClient, google_configured: None, error: str, code: str
) -> None:
    assert fragment(callback(client, error=error)) == {"error": code}


def test_callback_without_code(client: TestClient, google_configured: None) -> None:
    assert fragment(callback(client)) == {"error": "oauth_failed"}


def test_callback_unconfigured(client: TestClient) -> None:
    assert fragment(callback(client, code="c")) == {"error": "oauth_failed"}


def test_callback_token_exchange_failure(
    client: TestClient, google_configured: None, google_api: respx.MockRouter, db: Session
) -> None:
    mock_google(google_api, token_status=400)
    assert fragment(callback(client, code="c")) == {"error": "oauth_failed"}
    assert db.scalar(select(User)) is None


def test_callback_unverified_email(
    client: TestClient, google_configured: None, google_api: respx.MockRouter, db: Session
) -> None:
    mock_google(google_api, verified=False)
    assert fragment(callback(client, code="c")) == {"error": "email_unverified"}
    assert db.scalar(select(User)) is None


def test_callback_disabled_account(
    client: TestClient,
    google_configured: None,
    google_api: respx.MockRouter,
    user_factory: Callable[..., User],
) -> None:
    user_factory("off@example.com", google_id="google-sub-1", is_active=False)
    mock_google(google_api, email="off@example.com")
    assert fragment(callback(client, code="c")) == {"error": "account_disabled"}


def test_callback_database_error(
    client: TestClient,
    google_configured: None,
    google_api: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(db: Session, info: google.GoogleUserInfo) -> User:
        raise SQLAlchemyError("db down")

    monkeypatch.setattr(auth_service, "upsert_google_user", broken)
    mock_google(google_api)
    assert fragment(callback(client, code="c")) == {"error": "oauth_failed"}


def test_callback_happy_path_creates_user(
    client: TestClient, google_configured: None, google_api: respx.MockRouter, db: Session
) -> None:
    mock_google(google_api, verified="true")
    response = callback(client, code="auth-code")
    tokens = fragment(response)
    assert set(tokens) == {"access_token", "refresh_token", "token_type", "nonce"}
    assert tokens["nonce"] == NONCE  # echoed so the SPA can bind tokens to its own sign-in
    assert tokens["token_type"] == "bearer"

    token_request = google_api.calls[0].request
    form = parse_qs(token_request.content.decode())
    assert form["code"] == ["auth-code"]
    assert form["grant_type"] == ["authorization_code"]
    assert form["client_secret"] == ["client-secret"]

    user = db.scalar(select(User))
    assert user is not None
    assert user.email == "new.user@example.com"
    assert user.google_id == "google-sub-1"
    assert user.full_name == "New User"
    assert user.avatar_url == "https://lh3.googleusercontent.com/a/pic"

    me = client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    refreshed = client.post(f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200


def test_callback_links_existing_user_by_email(
    client: TestClient,
    google_configured: None,
    google_api: respx.MockRouter,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    existing = user_factory("new.user@example.com", google_id="legacy-id", full_name=None)
    mock_google(google_api, sub="fresh-sub", email="NEW.USER@example.com")
    tokens = fragment(callback(client, code="c"))
    assert decode_access_token(tokens["access_token"]) == existing.id
    db.expire_all()
    users = list(db.scalars(select(User)))
    assert len(users) == 1
    assert users[0].google_id == "fresh-sub"
    assert users[0].full_name == "New User"


def test_callback_existing_google_user_updates_profile(
    client: TestClient,
    google_configured: None,
    google_api: respx.MockRouter,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    existing = user_factory("old@example.com", google_id="google-sub-1")
    mock_google(google_api, email="changed@example.com")
    tokens = fragment(callback(client, code="c"))
    assert decode_access_token(tokens["access_token"]) == existing.id
    db.expire_all()
    assert db.get(User, existing.id).email == "changed@example.com"  # type: ignore[union-attr]


# --- google.py helpers -------------------------------------------------------------------------
def test_verify_state_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    signed = google.sign_state("abc", NONCE)
    assert google.verify_state(signed, "abc") == NONCE
    assert google.verify_state(signed, "abd") is None
    assert google.verify_state(None, "abc") is None
    assert google.verify_state(signed, None) is None
    assert google.verify_state("garbage", "abc") is None
    for bad_payload in ("abc", {"s": "abc"}, {"s": "abc", "n": 5}, {"not": "a dict payload"}):
        assert google.verify_state(google._state_serializer().dumps(bad_payload), "abc") is None
    monkeypatch.setattr(google, "STATE_COOKIE_MAX_AGE", -1)
    assert google.verify_state(signed, "abc") is None  # expired


@pytest.mark.parametrize("nonce", [None, "short", "has spaces in it 1234", "x" * 129])
def test_google_login_requires_valid_nonce(
    client: TestClient, google_configured: None, nonce: str | None
) -> None:
    params = {} if nonce is None else {"nonce": nonce}
    assert client.get(f"{AUTH}/google", params=params).status_code == 422


def test_generate_state_is_random() -> None:
    assert google.generate_state() != google.generate_state()
    assert len(google.generate_state()) >= 40


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"error": "x"}),
        httpx.Response(200, json=["access_token"]),
        httpx.Response(200, json={"access_token": ""}),
    ],
)
async def test_exchange_code_failures(
    google_api: respx.MockRouter, response: httpx.Response
) -> None:
    google_api.post(google.GOOGLE_TOKEN_URL).mock(return_value=response)
    with pytest.raises(google.GoogleOAuthError):
        await google.exchange_code_for_access_token("code")


async def test_exchange_code_network_error(google_api: respx.MockRouter) -> None:
    google_api.post(google.GOOGLE_TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(google.GoogleOAuthError, match="request failed"):
        await google.exchange_code_for_access_token("code")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401),
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, json=["sub"]),
        httpx.Response(200, json={"email": "a@b.com"}),
        httpx.Response(200, json={"sub": "1", "email": ""}),
        httpx.Response(200, json={"sub": 5, "email": "a@b.com"}),
    ],
)
async def test_fetch_user_info_failures(
    google_api: respx.MockRouter, response: httpx.Response
) -> None:
    google_api.get(google.GOOGLE_USERINFO_URL).mock(return_value=response)
    with pytest.raises(google.GoogleOAuthError):
        await google.fetch_user_info("token")


async def test_fetch_user_info_network_error(google_api: respx.MockRouter) -> None:
    google_api.get(google.GOOGLE_USERINFO_URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(google.GoogleOAuthError, match="request failed"):
        await google.fetch_user_info("token")


async def test_fetch_user_info_normalizes_fields(google_api: respx.MockRouter) -> None:
    route = google_api.get(google.GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "sub": "s",
                "email": "  Mixed@Case.COM ",
                "email_verified": "false",
                "name": "n" * 300,
                "picture": "x" * 2000,
            },
        )
    )
    info = await google.fetch_user_info("tok")
    assert route.calls.last.request.headers["authorization"] == "Bearer tok"
    assert info.email == "mixed@case.com"
    assert info.email_verified is False
    assert info.full_name == "n" * 255
    assert info.avatar_url is None
