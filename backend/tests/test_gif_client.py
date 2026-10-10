"""``gif_client`` against a mocked GIPHY (respx): never raises, safe URLs only, caching."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from app.config import settings
from app.services import gif_client, llm_client

pytestmark = pytest.mark.real_gifs


@pytest.fixture
def giphy(monkeypatch: pytest.MonkeyPatch) -> Iterator[respx.MockRouter]:
    monkeypatch.setattr(settings, "GIPHY_API_KEY", "giphy-test-key")
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def item(n: int, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "url": f"https://giphy.com/gifs/reaction-{n}",
        "images": {"fixed_height": {"url": f"https://media{n % 4}.giphy.com/media/{n}/200.gif"}},
    }
    body.update(overrides)
    return body


def test_every_llm_mood_has_queries() -> None:
    assert set(gif_client.MOOD_QUERIES) == set(llm_client.GIF_MOODS)


async def test_pick_gif_is_deterministic_and_g_rated(giphy: respx.MockRouter) -> None:
    route = giphy.get(gif_client.GIPHY_SEARCH_URL).respond(
        json={"data": [item(i) for i in range(5)]}
    )
    first = await gif_client.pick_gif("facepalm", "roast-1")
    again = await gif_client.pick_gif("facepalm", "roast-1")
    assert first is not None
    assert first == again
    assert first.url.startswith("https://media")
    assert first.page_url.startswith("https://giphy.com/gifs/")
    params = route.calls.last.request.url.params
    assert params["rating"] == "g"
    assert params["q"] == gif_client.MOOD_QUERIES["facepalm"][0]
    assert params["api_key"] == "giphy-test-key"
    assert route.call_count == 1  # second pick came from the cache


async def test_falls_back_to_next_query_when_empty(giphy: respx.MockRouter) -> None:
    primary, fallback = gif_client.MOOD_QUERIES["facepalm"]
    giphy.get(gif_client.GIPHY_SEARCH_URL, params={"q": primary}).respond(json={"data": []})
    giphy.get(gif_client.GIPHY_SEARCH_URL, params={"q": fallback}).respond(json={"data": [item(1)]})
    gif = await gif_client.pick_gif("facepalm", "seed")
    assert gif is not None
    assert gif.page_url == "https://giphy.com/gifs/reaction-1"


@pytest.mark.parametrize(
    "bad",
    [
        item(1, url="http://giphy.com/gifs/x"),
        item(2, url="https://evil.example.com/x"),
        item(3, images={"fixed_height": {"url": "https://giphy.com.evil.com/a.gif"}}),
        item(4, images={"fixed_height": {"url": "javascript:alert(1)"}}),
        item(5, images={"fixed_height": {}}),
        item(6, images=None),
        item(7, url="https://giphy.com/" + "a" * 600),
        "junk",
    ],
)
async def test_unsafe_or_malformed_items_are_skipped(giphy: respx.MockRouter, bad: Any) -> None:
    giphy.get(gif_client.GIPHY_SEARCH_URL).respond(json={"data": [bad]})
    assert await gif_client.pick_gif("cringe", "seed") is None


@pytest.mark.parametrize("mood", [None, "", "not-a-mood"])
async def test_unknown_mood_makes_no_call(giphy: respx.MockRouter, mood: str | None) -> None:
    route = giphy.get(gif_client.GIPHY_SEARCH_URL)
    assert await gif_client.pick_gif(mood, "seed") is None
    assert route.call_count == 0


async def test_no_api_key_means_no_gif(
    giphy: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GIPHY_API_KEY", "")
    route = giphy.get(gif_client.GIPHY_SEARCH_URL)
    assert await gif_client.pick_gif("facepalm", "seed") is None
    assert route.call_count == 0


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(429, json={}),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json={"data": "nope"}),
    ],
)
async def test_giphy_failures_never_raise(
    giphy: respx.MockRouter, response: httpx.Response
) -> None:
    giphy.get(gif_client.GIPHY_SEARCH_URL).mock(return_value=response)
    assert await gif_client.pick_gif("eye_roll", "seed") is None


async def test_network_error_never_raises(giphy: respx.MockRouter) -> None:
    giphy.get(gif_client.GIPHY_SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    assert await gif_client.pick_gif("bored", "seed") is None
