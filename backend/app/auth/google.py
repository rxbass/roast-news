"""Google OAuth 2.0 (authorization-code flow) helpers.

Holds the outbound HTTP calls to Google and the signed ``oauth_state`` cookie helpers.
No database access lives here.
"""

import hmac
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint URL
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"
HTTP_TIMEOUT_SECONDS = 10.0

STATE_COOKIE_NAME = "oauth_state"
STATE_COOKIE_MAX_AGE = 600
STATE_COOKIE_PATH = "/api/v1/auth"
_STATE_SALT = "oauth-state"


class GoogleOAuthError(Exception):
    """Raised when the token exchange or profile fetch with Google fails."""


@dataclass(frozen=True)
class GoogleUserInfo:
    """The subset of the OpenID Connect userinfo payload we use."""

    google_id: str
    email: str
    email_verified: bool
    full_name: str | None
    avatar_url: str | None


def is_configured() -> bool:
    """True when both the Google client id and secret are set."""
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


# --- state cookie --------------------------------------------------------------------------------
def _state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=_STATE_SALT)


def generate_state() -> str:
    """Return a fresh random OAuth ``state`` value."""
    return secrets.token_urlsafe(32)


def sign_state(state: str, nonce: str) -> str:
    """Sign ``state`` plus the browser's ``nonce`` for the ``oauth_state`` cookie.

    The nonce is echoed back to the SPA with the tokens, so the callback page only accepts
    tokens from a sign-in that *this* browser tab started (blocks login-CSRF via a crafted
    ``/auth/callback#access_token=...`` link).
    """
    return _state_serializer().dumps({"s": state, "n": nonce})


def verify_state(cookie_value: str | None, query_state: str | None) -> str | None:
    """Return the stored nonce if the signed cookie is valid, unexpired and matches ``state``.

    Returns ``None`` on any mismatch.
    """
    if not cookie_value or not query_state:
        return None
    try:
        payload = _state_serializer().loads(cookie_value, max_age=STATE_COOKIE_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(payload, dict):
        return None
    expected, nonce = payload.get("s"), payload.get("n")
    if not isinstance(expected, str) or not isinstance(nonce, str):
        return None
    if not hmac.compare_digest(expected.encode("utf-8"), query_state.encode("utf-8")):
        return None
    return nonce


# --- Google endpoints ----------------------------------------------------------------------------
def build_authorization_url(state: str) -> str:
    """Build the Google consent-screen URL for ``state``."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_access_token(code: str) -> str:
    """Exchange an authorization ``code`` for a Google access token.

    Raises ``GoogleOAuthError`` on network errors, non-200 responses, or a missing token.
    """
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL, data=data, headers={"Accept": "application/json"}
            )
    except httpx.HTTPError as exc:
        logger.warning("Google token exchange request failed: %s", type(exc).__name__)
        raise GoogleOAuthError("token exchange request failed") from exc

    if response.status_code != 200:
        logger.warning("Google token exchange returned HTTP %s", response.status_code)
        raise GoogleOAuthError("token exchange rejected")
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleOAuthError("token response is not JSON") from exc
    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(access_token, str) or not access_token:
        raise GoogleOAuthError("token response has no access_token")
    return access_token


async def fetch_user_info(access_token: str) -> GoogleUserInfo:
    """Fetch the signed-in user's OpenID Connect profile.

    Raises ``GoogleOAuthError`` on network errors, non-200 responses, or missing sub/email.
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
    except httpx.HTTPError as exc:
        logger.warning("Google userinfo request failed: %s", type(exc).__name__)
        raise GoogleOAuthError("userinfo request failed") from exc

    if response.status_code != 200:
        logger.warning("Google userinfo returned HTTP %s", response.status_code)
        raise GoogleOAuthError("userinfo rejected")
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleOAuthError("userinfo response is not JSON") from exc
    if not isinstance(payload, dict):
        raise GoogleOAuthError("userinfo response is not an object")

    sub = payload.get("sub")
    email = payload.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
        raise GoogleOAuthError("userinfo missing sub/email")

    verified = payload.get("email_verified")
    # Google sends a boolean; tolerate the legacy string form too.
    email_verified = verified is True or verified == "true"
    name = payload.get("name")
    picture = payload.get("picture")
    return GoogleUserInfo(
        google_id=sub,
        email=email.strip().lower(),
        email_verified=email_verified,
        full_name=name[:255] if isinstance(name, str) and name else None,
        avatar_url=picture if isinstance(picture, str) and 0 < len(picture) <= 1024 else None,
    )
