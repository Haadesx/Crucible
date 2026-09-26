"""Reasoning-model completion handling: empty content, length termination, bounded escalation.

The rig's Red model is a reasoning model: a budget spent entirely on hidden reasoning
returns finish_reason=length with empty visible content. These tests pin the production
response: retry with a larger *final-output* budget, bounded; never treat reasoning text
as the answer; never persist it; fail closed when a valid answer never arrives.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.coevolution.providers import OpenAICompatibleProvider, ProviderConfig, ProviderError
from test_coevolution import FakeCompletions  # type: ignore[import-not-found]


class Tiny(BaseModel):
    ok: bool


def completion(*, content: str = "", reasoning: str = "", finish_reason: str = "stop") -> Any:
    message = SimpleNamespace(content=content, tool_calls=[], reasoning_content=reasoning)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=None,
        model="reasoning-test-model",
    )


def provider_for(script: Any) -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(
        ProviderConfig(
            role_name="RED",
            provider="openai_compatible",
            base_url="http://127.0.0.1:9/v1",
            api_key="local",
            model="reasoning-test-model",
        )
    )
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(script)))
    return provider


def requests_of(provider: OpenAICompatibleProvider) -> list[dict[str, Any]]:
    return list(provider.client.chat.completions.requests)  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.coevolution.providers._sleep", _noop)


@pytest.mark.anyio
async def test_normal_content_response() -> None:
    provider = provider_for(lambda kwargs: completion(content="READY"))
    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}], run_id="T", generation=0, role="red_attacker", max_tokens=64
    )
    assert result.text == "READY"
    assert result.finish_reason == "stop"
    assert len(provider.calls) == 1 and provider.calls[0].error is None


@pytest.mark.anyio
async def test_reasoning_with_valid_final_content_is_accepted_and_reasoning_not_persisted() -> None:
    provider = provider_for(
        lambda kwargs: completion(reasoning="secret chain of thought", content=json.dumps({"ok": True}))
    )
    value, _call = await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=256
    )
    assert value.ok is True
    assert len(provider.calls) == 1
    assert provider.calls[0].output_text == json.dumps({"ok": True})
    assert "secret chain of thought" not in provider.calls[0].output_text


@pytest.mark.anyio
async def test_reasoning_only_completion_retries_with_a_larger_budget_then_succeeds() -> None:
    script = iter(
        [
            completion(reasoning="thinking forever", finish_reason="length"),
            completion(content=json.dumps({"ok": True})),
        ]
    )
    provider = provider_for(lambda kwargs: next(script))
    value, _ = await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=800
    )
    assert value.ok is True
    budgets = [request["max_tokens"] for request in requests_of(provider)]
    assert budgets == [800, 1600], "the retry must raise the final-output budget"
    assert len(provider.calls) == 2
    assert "reasoning-only completion" in (provider.calls[0].error or "")
    assert "max_tokens=1600" in (provider.calls[0].error or "")
    assert provider.calls[0].output_text == ""


@pytest.mark.anyio
async def test_length_termination_without_reasoning_is_reported_explicitly() -> None:
    script = iter([completion(finish_reason="length"), completion(content=json.dumps({"ok": True}))])
    provider = provider_for(lambda kwargs: next(script))
    await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=512
    )
    assert "empty completion (finish_reason=length)" in (provider.calls[0].error or "")


@pytest.mark.anyio
async def test_bounded_failure_after_retries_fails_closed() -> None:
    provider = provider_for(lambda kwargs: completion(reasoning="looping", finish_reason="length"))
    with pytest.raises(ProviderError) as exc:
        await provider.structured_output(
            schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=800
        )
    assert exc.value.code == "RED_PROVIDER_EMPTY_RESPONSE"
    assert len(provider.calls) <= 5, "emptiness must be retried a bounded number of times"
    assert all(call.output_text == "" for call in provider.calls)
    assert all("reasoning-only" in (call.error or "") for call in provider.calls)


@pytest.mark.anyio
async def test_truncated_json_repair_escalates_the_budget() -> None:
    script = iter(
        [
            completion(content='{"ok": tru', finish_reason="length"),
            completion(content=json.dumps({"ok": True})),
        ]
    )
    provider = provider_for(lambda kwargs: next(script))
    value, _ = await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=800
    )
    assert value.ok is True
    budgets = [request["max_tokens"] for request in requests_of(provider)]
    assert budgets == [800, 1600], "a truncated answer must raise the repair round's budget"


@pytest.mark.anyio
async def test_malformed_final_output_still_fails_validation() -> None:
    provider = provider_for(lambda kwargs: completion(content="definitely not json"))
    with pytest.raises(ProviderError) as exc:
        await provider.structured_output(
            schema=Tiny, system="s", user="u", run_id="T", generation=0, role="red_attacker", max_tokens=256, repairs=1
        )
    assert exc.value.code.endswith("_PROVIDER_UNUSABLE_OUTPUT")
