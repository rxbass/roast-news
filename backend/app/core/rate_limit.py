"""Rate limiting helpers built on slowapi.

Usage in a router (Phase 2)::

    from fastapi import Request
    from app.core.rate_limit import check_daily_limit, dynamic_limit, limiter

    @router.post("")
    @limiter.limit(dynamic_limit)          # anon: RATE_LIMIT_ANON per IP, user: RATE_LIMIT_USER
    async def create_roast(request: Request, ...):  # `request: Request` param is REQUIRED
        check_daily_limit()                # global DAILY_ROAST_LIMIT (raises RateLimitError)
        ...

The default ``key_func`` (``rate_limit_key``) returns ``"user:<id>"`` when the request carries a
valid access-token bearer header and ``"ip:<client ip>"`` otherwise. ``dynamic_limit`` receives
that key and picks the matching limit string.

NOTE (MVP): slowapi uses in-memory storage and ``check_daily_limit`` is an in-process counter.
Both are per-process: with several uvicorn workers/replicas the effective limits multiply and the
counters reset on restart. Move to Redis (``storage_uri="redis://..."``) before scaling out.
"""

import logging
import threading
from datetime import UTC, date, datetime, timedelta

import jwt
from fastapi import Request
from slowapi import Limiter

from app.config import settings
from app.exceptions import RateLimitError

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Client IP for rate limiting and ``client_ip_hash``.

    X-Forwarded-For is client-controlled, so it is ignored unless ``TRUSTED_PROXY_COUNT`` > 0.
    With N trusted proxies in front, the real client is the Nth address from the *right* (each
    proxy appends the peer it saw); anything further left could have been forged by the client.
    """
    if settings.TRUSTED_PROXY_COUNT > 0:
        hops = [
            h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()
        ]
        if len(hops) >= settings.TRUSTED_PROXY_COUNT:
            return hops[-settings.TRUSTED_PROXY_COUNT]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def get_user_id_from_request(request: Request) -> str | None:
    """Return the ``sub`` of a valid *access* bearer token, or None.

    Never raises: invalid/expired tokens simply fall back to IP-based limiting. The auth
    dependencies (Phase 2) are responsible for rejecting bad tokens with 401.
    """
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = jwt.decode(token.strip(), settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access" or payload.get("sub") is None:
        return None
    return str(payload["sub"])


def rate_limit_key(request: Request) -> str:
    """slowapi key function: ``user:<id>`` for signed-in users, ``ip:<ip>`` otherwise."""
    user_id = get_user_id_from_request(request)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_client_ip(request)}"


def dynamic_limit(key: str) -> str:
    """slowapi limit provider: choose the limit string based on the key from ``rate_limit_key``."""
    if key.startswith("user:"):
        return settings.RATE_LIMIT_USER
    return settings.RATE_LIMIT_ANON


limiter = Limiter(key_func=rate_limit_key, headers_enabled=False)


# --------------------------------------------------------------------------------------------
# Global daily cap (in-process, MVP only - see module docstring)
# --------------------------------------------------------------------------------------------

_daily_lock = threading.Lock()


class _DailyCounter:
    def __init__(self) -> None:
        self.day: date = datetime.now(UTC).date()
        self.count: int = 0


_daily = _DailyCounter()


def _seconds_until_utc_midnight(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def check_daily_limit(increment: bool = True) -> int:
    """Enforce ``DAILY_ROAST_LIMIT`` across all users for the current UTC day.

    Increments the counter (unless ``increment=False``) and returns the new count.
    Raises ``RateLimitError`` (429, Retry-After = seconds until UTC midnight) when exhausted.
    """
    now = datetime.now(UTC)
    with _daily_lock:
        if _daily.day != now.date():
            _daily.day = now.date()
            _daily.count = 0
        count = _daily.count
        if count >= settings.DAILY_ROAST_LIMIT:
            logger.warning("Global daily roast limit reached (%s)", settings.DAILY_ROAST_LIMIT)
            raise RateLimitError(
                detail="Daily roast limit reached",
                message="Inniki roast quota full machan! Naalaikku vaanga.",
                retry_after=_seconds_until_utc_midnight(now),
            )
        if increment:
            count += 1
            _daily.count = count
        return count


def reset_daily_limit() -> None:
    """Reset the in-process daily counter (used by tests)."""
    with _daily_lock:
        _daily.day = datetime.now(UTC).date()
        _daily.count = 0
