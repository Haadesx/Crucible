from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_container
from app.coevolution.matrix import build_matrix
from app.dependencies import AppContainer
from app.models.generation import GenerationRecord

router = APIRouter(tags=["lineage"])


@router.get("/generations", response_model=list[GenerationRecord])
async def list_generations(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> list[GenerationRecord]:
    return await container.repository.list_generations(run_id)


@router.get("/generations/{generation}", response_model=GenerationRecord)
async def get_generation(
    generation: int,
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> GenerationRecord:
    record = await container.repository.get_generation(generation, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="generation not found")
    return record


@router.get("/harnesses")
async def list_harnesses(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    records = await container.repository.list_harnesses(run_id)
    return [record.model_dump(mode="json") for record in records]


@router.get("/harnesses/active")
async def get_active_harness(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    """The champion for this run, straight from the registry that owns the answer.

    Reading the raw pointer here made this the one surface where a rejected harness
    could be announced as active while the engine measuring the same run called a
    different harness the champion. Pass ``run_id`` to ask about one run; without it
    the most recently promoted harness wins across runs.
    """

    champion = await container.evolution.harness_registry.champion(run_id)
    if champion is None:
        raise HTTPException(status_code=404, detail="active harness not found")
    record = await container.repository.get_harness(champion.id)
    if record is None:
        raise HTTPException(status_code=404, detail="active harness not found")
    return record.model_dump(mode="json")


@router.get("/harnesses/{harness_id}")
async def get_harness(
    harness_id: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    record = await container.repository.get_harness(harness_id)
    if record is None:
        raise HTTPException(status_code=404, detail="harness not found")
    return record.model_dump(mode="json")


@router.get("/harnesses/{harness_id}/failures")
async def get_harness_failures(
    harness_id: str,
    limit: int = 50,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    record = await container.repository.get_harness(harness_id)
    if record is None:
        raise HTTPException(status_code=404, detail="harness not found")
    failures = [
        failure
        for failure in await container.repository.list_failures(limit=200)
        if failure.analysis is not None and failure.analysis.harness_id == harness_id
    ]
    return [failure.model_dump(mode="json") for failure in failures[: min(max(limit, 1), 200)]]


@router.get("/harnesses/{from_id}/diff/{to_id}")
async def get_harness_diff(
    from_id: str,
    to_id: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    diff = await container.repository.get_harness_diff(from_id, to_id)
    if diff is None:
        raise HTTPException(status_code=404, detail="harness diff not found")
    return diff.model_dump(mode="json")


@router.get("/attacks/{attack_id}")
async def get_attack(attack_id: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    record = await container.repository.get_attack(attack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="attack not found")
    return record.model_dump(mode="json")


@router.get("/defenses/{defense_id}")
async def get_defense(defense_id: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    record = await container.repository.get_defense(defense_id)
    if record is None:
        raise HTTPException(status_code=404, detail="defense not found")
    return record.model_dump(mode="json")


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    episode = await container.repository.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode.model_dump(mode="json")


@router.get("/scenarios")
async def get_scenarios(container: AppContainer = Depends(get_container)) -> list[dict[str, object]]:
    return [scenario.model_dump(mode="json") for scenario in container.catalog.all()]


# --------------------------------------------------------------------------- #
# Evolving-agent truth: who Red and Blue actually were in each generation, and
# the concrete attack candidates those agents authored. The canvas needs these
# to label its Red/Blue nodes with runtime metadata instead of hard-coded names.
# --------------------------------------------------------------------------- #


@router.get("/red-versions")
async def list_red_versions(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    versions = await container.repository.list_red_versions(run_id)
    versions.sort(key=lambda version: (version.generation, version.created_at))
    return [version.model_dump(mode="json") for version in versions]


@router.get("/blue-versions")
async def list_blue_versions(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    versions = await container.repository.list_blue_versions(run_id)
    versions.sort(key=lambda version: (version.generation, version.created_at))
    return [version.model_dump(mode="json") for version in versions]


@router.get("/attack-candidates")
async def list_attack_candidates(
    run_id: str | None = None,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    candidates = await container.repository.list_attack_candidates(run_id)
    candidates.sort(key=lambda candidate: (candidate.generation, candidate.created_at))
    return [candidate.model_dump(mode="json") for candidate in candidates]


@router.get("/memory/failures")
async def get_failures(
    run_id: str | None = None,
    limit: int = 50,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    failures = await container.repository.list_failures(run_id, min(max(limit, 1), 200))
    return [failure.model_dump(mode="json") for failure in failures]


# --------------------------------------------------------------------------- #
# Observer truth: what actually persisted, and where it actually lives.
# These endpoints exist so the dashboard can show the engine's real artifacts
# (generations, episodes, model calls, patches) and state the persistence
# backend honestly instead of implying the Atlas sandbox is connected.
# --------------------------------------------------------------------------- #

MAX_PAGE = 200
MAX_MODEL_CALL_PAGE = 2_000


def _page_limit(limit: int, maximum: int) -> int:
    return min(max(limit, 1), maximum)


@dataclass
class _RunTally:
    run_id: str
    generations: int = 0
    episodes: int = 0
    model_calls: int = 0
    patches: int = 0
    has_report: bool = False
    last_activity: datetime | None = None

    def touch(self, when: datetime) -> None:
        if self.last_activity is None or when > self.last_activity:
            self.last_activity = when

    def as_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "generations": self.generations,
            "episodes": self.episodes,
            "model_calls": self.model_calls,
            "patches": self.patches,
            "has_report": self.has_report,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


async def _latest_run_id(container: AppContainer) -> str | None:
    """The run with the most recent persisted activity, or None when nothing exists."""

    latest: tuple[datetime, str] | None = None
    for episode in await container.repository.list_episodes():
        if latest is None or episode.created_at > latest[0]:
            latest = (episode.created_at, episode.run_id)
    return latest[1] if latest is not None else None


@router.get("/system/status")
async def system_status(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    """The run mode and persistence truth the observer is allowed to claim.

    An in-memory DEV run must never be presented as the Atlas sandbox, so this is the
    single place the frontend reads that verdict from.
    """

    settings = container.settings
    repository = container.repository
    mongodb_connected = repository.backend == "mongodb"
    uri = settings.mongodb_uri or ""
    atlas_connected = mongodb_connected and ("mongodb.net" in uri or uri.startswith("mongodb+srv"))
    if atlas_connected:
        label = "ATLAS CONNECTED"
    elif mongodb_connected:
        label = "MONGODB LOCAL / ATLAS NOT CONNECTED"
    elif repository.backend == "dev_snapshot":
        label = "DEV / ATLAS NOT CONNECTED (durable snapshot)"
    else:
        label = "DEV / ATLAS NOT CONNECTED (in-memory)"
    return {
        "run_mode": settings.effective_run_mode,
        # The repository owns the capability; the API only reports it. The UI must not
        # infer read-only from a filename or a run id.
        "read_only": bool(getattr(repository, "read_only", False)),
        "persistence": {
            "backend": repository.backend,
            "mongodb_connected": mongodb_connected,
            "atlas_connected": atlas_connected,
            "database": settings.mongodb_database,
            "label": label,
        },
        "vector_search": {
            "configured": container.vector_memory.retrieval_backend,
            "observed": container.vector_memory.observed_retrieval_backend,
        },
        "latest_run_id": await _latest_run_id(container),
    }


@router.get("/runs")
async def list_runs(container: AppContainer = Depends(get_container)) -> list[dict[str, object]]:
    """Every run this repository can actually see, with its persisted artifact counts.

    Counts come from the same collections the engine writes, so an empty list means
    nothing was persisted in this process's backend, not that the run is hidden.
    """

    repository = container.repository
    tallies: dict[str, _RunTally] = {}

    def tally(run_id: str) -> _RunTally:
        return tallies.setdefault(run_id, _RunTally(run_id=run_id))

    for generation in await repository.list_generations():
        entry = tally(generation.run_id)
        entry.generations += 1
        entry.touch(generation.created_at)
    for episode in await repository.list_episodes():
        entry = tally(episode.run_id)
        entry.episodes += 1
        entry.touch(episode.created_at)
    for call in await repository.list_model_calls(limit=MAX_MODEL_CALL_PAGE):
        entry = tally(call.run_id)
        entry.model_calls += 1
        entry.touch(call.created_at)
    for patch in await repository.list_patch_records():
        entry = tally(patch.run_id)
        entry.patches += 1
        entry.touch(patch.created_at)
    for entry in tallies.values():
        entry.has_report = (await repository.get_run_report(entry.run_id)) is not None
    return [
        entry.as_payload()
        for entry in sorted(
            tallies.values(),
            key=lambda entry: entry.last_activity or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
    ]


@router.get("/episodes")
async def list_episodes(
    run_id: str | None = None,
    limit: int = 50,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    """Newest persisted episodes first, for the observer's evidence panel."""

    episodes = await container.repository.list_episodes(run_id)
    episodes.sort(key=lambda episode: episode.created_at, reverse=True)
    return [episode.model_dump(mode="json") for episode in episodes[: _page_limit(limit, MAX_PAGE)]]


@router.get("/model-calls")
async def list_model_calls(
    run_id: str | None = None,
    limit: int = 100,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    """Newest persisted inference calls first; the ledger proof that models ran."""

    calls = await container.repository.list_model_calls(run_id, limit=MAX_MODEL_CALL_PAGE)
    calls.sort(key=lambda call: call.created_at, reverse=True)
    return [call.model_dump(mode="json") for call in calls[: _page_limit(limit, MAX_MODEL_CALL_PAGE)]]


@router.get("/patches")
async def list_patches(
    run_id: str | None = None,
    limit: int = 50,
    container: AppContainer = Depends(get_container),
) -> list[dict[str, object]]:
    """Newest persisted Blue patch records first, including their lifecycle status."""

    patches = await container.repository.list_patch_records(run_id)
    patches.sort(key=lambda record: record.created_at, reverse=True)
    return [record.model_dump(mode="json") for record in patches[: _page_limit(limit, MAX_PAGE)]]


@router.get("/runs/{run_id}/report")
async def get_run_report(run_id: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    report = await container.repository.get_run_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="run report not found")
    return report.model_dump(mode="json")


@router.get("/runs/{run_id}/matrix")
async def get_run_matrix(run_id: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    """Version x Test matrix for one run, derived from persisted evidence only."""

    return await build_matrix(container.repository, run_id)
