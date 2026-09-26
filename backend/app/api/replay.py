from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_writable
from app.dependencies import AppContainer
from app.models.generation import HarnessComparisonRequest, ReplayRequest
from app.models.harness import HarnessVersion

router = APIRouter(tags=["replay"])


@router.post("/replay/compare")
async def compare_harnesses(
    request: HarnessComparisonRequest,
    container: AppContainer = Depends(require_writable),
) -> dict[str, object]:
    attack = await container.repository.get_attack(request.attack_id)
    if attack is None:
        raise HTTPException(status_code=404, detail="attack not found")
    record = await container.repository.get_harness(request.harness_b_id)
    if record is None:
        raise HTTPException(status_code=404, detail="harness not found")
    try:
        scenario = container.catalog.get(request.scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc

    harness_a = (
        record.version
        if request.harness_a_id is None
        else await _get_harness_version(container, request.harness_a_id)
    )
    if request.harness_a_id is None:
        harness_a = HarnessVersion.naked(version_id="HARNESS-NAKED")
    deployed_a = container.evolution.harness_registry.rehearse(harness_a)
    deployed_b = container.evolution.harness_registry.rehearse(record.version)
    run_id = f"REPLAY-{uuid4().hex[:8]}"
    episode_a = await container.runner.run_episode(
        scenario,
        attack.genome,
        deployed_a.version,
        run_id=run_id,
        generation=attack.genome.generation,
        episode_id=f"EP-{run_id}-A",
        event_sink=lambda event: _save_replay_event(container, event),
        deployed=deployed_a,
    )
    episode_b = await container.runner.run_episode(
        scenario,
        attack.genome,
        deployed_b.version,
        run_id=run_id,
        generation=attack.genome.generation,
        episode_id=f"EP-{run_id}-B",
        event_sink=lambda event: _save_replay_event(container, event),
        deployed=deployed_b,
    )
    await container.repository.save_episode(episode_a)
    await container.repository.save_episode(episode_b)
    return {
        "run_id": run_id,
        "same_attack": episode_a.attack_id == episode_b.attack_id,
        "different_outcome": episode_a.attack_success != episode_b.attack_success,
        "harness_a": {
            "harness": deployed_a.version.model_dump(mode="json"),
            "episode": episode_a.model_dump(mode="json"),
        },
        "harness_b": {
            "harness": deployed_b.version.model_dump(mode="json"),
            "episode": episode_b.model_dump(mode="json"),
        },
    }


async def _get_harness_version(container: AppContainer, harness_id: str) -> HarnessVersion:
    record = await container.repository.get_harness(harness_id)
    if record is None:
        raise HTTPException(status_code=404, detail="harness not found")
    return record.version


@router.post("/replay")
async def replay_battle(
    request: ReplayRequest,
    container: AppContainer = Depends(require_writable),
) -> dict[str, object]:
    attack = await container.repository.get_attack(request.attack_id)
    defense = await container.repository.get_defense(request.defense_id)
    if attack is None:
        raise HTTPException(status_code=404, detail="attack not found")
    if defense is None:
        raise HTTPException(status_code=404, detail="defense not found")
    try:
        scenario = container.catalog.get(request.scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="scenario not found") from exc
    run_id = f"REPLAY-{uuid4().hex[:8]}"
    episode = await container.runner.run_episode(
        scenario,
        attack.genome,
        defense.genome,
        run_id=run_id,
        generation=attack.genome.generation,
        episode_id=f"EP-{run_id}",
        event_sink=lambda event: _save_replay_event(container, event),
    )
    await container.repository.save_episode(episode)
    return episode.model_dump(mode="json")


async def _save_replay_event(container: AppContainer, event: object) -> None:
    # Replay emits the same typed event stream as live battles.
    from app.models.events import ArenaEvent

    if isinstance(event, ArenaEvent):
        await container.repository.save_event(event)
        await container.event_bus.publish(event)
