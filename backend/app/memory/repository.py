from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel

from app.models.attack import AttackRecord
from app.models.audit import HallOfFameEntry, ModelCall, RunReport, new_model_call_id
from app.models.blue import BlueAgentVersion, HarnessPatchRecord
from app.models.defense import DefenseRecord
from app.models.episode import Episode
from app.models.events import ArenaEvent
from app.models.generation import GenerationRecord
from app.models.harness import HarnessDiff, HarnessRecord
from app.models.memory import FailureMemory
from app.models.red import AttackCandidate, RedAgentVersion
from app.models.scenario import Scenario


class DuplicateRecordIdError(RuntimeError):
    """Raised when a record id is already present.

    Mirrors MongoDB's ``DuplicateKeyError`` for the in-memory adapter, so the same
    contract (ids are unique keys, duplicates are rejected, not silently appended)
    holds with or without a live cluster.
    """


class RepositoryReadOnlyError(RuntimeError):
    """Raised when a write is attempted against a read-only repository.

    A snapshot-backed adapter served to an observer is evidence and must not be
    mutated; the co-evolution CLI and an explicitly opted-in live demo pass
    ``read_only=False``.
    """


READ_ONLY_DETAIL = (
    "Repository is read-only: this server is serving a snapshot-backed evidence store. "
    "Writes are refused to keep the evidence unmodified. Set ALLOW_SNAPSHOT_WRITES=true "
    "to enable writes for a dedicated live snapshot."
)


class MemoryRepository(Protocol):
    backend: str

    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...
    async def ensure_indexes(self) -> None: ...
    async def save_scenarios(self, scenarios: list[Scenario]) -> None: ...
    async def save_attack(self, record: AttackRecord) -> None: ...
    async def save_defense(self, record: DefenseRecord) -> None: ...
    async def save_episode(self, episode: Episode) -> None: ...
    async def save_generation(self, generation: GenerationRecord) -> None: ...
    async def save_failure(self, failure: FailureMemory) -> None: ...
    async def save_event(self, event: ArenaEvent) -> None: ...
    async def save_harness(self, record: HarnessRecord) -> None: ...
    async def get_harness(self, harness_id: str) -> HarnessRecord | None: ...
    async def list_harnesses(self, run_id: str | None = None) -> list[HarnessRecord]: ...
    async def save_harness_diff(self, diff: HarnessDiff) -> None: ...
    async def get_harness_diff(self, from_version: str, to_version: str) -> HarnessDiff | None: ...
    async def set_active_harness(self, run_id: str, harness_id: str) -> None: ...
    async def get_active_harness(self, run_id: str | None = None) -> HarnessRecord | None: ...
    async def get_attack(self, attack_id: str) -> AttackRecord | None: ...
    async def get_defense(self, defense_id: str) -> DefenseRecord | None: ...
    async def get_episode(self, episode_id: str) -> Episode | None: ...
    async def list_episodes(self, run_id: str | None = None) -> list[Episode]: ...
    async def get_generation(
        self, generation: int, run_id: str | None = None
    ) -> GenerationRecord | None: ...
    async def list_generations(self, run_id: str | None = None) -> list[GenerationRecord]: ...
    async def list_attacks(self, run_id: str | None = None) -> list[AttackRecord]: ...
    async def list_defenses(self, run_id: str | None = None) -> list[DefenseRecord]: ...
    async def list_failures(self, run_id: str | None = None, limit: int = 50) -> list[FailureMemory]: ...
    async def get_failure(self, failure_id: str) -> FailureMemory | None: ...
    async def save_red_version(self, version: RedAgentVersion) -> None: ...
    async def get_red_version(self, version_id: str) -> RedAgentVersion | None: ...
    async def list_red_versions(self, run_id: str | None = None) -> list[RedAgentVersion]: ...
    async def save_blue_version(self, version: BlueAgentVersion) -> None: ...
    async def list_blue_versions(self, run_id: str | None = None) -> list[BlueAgentVersion]: ...
    async def save_attack_candidate(self, candidate: AttackCandidate) -> None: ...
    async def get_attack_candidate(self, candidate_id: str) -> AttackCandidate | None: ...
    async def list_attack_candidates(self, run_id: str | None = None) -> list[AttackCandidate]: ...
    async def save_patch_record(self, record: HarnessPatchRecord) -> None: ...
    async def list_patch_records(self, run_id: str | None = None) -> list[HarnessPatchRecord]: ...
    async def save_model_call(self, call: ModelCall) -> ModelCall: ...
    async def list_model_calls(self, run_id: str | None = None, limit: int = 2_000) -> list[ModelCall]: ...
    async def save_hof_entry(self, entry: HallOfFameEntry) -> None: ...
    async def list_hof(self, kind: str | None = None, limit: int = 20) -> list[HallOfFameEntry]: ...
    async def save_run_report(self, report: RunReport) -> None: ...
    async def get_run_report(self, run_id: str) -> RunReport | None: ...
    async def vector_search(
        self,
        collection: str,
        index_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...
    async def recent_events(self, limit: int = 100) -> list[ArenaEvent]: ...
    async def reset(self) -> None: ...


class InMemoryRepository:
    """Fully functional persistence adapter used when MONGODB_URI is absent."""

    backend = "memory"

    _record_types: ClassVar[dict[str, type[BaseModel]]] = {
        "scenarios": Scenario,
        "attacks": AttackRecord,
        "defenses": DefenseRecord,
        "episodes": Episode,
        "generations": GenerationRecord,
        "failures": FailureMemory,
        "harnesses": HarnessRecord,
        "harness_diffs": HarnessDiff,
        "red_versions": RedAgentVersion,
        "blue_versions": BlueAgentVersion,
        "attack_candidates": AttackCandidate,
        "patch_records": HarnessPatchRecord,
        "hof": HallOfFameEntry,
        "run_reports": RunReport,
    }

    def __init__(self, snapshot_path: str | Path | None = None, *, read_only: bool | None = None) -> None:
        self.snapshot_path = Path(snapshot_path) if snapshot_path is not None else None
        if self.snapshot_path is not None:
            self.backend = "dev_snapshot"
        # A snapshot-backed adapter is evidence by default: observer servers must not be
        # able to write it. Writers that own the snapshot (the co-evolution CLI, an
        # opted-in live demo) pass read_only=False; a plain in-memory adapter stays writable.
        self.read_only = (self.snapshot_path is not None) if read_only is None else read_only
        self.scenarios: dict[str, Scenario] = {}
        self.attacks: dict[str, AttackRecord] = {}
        self.defenses: dict[str, DefenseRecord] = {}
        self.episodes: dict[str, Episode] = {}
        self.generations: dict[tuple[str, int], GenerationRecord] = {}
        self.failures: dict[str, FailureMemory] = {}
        self.harnesses: dict[str, HarnessRecord] = {}
        self.harness_diffs: dict[tuple[str, str], HarnessDiff] = {}
        # The active-harness pointer is per run. A single global pointer let two runs
        # sharing one repository overwrite each other's champion.
        self.active_harnesses: dict[str, str] = {}
        self.events: deque[ArenaEvent] = deque(maxlen=1_000)
        self.red_versions: dict[str, RedAgentVersion] = {}
        self.blue_versions: dict[str, BlueAgentVersion] = {}
        self.attack_candidates: dict[str, AttackCandidate] = {}
        self.patch_records: dict[str, HarnessPatchRecord] = {}
        self.model_calls: list[ModelCall] = []
        self.hof: dict[str, HallOfFameEntry] = {}
        self.run_reports: dict[str, RunReport] = {}

    async def start(self) -> None:
        if self.snapshot_path is not None and self.snapshot_path.exists():
            state = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            if state.get("version") != 1:
                raise ValueError("unsupported DEV snapshot version")
            restored = {
                name: {
                    tuple(key) if isinstance(key, list) else key: model.model_validate(value)
                    for key, value in state[name]
                }
                for name, model in self._record_types.items()
            }
            events = deque((ArenaEvent.model_validate(item) for item in state["events"]), maxlen=1_000)
            model_calls = [ModelCall.model_validate(item) for item in state["model_calls"]]
            for name, records in restored.items():
                setattr(self, name, records)
            self.active_harnesses = dict(state["active_harnesses"])
            self.events = events
            self.model_calls = model_calls
        return None

    def _ensure_writable(self) -> None:
        if self.read_only:
            raise RepositoryReadOnlyError(READ_ONLY_DETAIL)

    def _persist(self) -> None:
        # Every mutating method funnels through here, so this is the single write gate.
        self._ensure_writable()
        path = self.snapshot_path
        if path is None:
            return
        state = {
            "version": 1,
            **{
                name: [
                    [list(key) if isinstance(key, tuple) else key, record.model_dump(mode="json")]
                    for key, record in getattr(self, name).items()
                ]
                for name in self._record_types
            },
            "active_harnesses": self.active_harnesses,
            "events": [event.model_dump(mode="json") for event in self.events],
            "model_calls": [call.model_dump(mode="json") for call in self.model_calls],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def ensure_indexes(self) -> None:
        return None

    async def save_scenarios(self, scenarios: list[Scenario]) -> None:
        self.scenarios = {scenario.id: scenario.model_copy(deep=True) for scenario in scenarios}
        self._persist()

    async def save_attack(self, record: AttackRecord) -> None:
        self.attacks[record.genome.id] = record.model_copy(deep=True)
        self._persist()

    async def save_defense(self, record: DefenseRecord) -> None:
        self.defenses[record.genome.id] = record.model_copy(deep=True)
        self._persist()

    async def save_episode(self, episode: Episode) -> None:
        self.episodes[episode.id] = episode.model_copy(deep=True)
        self._persist()

    async def save_generation(self, generation: GenerationRecord) -> None:
        self.generations[(generation.run_id, generation.id)] = generation.model_copy(deep=True)
        self._persist()

    async def save_failure(self, failure: FailureMemory) -> None:
        self.failures[failure.id] = failure.model_copy(deep=True)
        self._persist()

    async def save_event(self, event: ArenaEvent) -> None:
        self.events.append(event.model_copy(deep=True))
        self._persist()

    async def save_harness(self, record: HarnessRecord) -> None:
        self.harnesses[record.version.id] = record.model_copy(deep=True)
        self._persist()

    async def get_harness(self, harness_id: str) -> HarnessRecord | None:
        record = self.harnesses.get(harness_id)
        return record.model_copy(deep=True) if record else None

    async def list_harnesses(self, run_id: str | None = None) -> list[HarnessRecord]:
        records = [
            record
            for record in self.harnesses.values()
            if run_id is None or record.version.id.startswith(f"B-{run_id}-") or record.version.id == run_id
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: (record.version.generation, record.version.id))

    async def save_harness_diff(self, diff: HarnessDiff) -> None:
        self.harness_diffs[(diff.from_version, diff.to_version)] = diff.model_copy(deep=True)
        self._persist()

    async def get_harness_diff(self, from_version: str, to_version: str) -> HarnessDiff | None:
        diff = self.harness_diffs.get((from_version, to_version))
        return diff.model_copy(deep=True) if diff else None

    async def set_active_harness(self, run_id: str, harness_id: str) -> None:
        self.active_harnesses[run_id] = harness_id
        self._persist()

    async def get_active_harness(self, run_id: str | None = None) -> HarnessRecord | None:
        if run_id is None:
            if not self.active_harnesses:
                return None
            run_id = next(reversed(self.active_harnesses))
        return await self.get_harness(self.active_harnesses[run_id])

    async def get_attack(self, attack_id: str) -> AttackRecord | None:
        record = self.attacks.get(attack_id)
        return record.model_copy(deep=True) if record else None

    async def get_defense(self, defense_id: str) -> DefenseRecord | None:
        record = self.defenses.get(defense_id)
        return record.model_copy(deep=True) if record else None

    async def list_episodes(self, run_id: str | None = None) -> list[Episode]:
        records = [
            episode
            for episode in self.episodes.values()
            if run_id is None or episode.run_id == run_id
        ]
        return sorted(
            (deepcopy(episode) for episode in records),
            key=lambda episode: (episode.created_at, episode.id),
        )

    async def get_episode(self, episode_id: str) -> Episode | None:
        episode = self.episodes.get(episode_id)
        return episode.model_copy(deep=True) if episode else None

    async def get_generation(
        self, generation: int, run_id: str | None = None
    ) -> GenerationRecord | None:
        if run_id is not None:
            record = self.generations.get((run_id, generation))
            return record.model_copy(deep=True) if record else None
        matches = [record for (stored_run, _), record in self.generations.items() if _ == generation]
        if not matches:
            return None
        return deepcopy(max(matches, key=lambda record: record.created_at))

    async def list_generations(self, run_id: str | None = None) -> list[GenerationRecord]:
        records = [
            record
            for (stored_run, _), record in self.generations.items()
            if run_id is None or stored_run == run_id
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: record.id)

    async def list_attacks(self, run_id: str | None = None) -> list[AttackRecord]:
        records = [
            record
            for record in self.attacks.values()
            if run_id is None or record.genome.id.startswith(f"R-{run_id}-")
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: record.genome.id)

    async def list_defenses(self, run_id: str | None = None) -> list[DefenseRecord]:
        records = [
            record
            for record in self.defenses.values()
            if run_id is None or record.genome.id.startswith(f"B-{run_id}-")
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: record.genome.id)

    async def get_failure(self, failure_id: str) -> FailureMemory | None:
        record = self.failures.get(failure_id)
        return record.model_copy(deep=True) if record else None

    async def vector_search(
        self,
        collection: str,
        index_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        del index_name, query_vector
        if collection == "attacks":
            return [
                {"_id": record.genome.id, "embedding": record.embedding}
                for record in list(self.attacks.values())[:limit]
            ]
        if collection == "memories":
            return [
                {"_id": record.id, "embedding": record.embedding}
                for record in list(self.failures.values())[:limit]
            ]
        return []

    async def list_failures(self, run_id: str | None = None, limit: int = 50) -> list[FailureMemory]:
        records = [
            record
            for record in self.failures.values()
            if run_id is None or record.run_id == run_id
        ]
        return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]

    async def save_red_version(self, version: RedAgentVersion) -> None:
        self.red_versions[version.id] = version.model_copy(deep=True)
        self._persist()

    async def get_red_version(self, version_id: str) -> RedAgentVersion | None:
        version = self.red_versions.get(version_id)
        return version.model_copy(deep=True) if version else None

    async def list_red_versions(self, run_id: str | None = None) -> list[RedAgentVersion]:
        records = [
            version
            for version in self.red_versions.values()
            if run_id is None or version.run_id == run_id
        ]
        return sorted((deepcopy(version) for version in records), key=lambda version: (version.generation, version.id))

    async def save_blue_version(self, version: BlueAgentVersion) -> None:
        self.blue_versions[version.id] = version.model_copy(deep=True)
        self._persist()

    async def list_blue_versions(self, run_id: str | None = None) -> list[BlueAgentVersion]:
        records = [
            version
            for version in self.blue_versions.values()
            if run_id is None or version.run_id == run_id
        ]
        return sorted((deepcopy(version) for version in records), key=lambda version: (version.generation, version.id))

    async def save_attack_candidate(self, candidate: AttackCandidate) -> None:
        self.attack_candidates[candidate.id] = candidate.model_copy(deep=True)
        self._persist()

    async def get_attack_candidate(self, candidate_id: str) -> AttackCandidate | None:
        candidate = self.attack_candidates.get(candidate_id)
        return candidate.model_copy(deep=True) if candidate else None

    async def list_attack_candidates(self, run_id: str | None = None) -> list[AttackCandidate]:
        records = [
            candidate
            for candidate in self.attack_candidates.values()
            if run_id is None or candidate.run_id == run_id
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: record.created_at)

    async def save_patch_record(self, record: HarnessPatchRecord) -> None:
        self.patch_records[record.id] = record.model_copy(deep=True)
        self._persist()

    async def list_patch_records(self, run_id: str | None = None) -> list[HarnessPatchRecord]:
        records = [
            record
            for record in self.patch_records.values()
            if run_id is None or record.run_id == run_id
        ]
        return sorted((deepcopy(record) for record in records), key=lambda record: record.created_at)

    async def save_model_call(self, call: ModelCall) -> ModelCall:
        record = call.model_copy(deep=True)
        if not record.id:
            record.id = new_model_call_id()
        if any(existing.id == record.id for existing in self.model_calls):
            raise DuplicateRecordIdError(f"model call {record.id} already exists")
        self.model_calls.append(record)
        self._persist()
        return record.model_copy(deep=True)

    async def list_model_calls(self, run_id: str | None = None, limit: int = 2_000) -> list[ModelCall]:
        records = [
            call
            for call in self.model_calls
            if run_id is None or call.run_id == run_id
        ]
        return deepcopy(records[-limit:])

    async def save_hof_entry(self, entry: HallOfFameEntry) -> None:
        self.hof[entry.id] = entry.model_copy(deep=True)
        self._persist()

    async def list_hof(self, kind: str | None = None, limit: int = 20) -> list[HallOfFameEntry]:
        records = [
            entry
            for entry in self.hof.values()
            if kind is None or entry.kind == kind
        ]
        return sorted(
            (deepcopy(entry) for entry in records),
            key=lambda entry: (entry.fitness, entry.created_at),
            reverse=True,
        )[:limit]

    async def save_run_report(self, report: RunReport) -> None:
        self.run_reports[report.run_id] = report.model_copy(deep=True)
        self._persist()

    async def get_run_report(self, run_id: str) -> RunReport | None:
        report = self.run_reports.get(run_id)
        return report.model_copy(deep=True) if report else None

    async def recent_events(self, limit: int = 100) -> list[ArenaEvent]:
        return list(self.events)[-limit:]

    async def reset(self) -> None:
        # Check before clearing so a refused wipe leaves the in-memory state intact.
        self._ensure_writable()
        self.scenarios.clear()
        self.attacks.clear()
        self.defenses.clear()
        self.episodes.clear()
        self.generations.clear()
        self.failures.clear()
        self.harnesses.clear()
        self.harness_diffs.clear()
        self.active_harnesses.clear()
        self.events.clear()
        self.red_versions.clear()
        self.blue_versions.clear()
        self.attack_candidates.clear()
        self.patch_records.clear()
        self.model_calls.clear()
        self.hof.clear()
        self.run_reports.clear()
        self._persist()
