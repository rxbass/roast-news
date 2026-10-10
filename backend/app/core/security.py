"""Small security helpers shared across modules."""

import hashlib

from app.config import settings


def hash_ip(ip: str) -> str:
    """Return a salted sha256 hex digest of an IP so raw IPs are never stored."""
    return hashlib.sha256((settings.IP_HASH_SALT + ip).encode("utf-8")).hexdigest()
