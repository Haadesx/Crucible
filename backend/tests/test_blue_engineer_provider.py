"""Capability-aware Blue engineer provider tests.

Pins the production decision from the 2026-09-26 bake-off: Nemotron first with a Ling
fallback, Ling never sent the response_format request it is known to reject, the fallback
used only on outright failure, and the authoring model persisted per patch.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.coevolution.engine import CoevolutionEngine
from app.coevolution.providers import (
    BlueEngineerProvider,
    OpenAICompatibleProvider,
    ProviderConfig,
)
from app.events import ArenaEventBus
from app.memory.repository import InMemoryRepository
from app.memory.vector import HashEmbedding, VectorMemory
from app.scenarios.loader import ScenarioCatalog
from test_coevolution import (  # type: ignore[import-not-found]
    PATCH_JSON,
    BlueScript,
    FakeCompletions,
    RedScript,
    _completion,
    _provider,
)


class Tiny(BaseModel):
    ok: bool


def scripted_config(model: str, *, json_mode: str = "auto") -> ProviderConfig:
    return ProviderConfig(
        role_name="BLUE",
        provider="openai_compatible",
        base_url="http://127.0.0.1:9/v1",
        api_key="local",
        model=model,
        json_mode=json_mode,  # type: ignore[arg-type]
    )


def scripted_provider(model: str, script: Any, *, json_mode: str = "auto") -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(scripted_config(model, json_mode=json_mode))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(script)))
    return provider


def _requests(provider: OpenAICompatibleProvider) -> list[dict[str, Any]]:
    return list(provider.client.chat.completions.requests)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_ling_engineer_never_sends_the_unsupported_response_format() -> None:
    provider = scripted_provider(
        "inclusionai/ling-3.0-flash-fin:free",
        lambda kwargs: _completion(json.dumps({"ok": True})),
        json_mode="never",
    )
    value, call = await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T-CAP", generation=0, role="blue_harness_engineer"
    )
    assert value.ok is True and call.call_id
    requests = _requests(provider)
    assert requests, "the request must still be made"
    assert all("response_format" not in request for request in requests), (
        "Ling must not be sent the response_format request it rejects with HTTP 400"
    )


@pytest.mark.anyio
async def test_auto_config_start_sends_native_json_mode() -> None:
    provider = scripted_provider(
        "nvidia/nemotron-3-super-120b-a12b:free",
        lambda kwargs: _completion(json.dumps({"ok": True})),
    )
    await provider.structured_output(
        schema=Tiny, system="s", user="u", run_id="T-CAP", generation=0, role="blue_harness_engineer"
    )
    assert "response_format" in _requests(provider)[0], "native JSON mode must be requested first"


@pytest.mark.anyio
async def test_engineer_falls_back_only_after_primary_fails() -> None:
    primary = scripted_provider("nvidia/nemotron-3-super-120b-a12b:free", lambda kwargs: _completion("not json at all"))
    fallback = scripted_provider(
        "inclusionai/ling-3.0-flash-fin:free",
        lambda kwargs: _completion(json.dumps({"ok": True})),
        json_mode="never",
    )
    engineer = BlueEngineerProvider(primary, fallback)

    value, call = await engineer.structured_output(
        schema=Tiny, system="s", user="u", run_id="T-FB", generation=0, role="blue_harness_engineer", repairs=1
    )
    assert value.ok is True
    assert engineer.fallbacks == 1
    assert len(primary.calls) == 2, "primary: one attempt plus one repair, then it failed"
    assert len(fallback.calls) == 1, "the fallback must be called exactly once"
    accepted = next(item for item in engineer.calls if item.id == call.call_id)
    assert accepted.model == "inclusionai/ling-3.0-flash-fin:free", "the authoring model must be the fallback"
    failed_attempts = [item for item in engineer.calls if item.model == "nvidia/nemotron-3-super-120b-a12b:free"]
    assert len(failed_attempts) == 2, "both rejected primary attempts stay visible in the ledger"
    assert all("not json" in item.output_text for item in failed_attempts)


@pytest.mark.anyio
async def test_engineer_does_not_touch_the_fallback_when_primary_succeeds() -> None:
    primary = scripted_provider(
        "nvidia/nemotron-3-super-120b-a12b:free",
        lambda kwargs: _completion(json.dumps({"ok": True})),
    )
    fallback = scripted_provider("inclusionai/ling-3.0-flash-fin:free", lambda kwargs: _completion(json.dumps({"ok": True})))
    engineer = BlueEngineerProvider(primary, fallback)
    await engineer.structured_output(
        schema=Tiny, system="s", user="u", run_id="T-NOFB", generation=0, role="blue_harness_engineer"
    )
    assert engineer.fallbacks == 0
    assert fallback.calls == [], "providers must not be raced by default"


@pytest.mark.anyio
async def test_engine_persists_the_engineer_model_that_authored_each_patch() -> None:
    red = _provider("RED", "test-red-model", RedScript())
    executor = _provider("BLUE", "executor-model", BlueScript())
    engineer_primary = scripted_provider(
        "nvidia/nemotron-3-super-120b-a12b:free",
        lambda kwargs: _completion(json.dumps(PATCH_JSON)),
    )
    engineer = BlueEngineerProvider(engineer_primary, None)

    repository = InMemoryRepository()
    await repository.start()
    engine = CoevolutionEngine(
        repository,
        VectorMemory(repository, HashEmbedding(64), use_atlas_vector_search=False),
        ScenarioCatalog(),
        red_provider=red,
        blue_provider=executor,
        engineer_provider=engineer,
        test_mode=False,
        event_bus=ArenaEventBus(),
    )
    await engine.run(run_id="T-ATTRIB", generations=1, red_versions=1, attacks_per_version=1, blue_candidates=1)

    calls = await repository.list_model_calls("T-ATTRIB")
    engineer_calls = [call for call in calls if call.role == "blue_harness_engineer"]
    assert engineer_calls, "the engineer's calls must reach the ledger"
    assert all(call.model == "nvidia/nemotron-3-super-120b-a12b:free" for call in engineer_calls)
    patches = [patch for patch in await repository.list_patch_records("T-ATTRIB") if not patch.id.endswith("-RESULT")]
    assert patches, "fixture must author a patch"
    by_id = {call.id: call for call in calls}
    assert patches[0].model_call_id in by_id
    assert by_id[patches[0].model_call_id].model == "nvidia/nemotron-3-super-120b-a12b:free"
    # The executor's own identity is untouched by the engineer swap.
    blue_versions = await repository.list_blue_versions("T-ATTRIB")
    assert any(version.base_model == "executor-model" for version in blue_versions)
