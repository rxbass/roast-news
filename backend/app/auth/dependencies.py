"""FastAPI auth dependencies.

- ``get_current_user``: requires a valid bearer access token (401 otherwise).
- ``get_optional_user``: ``None`` when no Authorization header is sent; 401 when a token *is*
  sent but is invalid/expired, so the frontend knows to refresh and retry.

Both are plain ``def``: they query the DB synchronously, so FastAPI runs them in its threadpool.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.user import User
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def _resolve_user(credentials: HTTPAuthorizationCredentials, db: Session) -> User:
    user_id = decode_access_token(credentials.credentials)
    user = auth_service.get_active_user(db, user_id)
    if user is None:
        raise UnauthorizedError("User not found or inactive")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user or raise ``UnauthorizedError`` (401)."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()
    return _resolve_user(credentials, db)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user, ``None`` for anonymous requests, 401 for bad tokens."""
    if credentials is None or not credentials.credentials:
        return None
    return _resolve_user(credentials, db)
