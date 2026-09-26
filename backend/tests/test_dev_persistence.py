import json
from datetime import UTC, datetime

import pytest

from app.coevolution.runtime import build_stack
from app.config import Settings
from app.memory.repository import InMemoryRepository
from app.models.audit import ModelCall
from app.models.events import ArenaEvent
from app.models.generation import GenerationRecord
from app.models.red import AttackCandidate, RedAgentVersion


@pytest.mark.asyncio
async def test_dev_snapshot_survives_fresh_repository_and_reset(tmp_path):
    path = tmp_path / "state.json"
    first = InMemoryRepository(snapshot_path=path, read_only=False)
    await first.start()
    generation = GenerationRecord(
        id=0,
        run_id="DEV-RUN",
        red_population=[],
        blue_population=[],
        red_champion="RED-0",
        blue_champion="BLUE-0",
        attack_success_rate=0,
        utility_rate=1,
        red_mean_fitness=0,
        blue_mean_fitness=1,
        total_battles=1,
        created_at=datetime.now(UTC),
    )
    await first.save_generation(generation)
    assert json.loads(path.read_text())["generations"][0][0] == ["DEV-RUN", 0]
    await first.save_red_version(
        RedAgentVersion(id="R-DEV-RUN-G00", run_id="DEV-RUN", generation=0, base_model="ai-rig", system_strategy="probe")
    )
    await first.save_attack_candidate(
        AttackCandidate(
            id="A-DEV-RUN-G00", run_id="DEV-RUN", red_agent_version_id="R-DEV-RUN-G00",
            scenario_id="S-1", attack_family="tool_output_injection", carrier="document",
            target_capability="send_email", payload="attack", generated_by_model="ai-rig", generation=0,
        )
    )
    await first.save_model_call(
        ModelCall(
            id="CALL-DEV", run_id="DEV-RUN", generation=0, provider="openai_compatible",
            model="ai-rig", role="red_attacker", input_hash="abc", prompt_chars=5, latency_ms=1,
        )
    )
    await first.save_event(ArenaEvent(type="generation_finished", run_id="DEV-RUN", generation=0, created_at=datetime.now(UTC)))
    await first.set_active_harness("DEV-RUN", "B-DEV-RUN-G00")

    restarted = InMemoryRepository(snapshot_path=path, read_only=False)
    await restarted.start()
    assert await restarted.get_generation(0, "DEV-RUN") == generation
    assert [version.id for version in await restarted.list_red_versions("DEV-RUN")] == ["R-DEV-RUN-G00"]
    assert [candidate.id for candidate in await restarted.list_attack_candidates("DEV-RUN")] == ["A-DEV-RUN-G00"]
    assert [call.id for call in await restarted.list_model_calls("DEV-RUN")] == ["CALL-DEV"]
    assert len(await restarted.recent_events()) == 1
    assert restarted.active_harnesses == {"DEV-RUN": "B-DEV-RUN-G00"}

    await restarted.reset()
    empty = InMemoryRepository(snapshot_path=path)
    await empty.start()
    assert await empty.list_generations("DEV-RUN") == []
    assert await empty.list_model_calls("DEV-RUN") == []
    assert empty.active_harnesses == {}


@pytest.mark.asyncio
async def test_ephemeral_repository_does_not_write_snapshot(tmp_path):
    repository = InMemoryRepository()
    await repository.start()
    await repository.save_event(ArenaEvent(type="generation_started", run_id="DEV", generation=0, created_at=datetime.now(UTC)))
    assert repository.backend == "memory"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_interrupted_snapshot_write_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    repository = InMemoryRepository(snapshot_path=path, read_only=False)
    await repository.save_event(ArenaEvent(type="generation_started", run_id="DEV", generation=0, created_at=datetime.now(UTC)))
    previous = path.read_bytes()

    def fail_replace(*_args):
        raise OSError("interrupted write")

    monkeypatch.setattr("app.memory.repository.os.replace", fail_replace)
    with pytest.raises(OSError, match="interrupted write"):
        await repository.save_event(ArenaEvent(type="generation_finished", run_id="DEV", generation=0, created_at=datetime.now(UTC)))

    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.asyncio
async def test_dev_stack_uses_snapshot_and_test_stack_stays_ephemeral(tmp_path):
    path = tmp_path / "dev-state.json"
    settings = Settings(
        _env_file=None, run_mode="DEV", test_mode=False, mongodb_uri="", dev_state_path=str(path),
        red_base_url="http://localhost:11500/v1", red_model="red",
        blue_provider="openai_compatible", blue_base_url="http://localhost:9000/v1", blue_model="blue",
    )
    first = await build_stack(settings)
    assert first.describe()["mongodb"] == "DEV / ATLAS NOT CONNECTED (durable snapshot)"
    await first.repository.save_event(ArenaEvent(type="generation_started", run_id="DEV", generation=0, created_at=datetime.now(UTC)))
    await first.close()

    restarted = await build_stack(settings)
    assert len(await restarted.repository.recent_events()) == 1
    await restarted.close()

    test_stack = await build_stack(settings.model_copy(update={"run_mode": "TEST"}))
    assert test_stack.describe()["mongodb"] == "TEST / ATLAS NOT CONNECTED (in-memory)"
    assert await test_stack.repository.recent_events() == []
    await test_stack.close()
