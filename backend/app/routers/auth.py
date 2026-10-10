"""Auth router: Google OAuth sign-in, token refresh/logout, and the current user."""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import google
from app.auth.dependencies import get_current_user
from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.exceptions import AppError
from app.models.user import User
from app.schemas.auth import LogoutRequest, RefreshRequest, TokenPair
from app.schemas.user import UserResponse
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

AUTH_ROUTE_LIMIT = "30/minute"
# crypto.randomUUID() from the SPA (36 chars) or any similar URL-safe random token.
NONCE_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"


def _frontend_redirect(fragment: dict[str, str]) -> RedirectResponse:
    """302 to the SPA callback page with ``fragment`` in the URL hash; clears the state cookie."""
    url = f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback#{urlencode(fragment)}"
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(
        google.STATE_COOKIE_NAME,
        path=google.STATE_COOKIE_PATH,
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
    return response


def _error_redirect(code: str) -> RedirectResponse:
    return _frontend_redirect({"error": code})


@router.get("/google", status_code=status.HTTP_302_FOUND)
async def google_login(
    nonce: str = Query(..., pattern=NONCE_PATTERN, description="Random value kept by the SPA"),
) -> RedirectResponse:
    """Start Google sign-in: set a signed ``oauth_state`` cookie and redirect to Google."""
    if not google.is_configured():
        raise AppError(
            status_code=503,
            detail="Google OAuth not configured",
            message="Google login innum setup aagala machan.",
        )
    state = google.generate_state()
    response = RedirectResponse(
        google.build_authorization_url(state), status_code=status.HTTP_302_FOUND
    )
    response.set_cookie(
        google.STATE_COOKIE_NAME,
        google.sign_state(state, nonce),
        max_age=google.STATE_COOKIE_MAX_AGE,
        path=google.STATE_COOKIE_PATH,
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
@limiter.limit(AUTH_ROUTE_LIMIT)
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Finish Google sign-in and redirect to the SPA with tokens (or an error) in the hash."""
    nonce = google.verify_state(request.cookies.get(google.STATE_COOKIE_NAME), state)
    if nonce is None:
        logger.info("OAuth callback rejected: state mismatch")
        return _error_redirect("state_mismatch")
    if error:
        logger.info("OAuth callback returned Google error: %s", error[:64])
        return _error_redirect("access_denied" if error == "access_denied" else "oauth_failed")
    if not code or not google.is_configured():
        return _error_redirect("oauth_failed")

    try:
        google_token = await google.exchange_code_for_access_token(code)
        info = await google.fetch_user_info(google_token)
    except google.GoogleOAuthError:
        return _error_redirect("oauth_failed")

    if not info.email_verified:
        logger.info("OAuth callback rejected: unverified Google email")
        return _error_redirect("email_unverified")

    try:
        user = auth_service.upsert_google_user(db, info)
        tokens = auth_service.issue_token_pair(db, user)
    except auth_service.InactiveUserError:
        logger.info("OAuth callback rejected: inactive account")
        return _error_redirect("account_disabled")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("OAuth callback failed while saving the user")
        return _error_redirect("oauth_failed")

    logger.info("User id=%s signed in with Google", user.id)
    return _frontend_redirect({**tokens.model_dump(), "nonce": nonce})


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(AUTH_ROUTE_LIMIT)
def refresh_tokens(
    request: Request, body: RefreshRequest, db: Session = Depends(get_db)
) -> TokenPair:
    """Rotate a refresh token: revoke the presented one and return a fresh pair."""
    return auth_service.rotate_refresh_token(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    """Revoke a refresh token. Always 204, whether or not the token existed."""
    auth_service.revoke_refresh_token(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user's profile."""
    return user
