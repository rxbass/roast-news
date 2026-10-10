"""JWT access tokens and opaque refresh-token helpers.

Access tokens are short-lived HS256 JWTs with the payload
``{"sub": str(user_id), "type": "access", "exp": ..., "iat": ...}`` (``core/rate_limit.py``
decodes this exact shape). Refresh tokens are opaque random strings; only their sha256 hex
digest is ever stored (``RefreshToken.token_hash``).
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings
from app.exceptions import UnauthorizedError

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - token type claim, not a secret

_SESSION_EXPIRED_MSG = "Session expire aayiduchu machan, thirumba login pannunga."


def create_access_token(user_id: int) -> str:
    """Create a signed access token for ``user_id``."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int:
    """Validate an access token and return its user id.

    Raises ``UnauthorizedError`` when the token is malformed, has a bad signature, is expired,
    is not an access token, or has a non-integer subject.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expired", _SESSION_EXPIRED_MSG) from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid token", _SESSION_EXPIRED_MSG) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type", _SESSION_EXPIRED_MSG)
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject", _SESSION_EXPIRED_MSG) from exc


def generate_refresh_token() -> str:
    """Return a new opaque, URL-safe refresh token (never stored in plain form)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Return the sha256 hex digest used to store/look up a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
