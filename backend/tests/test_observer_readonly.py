"""Observer read-only contract: serving an evidence snapshot must not write it.

The guard is capability-based (``repository.read_only``), not filename-based. A
snapshot-backed API repository opens read-only unless ``ALLOW_SNAPSHOT_WRITES=true``
opts a dedicated live snapshot into writes; mutating routes answer 409
``READ_ONLY_SNAPSHOT`` and the snapshot bytes never change. The co-evolution CLI owns
its snapshot and stays writable.
"""

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.coevolution.runtime import build_stack
from app.dependencies import AppContainer, build_container
from app.main import create_app
from app.memory.repository import InMemoryRepository, RepositoryReadOnlyError
from app.models.audit import ModelCall
from app.models.events import ArenaEvent
from app.models.generation import GenerationRecord

RUN = "OBS-READONLY"
BASE = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _write_source_snapshot(path: Path) -> None:
    """Produce a small valid snapshot the way the CLI would, for copying to observers."""

    writer = InMemoryRepository(snapshot_path=path, read_only=False)
    await writer.start()
    await writer.save_generation(
        GenerationRecord(
            id=0,
            run_id=RUN,
            red_population=[],
            blue_population=[],
            red_champion="R-0",
            blue_champion="B-0",
            attack_success_rate=0.5,
            utility_rate=1.0,
            red_mean_fitness=1.0,
            blue_mean_fitness=0.5,
            total_battles=2,
            created_at=BASE,
        )
    )
    await writer.save_model_call(
        ModelCall(
            run_id=RUN,
            generation=0,
            provider="openai_compatible",
            model="test-red",
            role="red_attacker",
            input_hash="hash-red",
            prompt_chars=10,
            latency_ms=1,
            created_at=BASE,
        )
    )
    await writer.save_event(
        ArenaEvent(type="generation_finished", run_id=RUN, generation=0, created_at=BASE)
    )


async def _serve_snapshot(path: Path, *, allow_writes: bool = False) -> tuple[FastAPI, AppContainer]:
    """Boot the real container wiring the API uses, pointed at ``path``."""

    settings = Settings(
        _env_file=None,
        run_mode="DEV",
        test_mode=False,
        mongodb_uri="",
        dev_state_path=str(path),
        allow_snapshot_writes=allow_writes,
        red_base_url="http://127.0.0.1:9/v1",
        red_model="test-red",
        blue_provider="openai_compatible",
        blue_base_url="http://127.0.0.1:9/v1",
        blue_model="test-blue",
    )
    container = await build_container(settings)
    app = create_app()
    app.state.container = container
    return app, container


async def test_snapshot_backed_repository_refuses_writes_and_reset(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    await _write_source_snapshot(source)
    served = tmp_path / "served.json"
    shutil.copy(source, served)

    repository = InMemoryRepository(snapshot_path=served)
    await repository.start()
    before = _sha256(served)

    assert repository.read_only is True
    with pytest.raises(RepositoryReadOnlyError):
        await repository.save_event(
            ArenaEvent(type="generation_started", run_id=RUN, generation=0, created_at=BASE)
        )
    with pytest.raises(RepositoryReadOnlyError):
        await repository.reset()

    assert _sha256(served) == before
    assert await repository.get_generation(0, RUN) is not None
    assert InMemoryRepository().read_only is False


async def test_observer_server_blocks_mutations_and_keeps_evidence_intact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    await _write_source_snapshot(source)
    served = tmp_path / "served.json"
    shutil.copy(source, served)
    before = _sha256(served)

    app, container = await _serve_snapshot(served)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/arena/start",
                json={"generations": 2, "red_population": 4, "blue_population": 4, "matchups_per_genome": 2},
            )
            assert start.status_code == 409
            assert "READ_ONLY_SNAPSHOT" in start.json()["detail"]

            reset = await client.post("/arena/reset")
            assert reset.status_code == 409
            assert "READ_ONLY_SNAPSHOT" in reset.json()["detail"]

            replay = await client.post(
                "/replay", json={"attack_id": "A-X", "defense_id": "B-X", "scenario_id": "DOC-001"}
            )
            assert replay.status_code == 409

            compare = await client.post(
                "/replay/compare",
                json={"attack_id": "A-X", "scenario_id": "DOC-001", "harness_b_id": "B-X"},
            )
            assert compare.status_code == 409

            status = await client.get("/arena/status")
            generations = await client.get(f"/generations?run_id={RUN}")
            runs = await client.get("/runs")
            calls = await client.get("/model-calls")
            system = await client.get("/system/status")
    finally:
        await container.close()

    assert status.status_code == 200
    assert generations.status_code == 200 and len(generations.json()) == 1
    assert runs.status_code == 200 and any(run["run_id"] == RUN for run in runs.json())
    assert calls.status_code == 200 and len(calls.json()) == 1
    assert system.status_code == 200
    assert _sha256(served) == before


async def test_allow_snapshot_writes_opt_in_makes_a_fresh_live_snapshot_writable(tmp_path: Path) -> None:
    live = tmp_path / "live.json"
    assert not live.exists()

    app, container = await _serve_snapshot(live, allow_writes=True)
    try:
        assert container.repository.read_only is False
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/arena/start",
                json={"generations": 2, "red_population": 4, "blue_population": 4, "matchups_per_genome": 2},
            )
            assert start.status_code == 200
            await container.evolution.wait()

            reset = await client.post("/arena/reset")
            assert reset.status_code == 200
    finally:
        await container.evolution.stop()
        await container.close()

    assert live.exists()
    assert container.repository.read_only is False
    assert await container.repository.list_generations() == []


async def test_system_status_exposes_the_repository_read_only_capability(tmp_path: Path) -> None:
    """The UI's HISTORICAL/LIVE chip reads this field, so it must come from the capability."""

    source = tmp_path / "source.json"
    await _write_source_snapshot(source)
    served = tmp_path / "served.json"
    shutil.copy(source, served)

    app, container = await _serve_snapshot(served)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            historical = (await client.get("/system/status")).json()
    finally:
        await container.close()

    assert historical["read_only"] is True
    assert historical["persistence"]["backend"] == "dev_snapshot"
    assert historical["persistence"]["atlas_connected"] is False

    live = tmp_path / "live.json"
    app, container = await _serve_snapshot(live, allow_writes=True)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            writable = (await client.get("/system/status")).json()
    finally:
        await container.close()

    assert writable["read_only"] is False


async def test_cli_runtime_keeps_its_snapshot_writable(tmp_path: Path) -> None:
    state = tmp_path / "cli-state.json"
    settings = Settings(
        _env_file=None,
        run_mode="DEV",
        test_mode=False,
        mongodb_uri="",
        dev_state_path=str(state),
        red_base_url="http://localhost:11500/v1",
        red_model="red",
        blue_provider="openai_compatible",
        blue_base_url="http://localhost:9000/v1",
        blue_model="blue",
    )
    stack = await build_stack(settings)
    try:
        assert stack.repository.read_only is False
        await stack.repository.save_event(
            ArenaEvent(type="generation_started", run_id="CLI", generation=0, created_at=BASE)
        )
    finally:
        await stack.close()

    assert state.exists()
