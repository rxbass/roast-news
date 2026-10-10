"""``safety_service`` verdicts and refusal lines (llm_client replaced by ``FakeLLM``)."""

import pytest

from app.exceptions import UpstreamError
from app.services import llm_client, safety_service
from app.services.safety_service import (
    REFUSAL_LINES,
    RefusalReason,
    check_article,
    check_output,
    is_model_refusal,
    refusal_message,
)
from app.services.scraper_service import Article
from tests.conftest import ARTICLE_TEXT, FakeLLM

ARTICLE = Article(
    title="Road repairs", text=ARTICLE_TEXT, domain="news.example.com", final_url="https://x"
)


async def test_clean_article_is_allowed(fake_llm: FakeLLM) -> None:
    verdict = await check_article(ARTICLE)
    assert verdict.allowed is True
    assert verdict.reason is None
    assert fake_llm.classify_calls == 1
    assert fake_llm.moderate_calls == [f"{ARTICLE.title}\n\n{ARTICLE.text}"]


async def test_moderation_flag_wins_over_classifier(fake_llm: FakeLLM) -> None:
    fake_llm.flag_everything = True
    fake_llm.sensitive = True
    verdict = await check_article(ARTICLE)
    assert verdict.allowed is False
    assert verdict.reason is RefusalReason.moderation_flagged
    assert fake_llm.classify_calls == 1  # both checks run concurrently


async def test_sensitive_article_is_refused(fake_llm: FakeLLM) -> None:
    fake_llm.sensitive = True
    fake_llm.category = "disaster"
    verdict = await check_article(ARTICLE)
    assert verdict.allowed is False
    assert verdict.reason is RefusalReason.sensitive_topic
    assert verdict.category == "disaster"


async def test_check_article_truncates_sample(fake_llm: FakeLLM) -> None:
    long_article = Article(title="T", text="z" * 10_000, domain="d", final_url="u")
    await check_article(long_article)
    assert len(fake_llm.moderate_calls[0]) == safety_service.CHECK_CHAR_LIMIT


async def test_check_article_propagates_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(text: str) -> bool:
        raise UpstreamError("down")

    monkeypatch.setattr(llm_client, "moderate", broken)
    with pytest.raises(UpstreamError):
        await check_article(ARTICLE)


@pytest.mark.parametrize("flagged", [True, False])
async def test_check_output(fake_llm: FakeLLM, flagged: bool) -> None:
    fake_llm.flag_everything = flagged
    assert await check_output("some roast") is flagged
    assert fake_llm.moderate_calls == ["some roast"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (REFUSAL_LINES[0], True),
        ("IDHU ROAST PANNA VENDIYA NEWS ILLA machan", True),
        ("Machan semma news!", False),
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
