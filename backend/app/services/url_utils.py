"""URL helpers: normalization (for cache keys), hashing, and domain extraction."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Exact query-param names that only track the visitor and never change the article.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "gbraid",
        "wbraid",
        "msclkid",
        "yclid",
        "twclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "ref_url",
        "referrer",
        "cmpid",
        "_ga",
        "_gl",
        "spm",
        "share",
        "s_cid",
        "ocid",
        "smid",
        "si",
    }
)
# Prefixes of tracking params (utm_source, utm_medium, ...).
_TRACKING_PREFIXES: tuple[str, ...] = ("utm_", "hsa_", "pk_", "mtm_")

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


def _is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    return lowered in _TRACKING_PARAMS or lowered.startswith(_TRACKING_PREFIXES)


def normalize_url(url: str) -> str:
    """Return a canonical form of ``url`` so equivalent links share a cache key.

    - lowercases scheme and host, drops userinfo, fragment and default ports
    - removes tracking params (``utm_*``, ``fbclid``, ``gclid``, ``ref``, ...)
    - sorts the remaining query params
    - strips a trailing slash from the path (except the root path ``/``)
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if ":" in host:  # IPv6 literal needs brackets back
        host = f"[{host}]"

    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host
    if port is not None and port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query_items.sort()
    query = urlencode(query_items, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(normalized: str) -> str:
    """Return the sha256 hex digest of an already-normalized URL."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    """Return the lowercase host of ``url`` without a leading ``www.``."""
    host = (urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def redact_url(url: str) -> str:
    """Return ``scheme://host/path`` only (no query/fragment) - safe to log at INFO."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.hostname or "", parts.path, "", ""))
