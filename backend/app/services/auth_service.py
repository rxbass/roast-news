"""Auth business logic: Google user upsert, token issuance, refresh rotation, logout."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.google import GoogleUserInfo
from app.auth.jwt import create_access_token, generate_refresh_token, hash_token
from app.config import settings
from app.exceptions import UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair

logger = logging.getLogger(__name__)

_REFRESH_INVALID_MESSAGE = "Session expire aayiduchu machan, thirumba login pannunga."


class InactiveUserError(Exception):
    """Raised when a disabled account tries to sign in."""


def _now() -> datetime:
    return datetime.now(UTC)


def get_active_user(db: Session, user_id: int) -> User | None:
    """Return the user with ``user_id`` if it exists and is active, else ``None``."""
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def upsert_google_user(db: Session, info: GoogleUserInfo) -> User:
    """Create or update the user for a verified Google profile and commit.

    Lookup order: by ``google_id``; otherwise by email (case-insensitive), in which case the
    existing account is linked to this Google id. Profile fields are refreshed on every login.
    Raises ``InactiveUserError`` if the matched account is disabled.
    """
    user = db.scalar(select(User).where(User.google_id == info.google_id))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == info.email.lower()))
        if user is not None:
            logger.info("Linking existing user id=%s to a Google account", user.id)
            user.google_id = info.google_id

    if user is None:
        user = User(
            email=info.email,
            google_id=info.google_id,
            full_name=info.full_name,
            avatar_url=info.avatar_url,
        )
        db.add(user)
    else:
        if not user.is_active:
            db.rollback()
            raise InactiveUserError()
        user.email = info.email
        user.full_name = info.full_name
        user.avatar_url = info.avatar_url

    db.commit()
    db.refresh(user)
    return user


def issue_token_pair(db: Session, user: User) -> TokenPair:
    """Mint a new access token and persist a new (hashed) refresh token for ``user``."""
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=raw_refresh)


def revoke_all_user_tokens(db: Session, user_id: int) -> int:
    """Revoke every active refresh token of ``user_id`` (no commit). Returns rows affected."""
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def rotate_refresh_token(db: Session, raw_token: str) -> TokenPair:
    """Exchange a refresh token for a new pair (the old token is revoked).

    Raises ``UnauthorizedError`` when the token is unknown, expired, revoked, or its user is
    missing/inactive. Presenting an already-revoked token is treated as theft: every active
    refresh token of that user is revoked as well (reuse detection).
    """
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None:
        raise UnauthorizedError("Invalid refresh token", _REFRESH_INVALID_MESSAGE)

    if token.revoked:
        revoked = revoke_all_user_tokens(db, token.user_id)
        db.commit()
        logger.warning(
            "Refresh token reuse detected for user id=%s; revoked %s active token(s)",
            token.user_id,
            revoked,
        )
        raise UnauthorizedError("Refresh token reused", _REFRESH_INVALID_MESSAGE)

    if token.expires_at <= _now():
        db.rollback()
        raise UnauthorizedError("Refresh token expired", _REFRESH_INVALID_MESSAGE)

    user = get_active_user(db, token.user_id)
    if user is None:
        token.revoked = True
        db.commit()
        raise UnauthorizedError("User not found or inactive", _REFRESH_INVALID_MESSAGE)

    token.revoked = True
    return issue_token_pair(db, user)  # commits the revocation and the new token together


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """Revoke ``raw_token`` if it exists. Silent either way (no existence leak)."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(raw_token),
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    db.commit()
