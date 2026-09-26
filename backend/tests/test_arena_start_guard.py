"""Kiro finding 1: POST /arena/start must not run the deterministic FakeAgent loop
against production-like persistence.

A writable MongoDB/Atlas observer (DEV mode, no target model -> FakeAgent) previously
accepted a start and would have written fake RUN-… records beside real evidence. The
guard refuses that, and any REAL-mode start; TEST/demo fixtures are unaffected.
"""

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from app.agent.provider import FakeAgent
from app.config import Settings
from app.main import create_app

START = {"generations": 2, "red_population": 4, "blue_population": 4, "matchups_per_genome": 2}


class _StubEvolution:
    """Records that a start was allowed, without running the arena."""

    def __init__(self) -> None:
        self.started = False

    async def start(self, request: Any) -> str:
        self.started = True
        return "RUN-STUB"


def _stub_container(*, test_mode: bool, backend: str, run_mode: str = "DEV") -> SimpleNamespace:
    return SimpleNamespace(
        settings=Settings(_env_file=None, run_mode=run_mode, test_mode=test_mode),
        agent=FakeAgent(),
        repository=SimpleNamespace(backend=backend, read_only=False),
        evolution=_StubEvolution(),
    )


async def _post_start(container: SimpleNamespace) -> Response:
    app: FastAPI = create_app()
    app.state.container = container
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/arena/start", json=START)


async def test_fake_agent_start_against_mongodb_is_refused_outside_test_mode() -> None:
    container = _stub_container(test_mode=False, backend="mongodb")

    response = await _post_start(container)

    assert response.status_code == 409
    assert response.json()["detail"].startswith("ARENA_START_UNAVAILABLE")
    assert container.evolution.started is False


async def test_real_mode_start_is_refused_even_with_a_real_agent() -> None:
    container = _stub_container(test_mode=False, backend="memory", run_mode="REAL")
    container.agent = SimpleNamespace()  # not a FakeAgent

    response = await _post_start(container)

    assert response.status_code == 409
    assert response.json()["detail"].startswith("ARENA_START_UNAVAILABLE")
    assert container.evolution.started is False


async def test_test_mode_fake_agent_start_still_works() -> None:
    container = _stub_container(test_mode=True, backend="memory")

    response = await _post_start(container)

    assert response.status_code == 200
    assert response.json() == {"run_id": "RUN-STUB", "status": "started"}
    assert container.evolution.started is True
