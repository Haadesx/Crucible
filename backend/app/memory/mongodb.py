from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    # A checker reads this branch and sees the real pymongo types, so the adapter that
    # does the most I/O in the project is type-checked against the API it actually
    # calls. The runtime branch below keeps a minimal install without pymongo
    # importable; it is never a ``type: ignore`` over the real names, because
    # overwriting a class with ``Any`` silently disarms the checker for everything
    # downstream of it.
    from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, IndexModel
    from pymongo.errors import OperationFailure
    from pymongo.operations import SearchIndexModel

    PYMONGO_AVAILABLE = True
else:
    try:
        from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, IndexModel
        from pymongo.errors import OperationFailure
        from pymongo.operations import SearchIndexModel

        PYMONGO_AVAILABLE = True
    except ImportError:  # pragma: no cover - exercised only in minimal demo installs
        # Nothing here is reachable: __init__ refuses to build a repository when
        # PYMONGO_AVAILABLE is False. These names exist only so the module imports.
        ASCENDING, DESCENDING = 1, -1
        AsyncMongoClient = Any
        IndexModel = Any
        OperationFailure = RuntimeError
        SearchIndexModel = Any
        PYMONGO_AVAILABLE = False

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

logger = logging.getLogger(__name__)


class MongoRepository:
    """Atlas/standalone MongoDB adapter using PyMongo's native async API."""

    backend = "mongodb"

    def __init__(self, uri: str, database: str, embedding_dimensions: int = 1536) -> None:
        if not PYMONGO_AVAILABLE:
            raise RuntimeError("pymongo is not installed; use MONGODB_URI only after installing dependencies")
        # The untyped mapping is the honest document type: every document this adapter
        # writes and reads is a plain dict handed straight to a Pydantic model.
        self.client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
            uri, serverSelectionTimeoutMS=5_000
        )
        self.db = self.client[database]
        self.embedding_dimensions = embedding_dimensions

    async def start(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        await self.client.close()

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
        except Exception:
            return False
        return True

    async def ensure_indexes(self) -> None:
        await self.db.attacks.create_indexes(
            [
                IndexModel([("generation", ASCENDING)]),
                IndexModel([("parent_ids", ASCENDING)]),
            ]
        )
        await self.db.defenses.create_indexes(
            [
                IndexModel([("generation", ASCENDING)]),
                IndexModel([("parent_ids", ASCENDING)]),
            ]
        )
        await self.db.episodes.create_indexes(
            [
                IndexModel([("generation", ASCENDING), ("attack_id", ASCENDING), ("defense_id", ASCENDING)]),
                IndexModel([("run_id", ASCENDING), ("created_at", DESCENDING)]),
            ]
        )
        await self.db.generations.create_index([("run_id", ASCENDING), ("id", ASCENDING)])
        await self.db.red_agent_versions.create_index([("run_id", ASCENDING), ("generation", ASCENDING)])
        await self.db.blue_agent_versions.create_index([("run_id", ASCENDING), ("generation", ASCENDING)])
        await self.db.attack_candidates.create_index([("run_id", ASCENDING), ("created_at", DESCENDING)])
        await self.db.harness_patches.create_index([("run_id", ASCENDING), ("created_at", DESCENDING)])
        await self.db.model_calls.create_index([("run_id", ASCENDING), ("created_at", ASCENDING)])
        await self.db.hall_of_fame.create_index([("kind", ASCENDING), ("fitness", DESCENDING)])
        await self.db.run_reports.create_index([("created_at", DESCENDING)])
        await self.db.harnesses.create_index([("version.id", ASCENDING), ("version.generation", ASCENDING)])
        await self.db.harnesses.create_index([("version.parent_id", ASCENDING)])
        await self.db.harness_diffs.create_index([("from_version", ASCENDING), ("to_version", ASCENDING)])
        await self.db.memories.create_index([("run_id", ASCENDING), ("created_at", DESCENDING)])
        await self._ensure_vector_indexes()

    async def _ensure_vector_indexes(self) -> None:
        definitions = {
            "attacks": ("attack_embedding_index", "embedding"),
            "memories": ("memory_embedding_index", "embedding"),
        }
        for collection, (name, path) in definitions.items():
            try:
                existing = [
                    str(index.get("name"))
                    async for index in await self.db[collection].list_search_indexes()
                ]
                if name in existing:
                    continue
                # The old singular ``createSearchIndex`` command is refused by current
                # Atlas with CommandNotFound; the supported path is createSearchIndexes
                # with an explicit vectorSearch type, or the server treats the index as
                # a text-search index and rejects it for missing mappings.
                await self.db[collection].create_search_indexes(
                    [
                        SearchIndexModel(
                            definition={
                                "fields": [
                                    {
                                        "type": "vector",
                                        "path": path,
                                        "numDimensions": self.embedding_dimensions,
                                        "similarity": "cosine",
                                    }
                                ]
                            },
                            name=name,
                            type="vectorSearch",
                        )
                    ]
                )
            except OperationFailure as exc:
                logger.info("Vector index %s is not available locally: %s", name, exc)

    async def save_scenarios(self, scenarios: list[Scenario]) -> None:
        for scenario in scenarios:
            await self.db.scenarios.replace_one(
                {"_id": scenario.id},
                scenario.model_dump(mode="python"),
                upsert=True,
            )

    async def save_attack(self, record: AttackRecord) -> None:
        document = {
            "_id": record.genome.id,
            "genome": record.genome.model_dump(mode="python"),
            "stats": record.stats.model_dump(mode="python"),
            "embedding": record.embedding,
            "created_at": record.created_at,
        }
        await self.db.attacks.replace_one({"_id": record.genome.id}, document, upsert=True)

    async def save_defense(self, record: DefenseRecord) -> None:
        document = {
            "_id": record.genome.id,
            "genome": record.genome.model_dump(mode="python"),
            "stats": record.stats.model_dump(mode="python"),
            "created_at": record.created_at,
        }
        await self.db.defenses.replace_one({"_id": record.genome.id}, document, upsert=True)

    async def save_episode(self, episode: Episode) -> None:
        await self.db.episodes.replace_one(
            {"_id": episode.id},
            episode.model_dump(mode="python"),
            upsert=True,
        )

    async def save_generation(self, generation: GenerationRecord) -> None:
        document = generation.model_dump(mode="python")
        document["_id"] = f"{generation.run_id}:G{generation.id:02d}"
        await self.db.generations.replace_one({"_id": document["_id"]}, document, upsert=True)

    async def save_failure(self, failure: FailureMemory) -> None:
        await self.db.memories.replace_one(
            {"_id": failure.id},
            failure.model_dump(mode="python"),
            upsert=True,
        )

    async def save_event(self, event: ArenaEvent) -> None:
        await self.db.arena_events.insert_one(event.model_dump(mode="python"))

    async def save_harness(self, record: HarnessRecord) -> None:
        await self.db.harnesses.replace_one(
            {"_id": record.version.id},
            record.model_dump(mode="python"),
            upsert=True,
        )

    async def get_harness(self, harness_id: str) -> HarnessRecord | None:
        document = await self.db.harnesses.find_one({"_id": harness_id})
        return HarnessRecord.model_validate(self._document(document)) if document else None

    async def list_harnesses(self, run_id: str | None = None) -> list[HarnessRecord]:
        query = {"version.id": {"$regex": f"^B-{run_id}-"}} if run_id else {}
        cursor = self.db.harnesses.find(query).sort([("version.generation", ASCENDING)])
        return [HarnessRecord.model_validate(self._document(document)) async for document in cursor]

    async def save_harness_diff(self, diff: HarnessDiff) -> None:
        await self.db.harness_diffs.replace_one(
            {"_id": f"{diff.from_version}->{diff.to_version}"},
            diff.model_dump(mode="python"),
            upsert=True,
        )

    async def get_harness_diff(self, from_version: str, to_version: str) -> HarnessDiff | None:
        document = await self.db.harness_diffs.find_one({"_id": f"{from_version}->{to_version}"})
        return HarnessDiff.model_validate(self._document(document)) if document else None

    async def set_active_harness(self, run_id: str, harness_id: str) -> None:
        await self.db.runtime_state.update_one(
            {"_id": f"active-harness:{run_id}"},
            {"$set": {"harness_id": harness_id, "run_id": run_id, "set_at": datetime.now(UTC)}},
            upsert=True,
        )

    async def get_active_harness(self, run_id: str | None = None) -> HarnessRecord | None:
        """Read the active-harness pointer, and nothing else.

        Deciding *which* harness is the champion belongs to the registry, which owns
        the lifecycle; a repository that quietly substituted its own guess here was a
        second owner whose answer could differ from the engine's. Matching the
        in-memory implementation keeps both honest.
        """

        if run_id is None:
            state = await self.db.runtime_state.find_one(
                {"_id": {"$regex": "^active-harness:"}}, sort=[("set_at", DESCENDING)]
            )
        else:
            state = await self.db.runtime_state.find_one({"_id": f"active-harness:{run_id}"})
        harness_id = str(state.get("harness_id")) if state and state.get("harness_id") else None
        if harness_id is None:
            return None
        document = await self.db.harnesses.find_one({"_id": harness_id})
        return HarnessRecord.model_validate(self._document(document)) if document else None

    async def get_attack(self, attack_id: str) -> AttackRecord | None:
        return self._attack(await self.db.attacks.find_one({"_id": attack_id}))

    async def get_defense(self, defense_id: str) -> DefenseRecord | None:
        return self._defense(await self.db.defenses.find_one({"_id": defense_id}))

    async def list_episodes(self, run_id: str | None = None) -> list[Episode]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.episodes.find(query).sort([("created_at", ASCENDING), ("_id", ASCENDING)])
        return [Episode.model_validate(self._document(document)) async for document in cursor]

    async def get_episode(self, episode_id: str) -> Episode | None:
        document = await self.db.episodes.find_one({"_id": episode_id})
        return Episode.model_validate(self._document(document)) if document else None

    async def get_generation(
        self, generation: int, run_id: str | None = None
    ) -> GenerationRecord | None:
        query: dict[str, Any] = {"id": generation}
        if run_id is not None:
            query["run_id"] = run_id
        document = await self.db.generations.find_one(query, sort=[("created_at", DESCENDING)])
        return GenerationRecord.model_validate(self._document(document)) if document else None

    async def list_generations(self, run_id: str | None = None) -> list[GenerationRecord]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.generations.find(query).sort([("id", ASCENDING)])
        return [GenerationRecord.model_validate(self._document(document)) async for document in cursor]

    async def list_attacks(self, run_id: str | None = None) -> list[AttackRecord]:
        query = {"genome.id": {"$regex": f"^R-{run_id}-"}} if run_id else {}
        cursor = self.db.attacks.find(query).sort([("genome.generation", ASCENDING)])
        return [record for document in await cursor.to_list(None) if (record := self._attack(document))]

    async def list_defenses(self, run_id: str | None = None) -> list[DefenseRecord]:
        query = {"genome.id": {"$regex": f"^B-{run_id}-"}} if run_id else {}
        cursor = self.db.defenses.find(query).sort([("genome.generation", ASCENDING)])
        return [record for document in await cursor.to_list(None) if (record := self._defense(document))]

    async def get_failure(self, failure_id: str) -> FailureMemory | None:
        document = await self.db.memories.find_one({"_id": failure_id})
        return FailureMemory.model_validate(self._document(document)) if document else None

    async def list_failures(self, run_id: str | None = None, limit: int = 50) -> list[FailureMemory]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.memories.find(query).sort([("created_at", DESCENDING)]).limit(limit)
        return [FailureMemory.model_validate(self._document(document)) async for document in cursor]

    async def save_red_version(self, version: RedAgentVersion) -> None:
        await self.db.red_agent_versions.replace_one(
            {"_id": version.id},
            version.model_dump(mode="python"),
            upsert=True,
        )

    async def get_red_version(self, version_id: str) -> RedAgentVersion | None:
        document = await self.db.red_agent_versions.find_one({"_id": version_id})
        return RedAgentVersion.model_validate(self._document(document)) if document else None

    async def list_red_versions(self, run_id: str | None = None) -> list[RedAgentVersion]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.red_agent_versions.find(query).sort([("generation", ASCENDING), ("id", ASCENDING)])
        return [RedAgentVersion.model_validate(self._document(document)) async for document in cursor]

    async def save_blue_version(self, version: BlueAgentVersion) -> None:
        await self.db.blue_agent_versions.replace_one(
            {"_id": version.id},
            version.model_dump(mode="python"),
            upsert=True,
        )

    async def list_blue_versions(self, run_id: str | None = None) -> list[BlueAgentVersion]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.blue_agent_versions.find(query).sort([("generation", ASCENDING), ("id", ASCENDING)])
        return [BlueAgentVersion.model_validate(self._document(document)) async for document in cursor]

    async def save_attack_candidate(self, candidate: AttackCandidate) -> None:
        await self.db.attack_candidates.replace_one(
            {"_id": candidate.id},
            candidate.model_dump(mode="python"),
            upsert=True,
        )

    async def get_attack_candidate(self, candidate_id: str) -> AttackCandidate | None:
        document = await self.db.attack_candidates.find_one({"_id": candidate_id})
        return AttackCandidate.model_validate(self._document(document)) if document else None

    async def list_attack_candidates(self, run_id: str | None = None) -> list[AttackCandidate]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.attack_candidates.find(query).sort([("created_at", ASCENDING)])
        return [AttackCandidate.model_validate(self._document(document)) async for document in cursor]

    async def save_patch_record(self, record: HarnessPatchRecord) -> None:
        await self.db.harness_patches.replace_one(
            {"_id": record.id},
            record.model_dump(mode="python"),
            upsert=True,
        )

    async def list_patch_records(self, run_id: str | None = None) -> list[HarnessPatchRecord]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.harness_patches.find(query).sort([("created_at", ASCENDING)])
        return [HarnessPatchRecord.model_validate(self._document(document)) async for document in cursor]

    async def save_model_call(self, call: ModelCall) -> ModelCall:
        record = call.model_copy(deep=True)
        if not record.id:
            record.id = new_model_call_id()
        # insert_one keeps the ledger append-only: a repeated id raises DuplicateKeyError,
        # the same contract the in-memory adapter enforces. That only holds if the ledger
        # id is the primary key — dumping the model alone left MongoDB to mint a fresh
        # ObjectId per row, so duplicate ids were appended silently and the two
        # adapters disagreed about what a repeated call means.
        document = record.model_dump(mode="python")
        document["_id"] = record.id
        await self.db.model_calls.insert_one(document)
        return record

    async def list_model_calls(self, run_id: str | None = None, limit: int = 2_000) -> list[ModelCall]:
        query = {"run_id": run_id} if run_id else {}
        cursor = self.db.model_calls.find(query).sort([("created_at", ASCENDING)]).limit(limit)
        return [ModelCall.model_validate(self._document(document)) async for document in cursor]

    async def save_hof_entry(self, entry: HallOfFameEntry) -> None:
        await self.db.hall_of_fame.replace_one(
            {"_id": entry.id},
            entry.model_dump(mode="python"),
            upsert=True,
        )

    async def list_hof(self, kind: str | None = None, limit: int = 20) -> list[HallOfFameEntry]:
        query = {"kind": kind} if kind else {}
        cursor = self.db.hall_of_fame.find(query).sort([("fitness", DESCENDING)]).limit(limit)
        return [HallOfFameEntry.model_validate(self._document(document)) async for document in cursor]

    async def save_run_report(self, report: RunReport) -> None:
        await self.db.run_reports.replace_one(
            {"_id": report.run_id},
            report.model_dump(mode="python"),
            upsert=True,
        )

    async def get_run_report(self, run_id: str) -> RunReport | None:
        document = await self.db.run_reports.find_one({"_id": run_id})
        return RunReport.model_validate(self._document(document)) if document else None

    async def recent_events(self, limit: int = 100) -> list[ArenaEvent]:
        cursor = self.db.arena_events.find().sort([("created_at", DESCENDING)]).limit(limit)
        events = [ArenaEvent.model_validate(self._document(document)) async for document in cursor]
        return list(reversed(events))

    async def reset(self) -> None:
        for collection in (
            self.db.scenarios,
            self.db.attacks,
            self.db.defenses,
            self.db.episodes,
            self.db.generations,
            self.db.memories,
            self.db.harnesses,
            self.db.harness_diffs,
            self.db.arena_events,
            self.db.runtime_state,
        ):
            await collection.delete_many({})

    async def vector_search(
        self,
        collection: str,
        index_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Use Atlas Vector Search when present; callers fall back locally on failure."""

        pipeline = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": max(100, limit * 10),
                    "limit": limit,
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "embedding": 1,
                    "attack_id": 1,
                    "defense_id": 1,
                    "summary": 1,
                    "episode_id": 1,
                    "type": 1,
                    "historical_match_ids": 1,
                    "analysis": 1,
                    "created_at": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        # PyMongo's async ``aggregate`` is itself a coroutine returning the cursor,
        # so the pipeline has to be awaited before ``to_list``; chaining them made
        # every Atlas retrieval fail with "'coroutine' object has no attribute
        # 'to_list'".
        cursor = await self.db[collection].aggregate(pipeline)
        # Needed only where pymongo is absent and the cursor is therefore Any, which
        # ``strict`` forbids returning; with pymongo installed the cast is genuinely
        # redundant, so both diagnostics are named rather than whichever one the
        # author happened to be running.
        rows = await cursor.to_list(length=limit)
        return cast(list[dict[str, Any]], rows)  # type: ignore[redundant-cast,unused-ignore]

    @staticmethod
    def _document(document: dict[str, Any] | None) -> dict[str, Any] | None:
        """Strip the server's ``_id`` before a document reaches a model.

        Every persisted model is ``extra="forbid"`` and MongoDB attaches ``_id``
        to every document it hands back, so validating a raw document failed on
        records this adapter itself had written. The in-memory adapter has no
        such field, so this is exactly the gap a real database exposed.
        """
        if document is None:
            return None
        return {key: value for key, value in document.items() if key != "_id"}

    @staticmethod
    def _attack(document: dict[str, Any] | None) -> AttackRecord | None:
        return AttackRecord.model_validate(MongoRepository._document(document)) if document else None

    @staticmethod
    def _defense(document: dict[str, Any] | None) -> DefenseRecord | None:
        return DefenseRecord.model_validate(MongoRepository._document(document)) if document else None
