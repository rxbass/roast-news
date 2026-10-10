"""URL normalization, hashing and domain extraction."""

import pytest

from app.services.url_utils import extract_domain, normalize_url, redact_url, url_hash


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://News.Example.COM/Story", "https://news.example.com/Story"),
        ("https://news.example.com/story#comments", "https://news.example.com/story"),
        ("https://news.example.com:443/story", "https://news.example.com/story"),
        ("http://news.example.com:80/story", "http://news.example.com/story"),
        ("http://news.example.com:8080/story", "http://news.example.com:8080/story"),
        ("https://news.example.com/story/", "https://news.example.com/story"),
        ("https://news.example.com/story///", "https://news.example.com/story"),
        ("https://news.example.com", "https://news.example.com/"),
        ("https://news.example.com/", "https://news.example.com/"),
        ("https://news.example.com./story", "https://news.example.com/story"),
        ("  https://news.example.com/story  ", "https://news.example.com/story"),
        ("https://user:pw@news.example.com/story", "https://news.example.com/story"),
        ("https://[2001:DB8::1]:8443/x", "https://[2001:db8::1]:8443/x"),
        ("https://news.example.com:99999/x", "https://news.example.com/x"),
    ],
)
def test_normalize_url_basic(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_normalize_strips_tracking_params_and_sorts() -> None:
    raw = (
        "https://news.example.com/story?utm_source=tw&b=2&fbclid=abc&a=1&gclid=x"
        "&UTM_Medium=social&ref=home&hsa_cam=1&keep="
    )
    assert normalize_url(raw) == "https://news.example.com/story?a=1&b=2&keep="


def test_normalize_keeps_repeated_params_sorted() -> None:
    assert normalize_url("https://e.com/p?x=2&x=1&id=9") == "https://e.com/p?id=9&x=1&x=2"


def test_tracking_variants_share_a_hash() -> None:
    a = normalize_url("https://News.example.com/story/?utm_source=x&id=5#top")
    b = normalize_url("https://news.example.com:443/story?id=5&fbclid=zzz")
    assert a == b
    assert url_hash(a) == url_hash(b)


def test_url_hash_is_stable_sha256() -> None:
    value = url_hash("https://news.example.com/story")
    assert value == url_hash("https://news.example.com/story")
    assert len(value) == 64
    assert int(value, 16) >= 0
    assert value != url_hash("https://news.example.com/other")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.TheHindu.com/news/x", "thehindu.com"),
        ("https://news.example.com./x", "news.example.com"),
        ("http://example.com:8080", "example.com"),
        ("not a url", ""),
    ],
)
def test_extract_domain(raw: str, expected: str) -> None:
    assert extract_domain(raw) == expected


def test_redact_url_drops_query_and_fragment() -> None:
    assert (
        redact_url("https://news.example.com/a/b?token=secret#frag")
        == "https://news.example.com/a/b"
    )
