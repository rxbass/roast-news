"""SSRF guard, download limits and extraction in ``scraper_service`` (network fully mocked)."""

import ipaddress
import socket
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx

from app.exceptions import BadRequestError, UnprocessableError, UpstreamError
from app.services import scraper_service
from app.services.scraper_service import fetch_article, is_ip_allowed, validate_target

PUBLIC_IP = "93.184.215.14"
PUBLIC_IP_2 = "93.184.215.15"

PARAGRAPH = (
    "The city corporation announced on Monday that it will hold another meeting about the "
    "long pending road repair project in the neighbourhood near the old bus stand."
)
ARTICLE_HTML = f"""<!doctype html>
<html><head><title>Fallback | Example News</title>
<meta property="og:title" content="Road repair meeting announced"></head>
<body><nav>Home | News | Sports</nav>
<article><h1>Road repair meeting announced</h1>
<p>{PARAGRAPH}</p>
<p>Residents said they had heard the same promise many times before and were not impressed.
Officials insisted that this time the funds have been sanctioned and work will begin soon.</p>
</article><footer>Copyright Example News</footer></body></html>""".encode()

SHORT_HTML = b"<html><head><title>Tiny</title></head><body><p>Too short.</p></body></html>"


class FakeResolver:
    """Replacement for ``socket.getaddrinfo`` driven by a hostname -> IPs table."""

    def __init__(self) -> None:
        self.table: dict[str, list[str]] = {}
        self.calls: list[str] = []

    def __call__(self, host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        name = host.decode() if isinstance(host, bytes) else str(host)
        self.calls.append(name)
        if name not in self.table:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        infos: list[Any] = []
        for ip in self.table[name]:
            if ipaddress.ip_address(ip.split("%")[0]).version == 6:
                infos.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, port, 0, 0)))
            else:
                infos.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)))
        return infos


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver()
    fake.table["news.example.com"] = [PUBLIC_IP]
    fake.table["www.news.example.com"] = [PUBLIC_IP]
    fake.table["other.example.org"] = [PUBLIC_IP_2]
    monkeypatch.setattr(socket, "getaddrinfo", fake)
    return fake


@pytest.fixture
def mock_http() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def html_response(body: bytes = ARTICLE_HTML) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "text/html; charset=utf-8"})


# --- is_ip_allowed -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.5.4",
        "192.168.1.1",
        "169.254.169.254",
        "169.254.170.2",
        "100.100.100.200",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fec0::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
        "2001:0:4136:e378:8000:63bf:f5ff:fffe",  # Teredo
    ],
)
def test_is_ip_allowed_blocks_non_public(ip: str) -> None:
    assert is_ip_allowed(ipaddress.ip_address(ip)) is False


@pytest.mark.parametrize("ip", [PUBLIC_IP, "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"])
def test_is_ip_allowed_accepts_public(ip: str) -> None:
    assert is_ip_allowed(ipaddress.ip_address(ip)) is True


# --- validate_target ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://news.example.com/file",
        "gopher://news.example.com/",
        "news.example.com/no-scheme",
        "http://127.0.0.1/",
        "http://10.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:a9fe:a9fe]/",
        "http://0.0.0.0/",
        "http://localhost/",
        "http://LOCALHOST./",
        "http://api.localhost/",
        "http://metadata.google.internal/",
        "http://printer.local/",
        "http://user:pw@news.example.com/",
        "http://user@news.example.com/",
        "http://news.example.com:8080/",
        "https://news.example.com:22/",
        "http://[::1/",
        "http:///path-only",
        "http://unknown-host.invalid/",
    ],
)
async def test_validate_target_blocks(url: str, resolver: FakeResolver) -> None:
    with pytest.raises(BadRequestError) as exc_info:
        await validate_target(url)
    assert exc_info.value.status_code == 400


async def test_hostname_resolving_to_private_ip_is_blocked(resolver: FakeResolver) -> None:
    resolver.table["evil.example.com"] = ["10.1.2.3"]
    with pytest.raises(BadRequestError, match="URL not allowed"):
        await validate_target("https://evil.example.com/story")
    assert "evil.example.com" in resolver.calls


async def test_mixed_public_and_private_resolution_is_blocked(resolver: FakeResolver) -> None:
    resolver.table["mixed.example.com"] = [PUBLIC_IP, "192.168.0.10"]
    with pytest.raises(BadRequestError, match="URL not allowed"):
        await validate_target("https://mixed.example.com/story")


async def test_ipv6_duplicates_and_zone_ids(resolver: FakeResolver) -> None:
    resolver.table["v6.example.com"] = ["2606:4700:4700::1111", "2606:4700:4700::1111"]
    target = await validate_target("https://v6.example.com/")
    assert str(target.ip) == "2606:4700:4700::1111"
    resolver.table["zone.example.com"] = ["fe80::1%eth0"]
    with pytest.raises(BadRequestError):
        await validate_target("https://zone.example.com/")


async def test_resolver_returning_garbage_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def garbage(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", port))]

    monkeypatch.setattr(socket, "getaddrinfo", garbage)
    with pytest.raises(BadRequestError, match="invalid address"):
        await validate_target("https://news.example.com/")


async def test_resolver_returning_nothing_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [])
    with pytest.raises(BadRequestError, match="did not resolve"):
        await validate_target("https://news.example.com/")


async def test_validate_target_accepts_public_host(resolver: FakeResolver) -> None:
    target = await validate_target("  HTTPS://News.Example.com/story  ")
    assert target.host == "news.example.com"
    assert target.scheme == "https"
    assert str(target.ip) == PUBLIC_IP
    assert target.url == "HTTPS://News.Example.com/story"


async def test_public_ip_literal_skips_dns(resolver: FakeResolver) -> None:
    target = await validate_target(f"http://{PUBLIC_IP}/x")
    assert str(target.ip) == PUBLIC_IP
    assert resolver.calls == []


# --- fetch_article -----------------------------------------------------------------------------
async def test_fetch_article_happy_path_pins_ip(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"http://{PUBLIC_IP}/story").mock(return_value=html_response())
    article = await fetch_article("http://www.news.example.com/story")

    assert article.title == "Road repair meeting announced"
    assert "road repair project" in article.text
    assert len(article.text) >= scraper_service.MIN_ARTICLE_CHARS
    assert article.domain == "news.example.com"
    assert article.final_url == "http://www.news.example.com/story"
    sent = route.calls.last.request
    assert sent.headers["host"] == "www.news.example.com"
    assert "Mozilla" in sent.headers["user-agent"]


async def test_fetch_article_https_sets_sni(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"https://{PUBLIC_IP}/story").mock(return_value=html_response())
    article = await fetch_article("https://news.example.com/story")
    assert article.domain == "news.example.com"
    assert route.calls.last.request.extensions["sni_hostname"] == "news.example.com"


async def test_fetch_article_follows_safe_redirect(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/short").mock(
        return_value=httpx.Response(301, headers={"location": "http://other.example.org/full"})
    )
    mock_http.get(f"http://{PUBLIC_IP_2}/full").mock(return_value=html_response())
    article = await fetch_article("http://news.example.com/short")
    assert article.domain == "other.example.org"
    assert article.final_url == "http://other.example.org/full"


async def test_redirect_to_private_ip_is_blocked(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/go").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
    )
    internal = mock_http.get("http://169.254.169.254/latest").mock(return_value=html_response())
    with pytest.raises(BadRequestError):
        await fetch_article("http://news.example.com/go")
    assert not internal.called


async def test_redirect_to_host_resolving_private_is_blocked(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    resolver.table["rebind.example.com"] = ["127.0.0.1"]
    mock_http.get(f"http://{PUBLIC_IP}/go").mock(
        return_value=httpx.Response(307, headers={"location": "http://rebind.example.com/"})
    )
    with pytest.raises(BadRequestError):
        await fetch_article("http://news.example.com/go")


async def test_too_many_redirects(resolver: FakeResolver, mock_http: respx.MockRouter) -> None:
    for i in range(6):
        mock_http.get(f"http://{PUBLIC_IP}/r{i}").mock(
            return_value=httpx.Response(302, headers={"location": f"/r{i + 1}"})
        )
    with pytest.raises(UpstreamError, match="Too many redirects") as exc_info:
        await fetch_article("http://news.example.com/r0")
    assert exc_info.value.status_code == 502


async def test_three_redirects_are_allowed(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    for i in range(3):
        mock_http.get(f"http://{PUBLIC_IP}/r{i}").mock(
            return_value=httpx.Response(302, headers={"location": f"/r{i + 1}"})
        )
    mock_http.get(f"http://{PUBLIC_IP}/r3").mock(return_value=html_response())
    article = await fetch_article("http://news.example.com/r0")
    assert article.final_url == "http://news.example.com/r3"


async def test_redirect_without_location(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/x").mock(return_value=httpx.Response(302))
    with pytest.raises(UpstreamError, match="without Location"):
        await fetch_article("http://news.example.com/x")


@pytest.mark.parametrize(
    "content_type", ["application/pdf", "application/json", "image/png", "", "text/plain"]
)
async def test_non_html_content_is_rejected(
    content_type: str, resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/doc").mock(
        return_value=httpx.Response(
            200, content=b"%PDF-1.4", headers={"content-type": content_type}
        )
    )
    with pytest.raises(UnprocessableError, match="Unsupported content type") as exc_info:
        await fetch_article("http://news.example.com/doc")
    assert exc_info.value.status_code == 422


async def test_xhtml_content_type_is_accepted(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/x").mock(
        return_value=httpx.Response(
            200, content=ARTICLE_HTML, headers={"content-type": "application/xhtml+xml"}
        )
    )
    article = await fetch_article("http://news.example.com/x")
    assert article.title


async def test_oversize_declared_body_is_rejected(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    big = b"<html>" + b"a" * (scraper_service.MAX_BODY_BYTES + 10)
    mock_http.get(f"http://{PUBLIC_IP}/big").mock(return_value=html_response(big))
    with pytest.raises(UnprocessableError, match="too large"):
        await fetch_article("http://news.example.com/big")


class _Chunks(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(5):
            yield b"x" * 400


async def test_oversize_streamed_body_without_length_is_rejected(
    resolver: FakeResolver, mock_http: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scraper_service, "MAX_BODY_BYTES", 1000)
    mock_http.get(f"http://{PUBLIC_IP}/stream").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, stream=_Chunks())
    )
    with pytest.raises(UnprocessableError, match="too large"):
        await fetch_article("http://news.example.com/stream")


async def test_too_short_article_is_422(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/tiny").mock(return_value=html_response(SHORT_HTML))
    with pytest.raises(UnprocessableError, match="No usable article") as exc_info:
        await fetch_article("http://news.example.com/tiny")
    assert exc_info.value.status_code == 422


async def test_http_500_is_502(resolver: FakeResolver, mock_http: respx.MockRouter) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/err").mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamError, match="HTTP 500") as exc_info:
        await fetch_article("http://news.example.com/err")
    assert exc_info.value.status_code == 502


async def test_http_404_is_502(resolver: FakeResolver, mock_http: respx.MockRouter) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/gone").mock(return_value=httpx.Response(404))
    with pytest.raises(UpstreamError):
        await fetch_article("http://news.example.com/gone")


async def test_network_error_is_502(resolver: FakeResolver, mock_http: respx.MockRouter) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/down").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamError, match="ConnectError"):
        await fetch_article("http://news.example.com/down")


async def test_timeout_is_502(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(url: str) -> tuple[bytes, str]:
        raise TimeoutError

    monkeypatch.setattr(scraper_service, "_download", slow)
    with pytest.raises(UpstreamError, match="timed out"):
        await fetch_article("http://news.example.com/slow")


async def test_extraction_crash_is_422(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_download(url: str) -> tuple[bytes, str]:
        return ARTICLE_HTML, url

    def boom(html: bytes, url: str) -> tuple[str, str]:
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(scraper_service, "_download", fake_download)
    monkeypatch.setattr(scraper_service, "_extract", boom)
    with pytest.raises(UnprocessableError, match="Extraction failed"):
        await fetch_article("http://news.example.com/x")


async def test_missing_title_falls_back_to_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_download(url: str) -> tuple[bytes, str]:
        return b"", url

    monkeypatch.setattr(scraper_service, "_download", fake_download)
    monkeypatch.setattr(scraper_service, "_extract", lambda html, url: ("", PARAGRAPH * 2))
    article = await fetch_article("http://news.example.com/x")
    assert article.title == "news.example.com"


def test_fallback_title_from_title_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraper_service.trafilatura, "bare_extraction", lambda *a, **k: None)
    title, text = scraper_service._extract(
        b"<html><head><title>\n  Spaced   Title </title></head></html>", "http://x.com/"
    )
    assert title == "Spaced Title"
    assert text == ""
    assert scraper_service._fallback_title(b"<html>no title</html>") == ""


# --- hardening: bot blocks, non-article hosts, IPv4 preference, extraction timeout -------------
@pytest.mark.parametrize("status", [401, 403, 429, 451])
async def test_bot_blocking_sites_get_a_specific_422(
    resolver: FakeResolver, mock_http: respx.MockRouter, status: int
) -> None:
    mock_http.get(f"http://{PUBLIC_IP}/story").mock(return_value=httpx.Response(status))
    with pytest.raises(UnprocessableError) as exc:
        await fetch_article("http://news.example.com/story")
    assert exc.value.message == scraper_service.BOT_BLOCKED_MESSAGE


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://x.com/someone/status/1",
        "https://m.facebook.com/story",
        "https://news.google.com/rss/articles/abc",
    ],
)
async def test_social_and_video_links_are_rejected_without_fetching(
    url: str, mock_http: respx.MockRouter
) -> None:
    with pytest.raises(UnprocessableError) as exc:
        await fetch_article(url)
    assert exc.value.message == scraper_service.NON_ARTICLE_MESSAGE
    assert not mock_http.calls


async def test_ipv4_is_preferred_over_ipv6(resolver: FakeResolver) -> None:
    resolver.table["dual.example.com"] = ["2606:4700:4700::1111", PUBLIC_IP]
    target = await validate_target("http://dual.example.com/x")
    assert str(target.ip) == PUBLIC_IP


async def test_slow_extraction_times_out(
    resolver: FakeResolver, mock_http: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    def slow_extract(html: bytes, url: str) -> tuple[str, str]:
        time.sleep(0.3)
        return "t", "x" * 500

    mock_http.get(f"http://{PUBLIC_IP}/story").mock(return_value=html_response())
    monkeypatch.setattr(scraper_service, "_extract", slow_extract)
    monkeypatch.setattr(scraper_service, "EXTRACT_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(UnprocessableError, match="Extraction timed out"):
        await fetch_article("http://news.example.com/story")


async def test_requests_ask_for_uncompressed_bodies(
    resolver: FakeResolver, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"http://{PUBLIC_IP}/story").mock(return_value=html_response())
    await fetch_article("http://news.example.com/story")
    assert route.calls.last.request.headers["accept-encoding"] == "identity"
