"""SSRF-safe article fetching and extraction.

Every hop (the submitted URL and each redirect target) goes through ``validate_target``:

- scheme ``http``/``https`` only, no ``user:pass@``, port 80/443/none only
- the hostname is resolved with ``asyncio`` ``getaddrinfo``; if ANY resolved address is not a
  public unicast address (private, loopback, link-local, multicast, reserved, unspecified,
  site-local, shared/CGNAT, IPv4-mapped/6to4/Teredo forms of those, cloud metadata) -> blocked

The connection is then **pinned** to the vetted IP: we request the IP-literal URL, send the real
hostname in the ``Host`` header and, for https, pass ``sni_hostname`` so TLS SNI and certificate
verification still use the real hostname. A second DNS lookup by the HTTP client never happens,
so DNS rebinding between the check and the connect is not possible.

Redirects are followed manually (max 3), re-validating each hop. The body is streamed and aborted
past 2 MB; only HTML content types are accepted. Extraction uses trafilatura in a worker thread.
"""

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from app.exceptions import BadRequestError, UnprocessableError, UpstreamError
from app.services.url_utils import extract_domain, redact_url

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10.0
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5  # shortener chains: t.co -> bit.ly -> http->https -> www
EXTRACT_TIMEOUT_SECONDS = 5.0
MIN_ARTICLE_CHARS = 200
MAX_TITLE_CHARS = 500

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({None, 80, 443})
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

BLOCKED_HOSTNAMES = frozenset(
    {"localhost", "metadata", "metadata.google.internal", "metadata.goog", "instance-data"}
)
METADATA_IPS = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS / GCP / Azure / OpenStack
        ipaddress.ip_address("169.254.170.2"),  # AWS ECS task metadata
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
        ipaddress.ip_address("fd00:ec2::254"),  # AWS IMDS over IPv6
    }
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
_REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
    "Accept-Language": "en-IN,en;q=0.9,ta;q=0.8",
    # No gzip/deflate: httpx decompresses whole network chunks before our size check, so a
    # small compressed "bomb" could expand far past MAX_BODY_BYTES in memory.
    "Accept-Encoding": "identity",
}

# Video / social links extract to junk; tell the user to paste a news article instead.
NON_ARTICLE_HOSTS = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "x.com",
        "twitter.com",
        "t.co",
        "instagram.com",
        "facebook.com",
        "fb.watch",
        "threads.net",
        "news.google.com",
    }
)
BOT_BLOCK_STATUSES = frozenset({401, 403, 429, 451})

INVALID_URL_MESSAGE = "Indha link sari illa machan."
FETCH_FAILED_MESSAGE = "Andha site-ae open aagala machan. Konjam kazhichu try pannunga."
NO_ARTICLE_MESSAGE = "Article-ae kaanom! Vera link kudu machan."
NON_ARTICLE_MESSAGE = (
    "News article link kudu machan, video/tweet illa! (Original article link paste pannunga.)"
)
BOT_BLOCKED_MESSAGE = (
    "Indha site bots-a ulla vida maatengudhu machan. Vera news site link try pannu!"
)

_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass(frozen=True)
class Article:
    """Extracted article content."""

    title: str
    text: str
    domain: str
    final_url: str


@dataclass(frozen=True)
class _Target:
    """A URL that passed the SSRF guard, plus the IP it must be fetched from."""

    url: str
    scheme: str
    host: str
    ip: IPAddress


def _blocked(detail: str) -> BadRequestError:
    return BadRequestError(detail=detail, message=INVALID_URL_MESSAGE)


def is_ip_allowed(ip: IPAddress) -> bool:
    """Return True only for public unicast addresses that are safe to connect to."""
    if ip in METADATA_IPS:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Check the embedded IPv4 address of mapped / 6to4 / Teredo forms too.
        embedded: list[ipaddress.IPv4Address] = []
        if ip.ipv4_mapped is not None:
            embedded.append(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            embedded.append(ip.sixtofour)
        if ip.teredo is not None:
            embedded.extend(ip.teredo)
        if any(not is_ip_allowed(inner) for inner in embedded):
            return False
        if ip.is_site_local:
            return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


async def _resolve(host: str, port: int) -> list[IPAddress]:
    """Resolve ``host`` to all of its addresses (A + AAAA)."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        logger.debug("Resolution failed for %s: %s", host, exc)
        raise _blocked("Could not resolve host") from exc
    addresses: list[IPAddress] = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        raw = str(sockaddr[0]).split("%", 1)[0]  # drop IPv6 zone id
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise _blocked("Resolver returned an invalid address") from exc
        if addr not in addresses:
            addresses.append(addr)
    if not addresses:
        raise _blocked("Host did not resolve to any address")
    return addresses


async def validate_target(url: str) -> _Target:
    """Run the SSRF guard on ``url``; raise ``BadRequestError`` if it must not be fetched."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise _blocked("Malformed URL") from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise _blocked(f"Scheme not allowed: {scheme or '(none)'}")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise _blocked("Credentials in URL are not allowed")
    if port not in ALLOWED_PORTS:
        raise _blocked(f"Port not allowed: {port}")

    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise _blocked("URL has no host")
    if host in BLOCKED_HOSTNAMES or host.endswith((".localhost", ".internal", ".local")):
        raise _blocked("Host not allowed")

    try:
        literal: IPAddress | None = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    addresses = [literal] if literal is not None else await _resolve(host, port or 443)
    for addr in addresses:
        if not is_ip_allowed(addr):
            # Don't echo the address: it would map internal names to IPs for an attacker.
            logger.debug("Blocked %s: resolves to non-public %s", host, addr)
            raise _blocked("URL not allowed")

    # Prefer IPv4: containers often have no IPv6 route even when the site publishes AAAA.
    pinned = sorted(addresses, key=lambda a: a.version)[0]
    return _Target(url=url.strip(), scheme=scheme, host=host, ip=pinned)


def _pinned_request(client: httpx.AsyncClient, target: _Target) -> httpx.Request:
    """Build a request that connects to the vetted IP while keeping Host / SNI = hostname."""
    pinned_url = httpx.URL(target.url).copy_with(host=str(target.ip))
    extensions: dict[str, str] = {}
    if target.scheme == "https":
        # httpcore uses this for TLS SNI *and* certificate hostname verification.
        extensions["sni_hostname"] = target.host
    headers = {**_REQUEST_HEADERS, "Host": target.host}
    return client.build_request("GET", pinned_url, headers=headers, extensions=extensions)


async def _read_limited(response: httpx.Response) -> bytes:
    """Read the streamed body, aborting once it exceeds ``MAX_BODY_BYTES``."""
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise UnprocessableError(detail="Response too large", message=NO_ARTICLE_MESSAGE)
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise UnprocessableError(detail="Response too large", message=NO_ARTICLE_MESSAGE)
        chunks.append(chunk)
    return b"".join(chunks)


async def _download(url: str) -> tuple[bytes, str]:
    """Fetch ``url`` with SSRF checks on every hop; return (html bytes, final url)."""
    current = url
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,  # never route through env proxies (would bypass IP pinning)
    ) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            target = await validate_target(current)
            request = _pinned_request(client, target)
            response = await client.send(request, stream=True)
            try:
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise UpstreamError(
                            detail="Redirect without Location", message=FETCH_FAILED_MESSAGE
                        )
                    current = urljoin(target.url, location)
                    logger.debug("Following redirect to %s", redact_url(current))
                    continue
                if response.status_code in BOT_BLOCK_STATUSES:
                    raise UnprocessableError(
                        detail=f"Source site refused the fetch (HTTP {response.status_code})",
                        message=BOT_BLOCKED_MESSAGE,
                    )
                if not response.is_success:
                    raise UpstreamError(
                        detail=f"Source site returned HTTP {response.status_code}",
                        message=FETCH_FAILED_MESSAGE,
                    )
                content_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise UnprocessableError(
                        detail=f"Unsupported content type: {content_type or '(none)'}",
                        message=NO_ARTICLE_MESSAGE,
                    )
                body = await _read_limited(response)
                return body, target.url
            finally:
                await response.aclose()
    raise UpstreamError(detail="Too many redirects", message=FETCH_FAILED_MESSAGE)


def _fallback_title(html: bytes) -> str:
    match = _TITLE_RE.search(html)
    if not match:
        return ""
    raw = match.group(1).decode("utf-8", errors="ignore")
    return " ".join(raw.split())


def _extract(html: bytes, url: str) -> tuple[str, str]:
    """Blocking trafilatura extraction -> (title, text). Run in a worker thread."""
    doc = trafilatura.bare_extraction(
        html,
        url=url,
        with_metadata=True,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    text = ""
    title = ""
    if doc is not None and not isinstance(doc, dict):
        text = (doc.text or "").strip()
        title = (doc.title or "").strip()
    if not title:
        title = _fallback_title(html)
    return title, text


async def fetch_article(url: str) -> Article:
    """Safely fetch ``url`` and extract its article.

    Raises:
        BadRequestError: invalid or blocked URL (400).
        UpstreamError: network failure, timeout, non-2xx, too many redirects (502).
        UnprocessableError: non-HTML, oversized, or no usable article text (422).
    """
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host in NON_ARTICLE_HOSTS:
        raise UnprocessableError(
            detail=f"Not a news article host: {host}", message=NON_ARTICLE_MESSAGE
        )

    try:
        async with asyncio.timeout(FETCH_TIMEOUT_SECONDS):
            html, final_url = await _download(url)
    except TimeoutError as exc:
        raise UpstreamError(detail="Source site timed out", message=FETCH_FAILED_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.info("Fetch failed for %s: %s", redact_url(url), type(exc).__name__)
        raise UpstreamError(
            detail=f"Could not fetch source: {type(exc).__name__}", message=FETCH_FAILED_MESSAGE
        ) from exc

    try:
        # The worker thread can't be cancelled, but the request stops waiting on pathological HTML.
        async with asyncio.timeout(EXTRACT_TIMEOUT_SECONDS):
            title, text = await asyncio.to_thread(_extract, html, final_url)
    except TimeoutError as exc:
        logger.warning("Extraction timed out for %s", redact_url(final_url))
        raise UnprocessableError(detail="Extraction timed out", message=NO_ARTICLE_MESSAGE) from exc
    except Exception as exc:  # noqa: BLE001 - parser failures mean "no article"
        logger.warning("Extraction crashed for %s: %s", redact_url(final_url), exc)
        raise UnprocessableError(detail="Extraction failed", message=NO_ARTICLE_MESSAGE) from exc

    if len(text) < MIN_ARTICLE_CHARS:
        raise UnprocessableError(detail="No usable article text found", message=NO_ARTICLE_MESSAGE)

    domain = extract_domain(final_url)
    title = (title or domain)[:MAX_TITLE_CHARS]
    logger.info("Extracted article from %s (%d chars)", domain, len(text))
    return Article(title=title, text=text, domain=domain, final_url=final_url)
