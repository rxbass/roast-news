"""``safety_service`` verdicts and refusal lines (llm_client replaced by ``FakeLLM``)."""

import pytest

from app.exceptions import UpstreamError
from app.services import llm_client
from app.services.safety_service import (
    REFUSAL_LINES,
    RefusalReason,
    check_movie,
    check_output,
    is_model_refusal,
    refusal_message,
)
from app.services.tmdb_client import movie_context
from tests.conftest import MOVIE, FakeLLM


async def test_clean_movie_is_allowed(fake_llm: FakeLLM) -> None:
    verdict = await check_movie(MOVIE)
    assert verdict.allowed is True
    assert verdict.reason is None
    assert fake_llm.classify_calls == 1
    assert fake_llm.moderate_calls == []  # TMDB facts aren't user input: no input moderation


async def test_sensitive_movie_is_refused(fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    fake_llm.category = "real_tragedy"
    verdict = await check_movie(MOVIE)
    assert verdict.allowed is False
    assert verdict.reason is RefusalReason.sensitive_topic
    assert verdict.category == "real_tragedy"


async def test_check_movie_sends_title_and_fact_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []

    async def spy(title: str, context: str) -> llm_client.SensitiveResult:
        seen.append((title, context))
        return llm_client.SensitiveResult(sensitive=False, category="none")

    monkeypatch.setattr(llm_client, "classify_sensitive", spy)
    await check_movie(MOVIE)
    assert seen == [(MOVIE.title, movie_context(MOVIE))]


async def test_check_movie_propagates_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(title: str, context: str) -> llm_client.SensitiveResult:
        raise UpstreamError("down")

    monkeypatch.setattr(llm_client, "classify_sensitive", broken)
    with pytest.raises(UpstreamError):
        await check_movie(MOVIE)


@pytest.mark.parametrize("flagged", [True, False])
async def test_check_output(fake_llm: FakeLLM, flagged: bool) -> None:
    fake_llm.flag_everything = flagged
    assert await check_output("some roast") is flagged
    assert fake_llm.moderate_calls == ["some roast"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (REFUSAL_LINES[0], True),
        ("IDHU ROAST PANNA VENDIYA PADAM ILLA machan", True),
        ("Machan semma padam!", False),
    ],
)
def test_is_model_refusal(text: str, expected: bool) -> None:
    assert is_model_refusal(text) is expected


def test_refusal_message_is_deterministic() -> None:
    first = refusal_message("sensitive_topic", "abc-123")
    assert first == refusal_message("sensitive_topic", "abc-123")
    assert first in REFUSAL_LINES


def test_refusal_message_varies_with_seed() -> None:
    lines = {refusal_message("sensitive_topic", f"seed-{i}") for i in range(60)}
    assert len(lines) > 1
    assert lines <= set(REFUSAL_LINES)


def test_refusal_message_handles_none_reason() -> None:
    assert refusal_message(None, "x") in REFUSAL_LINES
    assert refusal_message(None, "x") == refusal_message("", "x")
