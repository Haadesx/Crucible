"""``memory_retrieved`` provenance: the recall that fed Blue must be visible and honest.

Frozen contract (frontend/src/types.ts): type="memory_retrieved", payload={"count": int,
"backend": "atlas"|"local", "memories": [{"memory_id", "similarity", "run_id",
"generation", "attack_family", "patch_id", "outcome"}]}. Retrieval spans every run, so a
prior run's failure can teach this generation; the event reports the search as it
happened, while Blue still receives the current breaches when nothing was recalled.
"""

from datetime import UTC, datetime
from typing import Any

from app.coevolution.blue_search import _patch_followed
from app.coevolution.engine import CoevolutionEngine
from app.events import ArenaEventBus
from app.memory.repository import InMemoryRepository
from app.memory.vector import HashEmbedding, VectorMemory
from app.models.blue import HarnessOperation, HarnessPatch, HarnessPatchRecord
from app.models.episode import Episode
from app.models.memory import FailureMemory
from app.models.red import AttackCandidate
from app.scenarios.loader import ScenarioCatalog
from tests.test_coevolution import BlueScript, RedScript, _engine, _provider

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
PRIOR_RUN = "T-PRIOR"
CURRENT_RUN = "T-CURRENT"
SUMMARY = "Breach on DOC-001 by GN-A-T-PRIOR-G04-abc: ['send_email'] executed with attacker payload"
RECALLED_FIELDS = {
    "memory_id",
    "similarity",
    "run_id",
    "generation",
    "attack_family",
    "patch_id",
    "outcome",
}


def _memory(**overrides: Any) -> FailureMemory:
    values: dict[str, Any] = {
        "id": f"MEM-{PRIOR_RUN}-G04-abcd1234",
        "run_id": PRIOR_RUN,
        "episode_id": "EP-T-PRIOR-G04-breach",
        "type": "breach",
        "summary": SUMMARY,
        "attack_id": "GN-A-T-PRIOR-G04-abc",
        "defense_id": "B-T-PRIOR-G00-B0",
        "created_at": NOW,
    }
    values.update(overrides)
    return FailureMemory(**values)


def _episode(memory: FailureMemory, generation: int) -> Episode:
    return Episode(
        id=memory.episode_id,
        run_id=memory.run_id,
        generation=generation,
        attack_id=memory.attack_id,
        defense_id=memory.defense_id,
        scenario_id="DOC-001",
        user_prompt="",
        attack_payload="",
        attack_success=True,
        legitimate_task_success=False,
        security_score=0.0,
        utility_score=1.0,
        latency_ms=1,
        model_calls=1,
        created_at=NOW,
    )


def _candidate(attack_id: str, family: str) -> AttackCandidate:
    return AttackCandidate(
        id=attack_id.removeprefix("GN-"),
        run_id=PRIOR_RUN,
        red_agent_version_id="R-T-PRIOR-G00-001",
        scenario_id="DOC-001",
        attack_family=family,
        carrier="document",
        target_capability="exfiltrate via send_email",
        payload="injected directive",
        generated_by_model="test-red-model",
        generation=4,
        created_at=NOW,
    )


def _patch_record(defense_id: str, status: str = "REJECTED") -> HarnessPatchRecord:
    return HarnessPatchRecord(
        id="PATCH-T-PRIOR-G04-1",
        run_id=PRIOR_RUN,
        generation=5,
        parent_harness_id=defense_id,
        child_harness_id="B-T-PRIOR-G05-C1",
        patch=HarnessPatch(
            analysis="bind tools to the user goal before execution",
            operations=[
                HarnessOperation(op="ADD_STAGE", target="GoalBinding", value=None, reason="bind the goal")
            ],
            expected_effect="document-sourced email proposals are denied",
        ),
        status=status,  # type: ignore[arg-type]
        created_at=NOW,
    )


def _engine_without_providers(repository: InMemoryRepository) -> CoevolutionEngine:
    return CoevolutionEngine(
        repository,
        VectorMemory(repository, HashEmbedding(64), use_atlas_vector_search=False),
        ScenarioCatalog(),
        red_provider=None,
        blue_provider=None,
        test_mode=True,
        event_bus=ArenaEventBus(),
    )


async def test_memory_retrieved_event_carries_prior_run_provenance() -> None:
    repository = InMemoryRepository()
    await repository.start()
    prior = _memory()
    await repository.save_episode(_episode(prior, generation=4))
    await repository.save_attack_candidate(_candidate(prior.attack_id, "context_poisoning"))
    await repository.save_failure(prior)
    await repository.save_patch_record(_patch_record(prior.defense_id))
    engine = _engine_without_providers(repository)

    breach = _memory(
        id=f"MEM-{CURRENT_RUN}-G00-feedface",
        run_id=CURRENT_RUN,
        episode_id="EP-T-CURRENT-G00-breach",
        defense_id="B-T-CURRENT-G00-B0",
    )

    retrieved = await engine._retrieve_memories_for_blue(
        [breach], run_id=CURRENT_RUN, generation=1, patch_history=[]
    )

    assert [memory.id for memory in retrieved] == [prior.id], "prior-run recall was not surfaced"
    events = [event for event in await repository.recent_events() if event.type == "memory_retrieved"]
    assert len(events) == 1
    event = events[0]
    assert event.run_id == CURRENT_RUN, "the event must belong to the retrieving run"
    assert event.generation == 1, "retrieval serves the engineering generation (breach + 1)"
    assert event.payload["count"] == 1
    assert event.payload["backend"] == "local"

    recalled = event.payload["memories"]
    assert isinstance(recalled, list) and len(recalled) == 1
    row = recalled[0]
    assert set(row) == RECALLED_FIELDS
    assert row["memory_id"] == prior.id
    assert row["run_id"] == PRIOR_RUN, "the source run must be the prior run, not the retriever"
    assert row["generation"] == 4
    assert row["attack_family"] == "context_poisoning"
    assert row["patch_id"] == "PATCH-T-PRIOR-G04-1"
    assert row["outcome"] == "REJECTED"
    assert row["similarity"] >= 0.99, "an identical summary must score near 1.0"


async def test_memory_retrieved_event_is_empty_and_truthful_when_nothing_matches() -> None:
    repository = InMemoryRepository()
    await repository.start()
    engine = _engine_without_providers(repository)
    breach = _memory(
        id="MEM-T-EMPTY-G00-1",
        run_id="T-EMPTY",
        episode_id="EP-T-EMPTY-G00-breach",
        defense_id="B-T-EMPTY-G00-B0",
        summary="Breach on DOC-001 by GN-A-T-EMPTY-G00-1: ['send_email'] executed with attacker payload",
    )

    retrieved = await engine._retrieve_memories_for_blue(
        [breach], run_id="T-EMPTY", generation=1, patch_history=[]
    )

    assert [memory.id for memory in retrieved] == [breach.id], "Blue must still receive the current breach"
    events = [event for event in await repository.recent_events() if event.type == "memory_retrieved"]
    assert len(events) == 1
    assert events[0].payload == {
        "run_id": "T-EMPTY",
        "count": 0,
        "backend": "local",
        "memories": [],
    }


class _AtlasStub:
    """A Mongo-shaped repository whose vector index returns one prior-run memory."""

    backend = "mongodb"

    def __init__(self, failure: FailureMemory) -> None:
        self.failure = failure
        self.calls: list[tuple[str, str, int]] = []

    async def vector_search(
        self, collection: str, index_name: str, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        self.calls.append((collection, index_name, limit))
        return [{"_id": self.failure.id, "score": 0.91}]

    async def get_failure(self, failure_id: str) -> FailureMemory | None:
        return self.failure if failure_id == self.failure.id else None

    async def list_failures(self, run_id: str | None = None, limit: int = 50) -> list[FailureMemory]:
        raise AssertionError("Atlas recall must not silently fall back to the local scan")


async def test_atlas_recall_offers_prior_run_memories_without_a_local_substitute() -> None:
    prior = _memory()
    stub = _AtlasStub(prior)
    vectors = VectorMemory(stub, HashEmbedding(64), use_atlas_vector_search=True, strict_atlas=True)  # type: ignore[arg-type]

    matches = await vectors.similar_failures("query text", limit=5)

    assert [memory.run_id for memory in matches] == [PRIOR_RUN], "the Atlas query is not run-scoped"
    assert matches[0].similarity == 0.91
    assert vectors.observed_retrieval_backend == "atlas"
    assert stub.calls == [("memories", "memory_embedding_index", 5)]


async def test_engine_run_emits_memory_retrieved_with_ids_and_scores() -> None:
    red = _provider("RED", "test-red-model", RedScript())
    blue = _provider("BLUE", "test-blue-model", BlueScript())
    engine, repository = await _engine(red, blue)

    await engine.run(run_id="T-MEM-E2E", generations=1, red_versions=1, attacks_per_version=1, blue_candidates=1)

    events = [event for event in await repository.recent_events() if event.type == "memory_retrieved"]
    assert events, "the engine never recorded what Blue was shown"
    event = events[0]
    assert event.run_id == "T-MEM-E2E"
    assert event.payload["backend"] == "local"
    assert event.payload["count"] >= 1
    recalled = event.payload["memories"]
    assert isinstance(recalled, list) and recalled
    for row in recalled:
        assert set(row) == RECALLED_FIELDS
        assert row["memory_id"]
        assert row["run_id"] == "T-MEM-E2E"
        assert float(row["similarity"]) > 0.0


async def test_recalled_prior_run_memory_carries_its_patch_outcome_into_blue_context() -> None:
    repository = InMemoryRepository()
    await repository.start()
    prior = _memory()
    await repository.save_patch_record(_patch_record(prior.defense_id))
    engine = _engine_without_providers(repository)

    annotated = await engine._annotate_failure_history([prior], [], run_id=CURRENT_RUN)

    assert len(annotated) == 1
    analysis = annotated[0].analysis
    assert analysis is not None, "a remembered failure with a known patch must be annotated"
    assert analysis.historical_match_ids == ["PATCH-T-PRIOR-G04-1"]
    assert analysis.historical_patch_outcome == "REJECTED"
    line = _patch_followed(analysis)
    assert "PATCH-T-PRIOR-G04-1 (REJECTED)" in line, "the engineer must see how the prior fix turned out"
    assert "ADD_STAGE GoalBinding" in line, "the engineer must see what the prior fix proposed"


async def test_a_second_run_recalls_the_first_runs_failure_end_to_end() -> None:
    red = _provider("RED", "test-red-model", RedScript())
    blue = _provider("BLUE", "test-blue-model", BlueScript())
    engine, repository = await _engine(red, blue)
    await engine.run(run_id="T-MEM-PRIOR", generations=1, red_versions=1, attacks_per_version=1, blue_candidates=1)

    later, _ = await _engine(
        _provider("RED", "test-red-model", RedScript()),
        _provider("BLUE", "test-blue-model", BlueScript()),
        repository,
    )
    await later.run(run_id="T-MEM-LATER", generations=1, red_versions=1, attacks_per_version=1, blue_candidates=1)

    events = [
        event
        for event in await repository.recent_events()
        if event.type == "memory_retrieved" and event.run_id == "T-MEM-LATER"
    ]
    assert events, "the later run emitted no recall event"
    sources = {row["run_id"] for event in events for row in event.payload["memories"]}
    assert "T-MEM-PRIOR" in sources, "a prior run's failure was not recallable"
    assert "T-MEM-LATER" in sources, "the current run's own failure is missing from the recall"

