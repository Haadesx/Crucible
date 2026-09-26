from fastapi import APIRouter, Depends, HTTPException

from app.agent.provider import FakeAgent
from app.api.dependencies import get_container, require_writable
from app.dependencies import AppContainer
from app.models.generation import ArenaStartRequest, RunStatus

router = APIRouter(prefix="/arena", tags=["arena"])

ARENA_START_UNAVAILABLE = (
    "ARENA_START_UNAVAILABLE: live co-evolution runs start via `python -m app.coevolution`; "
    "this endpoint only supports TEST/demo fixtures"
)


def _refuses_arena_start(container: AppContainer) -> bool:
    """The HTTP start route runs the deterministic FakeAgent loop; it is for TEST/demo
    fixtures, never for production-like persistence. WITHOUT this guard a DEV observer
    booted against MongoDB/Atlas (no target model) would accept a start and write fake
    RUN-… records beside real evidence. REAL runs belong to the co-evolution CLI.
    """

    if container.settings.effective_run_mode == "REAL":
        return True
    return (
        not container.settings.test_mode
        and isinstance(container.agent, FakeAgent)
        and container.repository.backend == "mongodb"
    )


@router.post("/reset")
async def reset_arena(container: AppContainer = Depends(require_writable)) -> dict[str, str]:
    await container.evolution.stop()
    await container.repository.reset()
    await container.event_bus.clear()
    return {"status": "reset"}


@router.post("/start")
async def start_arena(
    request: ArenaStartRequest,
    container: AppContainer = Depends(require_writable),
) -> dict[str, str]:
    if _refuses_arena_start(container):
        raise HTTPException(status_code=409, detail=ARENA_START_UNAVAILABLE)
    if container.settings.demo_mode:
        request = request.model_copy(
            update={"generations": min(request.generations, 3), "red_population": min(request.red_population, 4), "blue_population": min(request.blue_population, 4), "matchups_per_genome": min(request.matchups_per_genome, 2)}
        )
    try:
        run_id = await container.evolution.start(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "started"}


@router.post("/stop")
async def stop_arena(container: AppContainer = Depends(get_container)) -> dict[str, str]:
    await container.evolution.stop()
    return {"status": (await container.evolution.status()).status}


@router.get("/status", response_model=RunStatus)
async def arena_status(container: AppContainer = Depends(get_container)) -> RunStatus:
    return await container.evolution.status()


@router.get("/lineage")
async def arena_lineage(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    if run_id is None:
        status = await container.evolution.status()
        run_id = status.run_id
    if run_id is None:
        return {"run_id": None, "red": [], "blue": []}
    red, blue = await container.repository.list_attacks(run_id), await container.repository.list_defenses(run_id)
    return {
        "run_id": run_id,
        "red": [record.model_dump(mode="json") for record in red],
        "blue": [record.model_dump(mode="json") for record in blue],
    }
