"""Movie Roast API entrypoint."""

import logging
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import settings
from app.core.rate_limit import limiter
from app.exceptions import AppError, RateLimitError
from app.logging_config import configure_logging
from app.routers import auth, movies, roasts

configure_logging("INFO" if settings.is_production else "DEBUG")
logger = logging.getLogger("app")

RATE_LIMIT_MESSAGE = "Konjam slow-a po machan! Roast oven cool aaganum."

app = FastAPI(
    title="Movie Roast API",
    version="2.0.0",
    description="Pick a movie, get a Tanglish roast.",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

# --- Rate limiting -----------------------------------------------------------------------------
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# --- CORS --------------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)


# --- Exception handlers ------------------------------------------------------------------------
def _error_body(detail: str, message: str | None) -> dict[str, Any]:
    return {"detail": detail, "message": message}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.status_code >= 500:
        logger.error(
            "%s %s -> %s: %s", request.method, request.url.path, exc.status_code, exc.detail
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.detail, exc.message),
        headers=headers or None,
    )


def _retry_after_seconds(request: Request, exc: RateLimitExceeded) -> int:
    """Seconds until the exhausted window resets (falls back to the window length)."""
    try:
        view_limit = request.state.view_rate_limit
        reset_at, _remaining = limiter.limiter.get_window_stats(view_limit[0], *view_limit[1])
        return max(1, int(reset_at - time.time()))
    except Exception:  # noqa: BLE001 - best effort; never fail the 429 response
        if exc.limit is None:
            return 60
        return max(1, int(exc.limit.limit.get_expiry()))


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = _retry_after_seconds(request, exc)
    logger.info("Rate limit hit on %s (%s)", request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content=_error_body(f"Rate limit exceeded: {exc.detail}", RATE_LIMIT_MESSAGE),
        headers={"Retry-After": str(retry_after)},
    )


# --- Routers -----------------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(movies.router)
app.include_router(roasts.router)


# --- Health ------------------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness + DB ping."""
    db_status = "ok"
    try:
        from app.database import SessionLocal  # lazy: owned by DATABASE-AGENT

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - report, don't crash the health check
        logger.exception("Health check DB ping failed")
        db_status = "error"
    return {"status": "ok", "database": db_status}
