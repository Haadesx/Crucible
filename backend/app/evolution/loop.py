import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from statistics import fmean
from uuid import uuid4

from app.arena.fitness import group_episodes_by_id, score_blue, score_red
from app.arena.runner import ArenaRunner
from app.events import ArenaEventBus
from app.harness.analysis import FailureAnalyzer
from app.harness.compiler import CompiledHarness
from app.harness.registry import DeployedHarness, HarnessRegistry
from app.evolution.mutation import DeterministicRedMutator
from app.harness.mutation import DeterministicHarnessMutator
from app.evolution.seeds import initial_attacks, initial_defenses
from app.evolution.selection import choose_parents
from app.evolution.tournament import Matchup, TournamentScheduler
from app.memory.repository import MemoryRepository
from app.memory.vector import VectorMemory, attack_text
from app.models.attack import AttackGenome, AttackRecord, AttackStats
from app.models.defense import DefenseGenome, DefenseRecord, DefenseStats
from app.models.episode import Episode
from app.models.events import ArenaEvent, ArenaEventType
from app.models.generation import ArenaStartRequest, GenerationRecord, RunStatus
from app.models.harness import HarnessVersion
from app.models.memory import FailureMemory
from app.scenarios.loader import ScenarioCatalog

logger = logging.getLogger(__name__)


class EvolutionLoop:
    """Own one complete run; all selection is driven by measured episode outcomes."""

    def __init__(
        self,
        repository: MemoryRepository,
        runner: ArenaRunner,
        event_bus: ArenaEventBus,
        vector_memory: VectorMemory,
        catalog: ScenarioCatalog,
        *,
        max_parallel_episodes: int = 4,
        harness_registry: HarnessRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.runner = runner
        self.event_bus = event_bus
        self.vector_memory = vector_memory
        self.catalog = catalog
        self.max_parallel_episodes = max_parallel_episodes
        self.harness_registry = harness_registry or HarnessRegistry(repository)
        self.failure_analyzer = FailureAnalyzer()
        self.harness_versions: dict[str, HarnessVersion] = {}
        self.compiled_harnesses: dict[str, CompiledHarness] = {}
        self.deployed_harnesses: dict[str, DeployedHarness] = {}
        self.red_mutator = DeterministicRedMutator()
        self.harness_mutator = DeterministicHarnessMutator()
        self._task: asyncio.Task[None] | None = None
        self._stop_requested = asyncio.Event()
        self._status = RunStatus(status="idle")
        self._run_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self, request: ArenaStartRequest) -> str:
        async with self._lock:
            if self._task is not None and not self._task.done():
                raise RuntimeError("an evolution run is already active")
            run_id = f"RUN-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4]}"
            self._run_id = run_id
            self._stop_requested = asyncio.Event()
            self.harness_registry.reset()
            red = initial_attacks(run_id, request.red_population)
            blue = initial_defenses(run_id, request.blue_population)
            await self.repository.save_scenarios(self.catalog.all())
            self.harness_versions.clear()
            self.compiled_harnesses.clear()
            self.deployed_harnesses.clear()
            await self._register_harnesses(blue, run_id, generation=0)
            await self._persist_population(red, blue, run_id)
            self._status = RunStatus(
                run_id=run_id,
                status="started",
                generation=0,
                total_generations=request.generations,
                red_population=len(red),
                blue_population=len(blue),
                latest_event="run queued",
            )
            self._task = asyncio.create_task(self._run(request, run_id, red, blue), name=run_id)
            return run_id

    async def stop(self) -> None:
        self._stop_requested.set()
        task = self._task
        if task is not None and not task.done():
            self._status.status = "stopping"
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=30)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self._status.status = "stopped" if self._task and self._task.done() else self._status.status

    async def status(self) -> RunStatus:
        return self._status.model_copy(deep=True)

    async def wait(self) -> None:
        """Await the active run; useful for CLI demos and integration tests."""

        if self._task is not None:
            await self._task

    async def _run(
        self,
        request: ArenaStartRequest,
        run_id: str,
        red_population: list[AttackGenome],
        blue_population: list[DefenseGenome],
    ) -> None:
        try:
            for generation in range(request.generations):
                if self._stop_requested.is_set():
                    self._status.status = "stopped"
                    return
                self._status.generation = generation
                self._status.status = "running"
                await self._emit(
                    "generation_started",
                    run_id,
                    generation,
                    {
                        "red_population": len(red_population),
                        "blue_population": len(blue_population),
                        "matchups_per_genome": request.matchups_per_genome,
                    },
                )
                prior_attacks = await self.repository.list_attacks(run_id)
                matchups = TournamentScheduler(self.catalog).create(
                    red_population,
                    blue_population,
                    run_id=run_id,
                    generation=generation,
                    matchups_per_genome=request.matchups_per_genome,
                )
                episodes = await self._run_battles(matchups, run_id, generation)
                self._status.completed_battles += len(episodes)
                await self._persist_episodes_and_failures(episodes, run_id, red_population, blue_population)
                novelty = {
                    attack.id: await self.vector_memory.novelty(attack, prior_attacks)
                    for attack in red_population
                }
                red_scores, blue_scores = await self._persist_scores(
                    red_population,
                    blue_population,
                    episodes,
                    novelty,
                )
                blue_champion = max(blue_scores, key=lambda genome_id: blue_scores[genome_id])
                await self._evaluate_harnesses(
                    blue_population,
                    episodes,
                    blue_scores,
                    blue_champion,
                    run_id,
                    generation,
                )
                red_record = GenerationRecord(
                    id=generation,
                    run_id=run_id,
                    red_population=red_population,
                    blue_population=blue_population,
                    red_champion=max(red_scores, key=lambda genome_id: red_scores[genome_id]),
                    blue_champion=blue_champion,
                    active_harness_id=blue_champion,
                    harness_status="ACTIVE",
                    attack_success_rate=fmean(float(episode.attack_success) for episode in episodes),
                    utility_rate=fmean(float(episode.legitimate_task_success) for episode in episodes),
                    red_mean_fitness=fmean(red_scores.values()),
                    blue_mean_fitness=fmean(blue_scores.values()),
                    total_battles=len(episodes),
                    created_at=datetime.now(UTC),
                )
                await self.repository.save_generation(red_record)
                await self._emit(
                    "generation_finished",
                    run_id,
                    generation,
                    {
                        "generation": red_record.model_dump(mode="json"),
                        "attack_success_rate": red_record.attack_success_rate,
                        "utility_rate": red_record.utility_rate,
                    },
                )
                if generation + 1 >= request.generations:
                    continue
                next_red = await self._evolve_red(
                    red_population,
                    red_scores,
                    episodes,
                    run_id,
                    generation + 1,
                )
                next_blue = await self._evolve_blue(
                    blue_population,
                    blue_scores,
                    episodes,
                    run_id,
                    generation + 1,
                )
                red_population = next_red
                blue_population = next_blue
                await self._register_harnesses(blue_population, run_id, generation=generation + 1)
                await self._persist_population(red_population, blue_population, run_id)
            self._status.status = "stopped" if self._stop_requested.is_set() else "completed"
            await self._emit("run_finished", run_id, request.generations - 1, {"status": self._status.status})
        except asyncio.CancelledError:
            self._status.status = "cancelled"
            raise
        except Exception as exc:
            logger.exception("Evolution run %s failed", run_id)
            self._status.status = "error"
            self._status.error = str(exc)
            await self._emit("run_finished", run_id, self._status.generation, {"status": "error", "error": str(exc)})

    async def _run_battles(
        self,
        matchups: list[Matchup],
        run_id: str,
        generation: int,
    ) -> list[Episode]:
        semaphore = asyncio.Semaphore(self.max_parallel_episodes)

        async def run_one(matchup: Matchup) -> Episode:
            async with semaphore:
                deployed = self.deployed_harnesses.get(matchup.defense.id)
                if deployed is None:
                    raise RuntimeError(f"harness {matchup.defense.id} was not deployed")
                return await self.runner.run_episode(
                    matchup.scenario,
                    matchup.attack,
                    deployed.version,
                    run_id=run_id,
                    generation=generation,
                    episode_id=matchup.episode_id,
                    event_sink=self._event_sink,
                    deployed=deployed,
                )

        return list(await asyncio.gather(*(run_one(matchup) for matchup in matchups)))

    async def _event_sink(self, event: ArenaEvent) -> None:
        await self.repository.save_event(event)
        await self.event_bus.publish(event)
        self._status.latest_event = event.type

    async def _emit(
        self,
        event_type: ArenaEventType,
        run_id: str,
        generation: int,
        payload: dict[str, object],
    ) -> None:
        await self._event_sink(
            ArenaEvent(
                type=event_type,
                run_id=run_id,
                generation=generation,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )

    async def _evaluate_harnesses(
        self,
        population: list[DefenseGenome],
        episodes: list[Episode],
        scores: dict[str, float],
        champion_id: str,
        run_id: str,
        generation: int,
    ) -> None:
        groups = group_episodes_by_id(episodes, "defense_id")
        champion_fitness = scores.get(champion_id, 0.0)
        for defense in population:
            harness_record = await self.harness_registry.evaluate(
                defense.id,
                groups.get(defense.id, []),
                champion_fitness=champion_fitness,
            )
            await self._emit(
                "harness_evaluated",
                run_id,
                generation,
                {
                    "harness_id": defense.id,
                    "fitness": harness_record.metrics.fitness,
                    "block_rate": harness_record.metrics.block_rate,
                    "utility_rate": harness_record.metrics.utility_rate,
                    "battles": harness_record.metrics.battles,
                    "status": harness_record.version.status,
                },
            )
            if defense.id == champion_id:
                promoted = await self.harness_registry.promote(defense.id)
                await self._emit(
                    "harness_promoted",
                    run_id,
                    generation,
                    {
                        "harness_id": defense.id,
                        "fitness": promoted.metrics.fitness,
                        "status": promoted.version.status,
                        "deployment": promoted.deployment.status,
                    },
                )
            else:
                await self._emit(
                    "harness_rejected",
                    run_id,
                    generation,
                    {
                        "harness_id": defense.id,
                        "fitness": harness_record.metrics.fitness,
                        "status": harness_record.version.status,
                        "champion": champion_id,
                    },
                )

    async def _activate_harness(
        self,
        compiled: CompiledHarness,
        run_id: str,
        generation: int,
    ) -> DeployedHarness:
        deployed = await self.harness_registry.activate(compiled)
        self.harness_versions[deployed.id] = deployed.version
        self.compiled_harnesses[deployed.id] = compiled
        self.deployed_harnesses[deployed.id] = deployed
        await self._emit(
            "harness_activated",
            run_id,
            generation,
            {
                "harness_id": deployed.id,
                "deployment_id": deployed.deployment.id,
                "status": deployed.version.status,
                "activated_at": deployed.deployment.activated_at,
            },
        )
        await self._emit(
            "harness_deployed",
            run_id,
            generation,
            {
                "harness_id": deployed.id,
                "deployment_id": deployed.deployment.id,
                "active_modules": deployed.runtime.active_module_names,
                "graph": deployed.graph.model_dump(mode="json"),
                "deployment": deployed.deployment.status,
            },
        )
        return deployed

    async def _register_harnesses(
        self,
        population: list[DefenseGenome],
        run_id: str,
        *,
        generation: int,
    ) -> None:
        for defense in population:
            if defense.id in self.harness_versions:
                continue
            version = HarnessVersion.from_defense(defense)
            compiled = await self.harness_registry.register(version, run_id=run_id)
            await self._emit(
                "harness_compiled",
                run_id,
                generation,
                {
                    "harness_id": compiled.version.id,
                    "parent_id": compiled.version.parent_id,
                    "status": compiled.version.status,
                    "graph": compiled.graph.model_dump(mode="json"),
                    "mutation_reason": compiled.version.mutation_reason,
                },
            )
            await self._activate_harness(compiled, run_id, generation)

    async def _persist_population(
        self,
        red: list[AttackGenome],
        blue: list[DefenseGenome],
        run_id: str,
    ) -> None:
        for attack in red:
            if await self.repository.get_attack(attack.id) is None:
                record = AttackRecord(
                    genome=attack,
                    stats=AttackStats(),
                    embedding=await self.vector_memory.embed_text(attack_text(attack)),
                    created_at=datetime.now(UTC),
                )
                await self.repository.save_attack(record)
        for defense in blue:
            if await self.repository.get_defense(defense.id) is None:
                await self.repository.save_defense(
                    DefenseRecord(
                        genome=defense,
                        stats=DefenseStats(),
                        created_at=datetime.now(UTC),
                    )
                )

    async def _persist_episodes_and_failures(
        self,
        episodes: list[Episode],
        run_id: str,
        red: list[AttackGenome],
        blue: list[DefenseGenome],
    ) -> None:
        red_by_id = {attack.id: attack for attack in red}
        blue_by_id = {defense.id: defense for defense in blue}
        for episode in episodes:
            await self.repository.save_episode(episode)
            attack = red_by_id.get(episode.attack_id)
            defense = blue_by_id.get(episode.defense_id)
            if attack is None or defense is None:
                continue
            if episode.attack_success:
                failure_type = "breach"
                summary = (
                    f"Unauthorized {', '.join(sorted({call.name for call in episode.executed_tool_calls}))} "
                    f"executed by {defense.id} against {attack.id}."
                )
            elif not episode.legitimate_task_success:
                failure_type = "utility_failure"
                summary = f"Defense {defense.id} blocked the attack but failed the legitimate task."
            else:
                continue
            harness_version = self.harness_versions.get(defense.id) or HarnessVersion.from_defense(defense)
            historical_matches: list[dict[str, Any]] = []
            if episode.attack_success:
                historical_matches = [
                    failure.model_dump(mode="json")
                    for failure in await self.vector_memory.similar_failures(
                        f"{attack.strategy} {attack.carrier} {attack.target_tool} unauthorized execution",
                        limit=3,
                    )
                    if failure.id != f"FM-{episode.id}"
                ]
            analysis = (
                self.failure_analyzer.analyze(
                    episode,
                    harness_version,
                    historical_match_ids=[str(item.get("id")) for item in historical_matches if item.get("id")],
                    historical_similarity=max(
                        (
                            float(item["similarity"])
                            if isinstance(item.get("similarity"), (int, float))
                            else 0.0
                            for item in historical_matches
                        ),
                        default=0.0,
                    ),
                    historical_adaptations=[
                        str(change)
                        for item in historical_matches
                        for change in (
                            item["analysis"].get("candidate_changes", [])
                            if isinstance(item.get("analysis"), dict)
                            else []
                        )
                    ][:6],
                    evidence=[f"retrieved {len(historical_matches)} related failure memories"],
                )
                if episode.attack_success
                else None
            )
            failure = FailureMemory(
                id=f"FM-{episode.id}",
                run_id=run_id,
                episode_id=episode.id,
                type=failure_type,
                summary=summary,
                attack_id=attack.id,
                defense_id=defense.id,
                attack_features=attack.model_dump(mode="json"),
                defense_features=defense.model_dump(mode="json"),
                analysis=analysis,
                historical_match_ids=[str(item.get("id")) for item in historical_matches if item.get("id")],
                embedding=await self.vector_memory.embed_text(
                    f"{summary} {attack_text(attack)}"
                ),
                created_at=datetime.now(UTC),
            )
            await self.repository.save_failure(failure)
            if analysis is not None:
                await self._emit(
                    "failure_analysis",
                    run_id,
                    episode.generation,
                    {
                        "failure_id": failure.id,
                        "episode_id": episode.id,
                        "harness_id": episode.harness_id,
                        "analysis": analysis.model_dump(mode="json"),
                    },
                )
            if historical_matches:
                await self._emit(
                    "memory_retrieved",
                    run_id,
                    episode.generation,
                    {
                        "failure_id": failure.id,
                        "matches": [
                            {
                                "id": item.get("id"),
                                "similarity": item.get("similarity", 0.0),
                                "adaptations": item["analysis"].get("candidate_changes", [])
                                if isinstance(item.get("analysis"), dict)
                                else [],
                            }
                            for item in historical_matches
                        ],
                    },
                )

    async def _persist_scores(
        self,
        red: list[AttackGenome],
        blue: list[DefenseGenome],
        episodes: list[Episode],
        novelty: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, float]]:
        red_groups = group_episodes_by_id(episodes, "attack_id")
        blue_groups = group_episodes_by_id(episodes, "defense_id")
        red_scores: dict[str, float] = {}
        blue_scores: dict[str, float] = {}
        for attack in red:
            attack_episodes = red_groups.get(attack.id, [])
            score = score_red(attack_episodes, {attack.id: novelty.get(attack.id, 1.0)})
            red_scores[attack.id] = score["fitness"]
            old = await self.repository.get_attack(attack.id)
            await self.repository.save_attack(
                AttackRecord(
                    genome=attack,
                    stats=AttackStats(
                        fitness=score["fitness"],
                        success_rate=score["success_rate"],
                        novelty=novelty.get(attack.id, 1.0),
                        battles=len(attack_episodes),
                    ),
                    embedding=old.embedding if old else await self.vector_memory.embed_text(attack_text(attack)),
                    created_at=old.created_at if old else datetime.now(UTC),
                )
            )
        for defense in blue:
            defense_episodes = blue_groups.get(defense.id, [])
            score = score_blue(defense_episodes)
            blue_scores[defense.id] = score["fitness"]
            old_defense = await self.repository.get_defense(defense.id)
            await self.repository.save_defense(
                DefenseRecord(
                    genome=defense,
                    stats=DefenseStats(
                        fitness=score["fitness"],
                        block_rate=score["block_rate"],
                        utility_rate=score["utility_rate"],
                        battles=len(defense_episodes),
                    ),
                    created_at=old_defense.created_at if old_defense else datetime.now(UTC),
                )
            )
        return red_scores, blue_scores

    async def _evolve_red(
        self,
        population: list[AttackGenome],
        scores: dict[str, float],
        episodes: list[Episode],
        run_id: str,
        generation: int,
    ) -> list[AttackGenome]:
        groups = group_episodes_by_id(episodes, "attack_id")
        child_count = max(0, len(population) - 2)
        parents = choose_parents(population, scores, child_count, seed=hash(run_id) ^ generation)
        children: list[AttackGenome] = [population[index] for index in _elite_indices(population, scores, 2)]
        for index, parent in enumerate(parents):
            feedback = [episode.model_dump(mode="json") for episode in groups.get(parent.id, [])]
            child = await self.red_mutator.mutate(
                parent,
                genome_id=f"R-{run_id}-G{generation:02d}-{index + 1:03d}",
                generation=generation,
                feedback=feedback,
                seed=hash((run_id, generation, index)),
            )
            children.append(child)
            await self._emit(
                "mutation_created",
                run_id,
                generation,
                {"side": "red", "genome": child.model_dump(mode="json"), "parent_id": parent.id},
            )
        return children

    async def _evolve_blue(
        self,
        population: list[DefenseGenome],
        scores: dict[str, float],
        episodes: list[Episode],
        run_id: str,
        generation: int,
    ) -> list[DefenseGenome]:
        groups = group_episodes_by_id(episodes, "defense_id")
        child_count = max(0, len(population) - 2)
        parents = choose_parents(population, scores, child_count, seed=hash(run_id) ^ (generation << 8))
        children: list[DefenseGenome] = [population[index] for index in _elite_indices(population, scores, 2)]
        stored_failures = await self.repository.list_failures(run_id, limit=100)
        for index, parent in enumerate(parents):
            parent_episodes = groups.get(parent.id, [])
            breached_tools: list[str] = [
                str(call.name)
                for episode in parent_episodes
                if episode.attack_success
                for call in episode.executed_tool_calls
            ]
            analyses = [
                failure.analysis
                for failure in stored_failures
                if failure.defense_id == parent.id and failure.analysis is not None
            ]
            historical_failures = [
                failure.model_dump(mode="json")
                for failure in await self.vector_memory.similar_failures(
                    f"{parent.id} {' '.join(sorted(set(breached_tools)))} unauthorized tool execution",
                    limit=3,
                )
            ]
            parent_version = self.harness_versions.get(parent.id) or HarnessVersion.from_defense(parent)
            child_version = await self.harness_mutator.mutate(
                parent_version,
                version_id=f"B-{run_id}-G{generation:02d}-{index + 1:03d}",
                generation=generation,
                breached_tools=breached_tools,
                analyses=analyses,
                historical_failures=historical_failures,
            )
            compiled = await self.harness_registry.register(child_version, run_id=run_id)
            await self._emit(
                "harness_compiled",
                run_id,
                generation,
                {
                    "harness_id": compiled.version.id,
                    "parent_id": compiled.version.parent_id,
                    "status": compiled.version.status,
                    "graph": compiled.graph.model_dump(mode="json"),
                    "mutation_reason": compiled.version.mutation_reason,
                },
            )
            deployed = await self._activate_harness(compiled, run_id, generation)
            child = deployed.version.to_defense()
            children.append(child)
            diff = await self.repository.get_harness_diff(parent_version.id, child_version.id)
            if diff is not None:
                await self._emit(
                    "harness_diff",
                    run_id,
                    generation,
                    diff.model_dump(mode="json"),
                )
            await self._emit(
                "mutation_created",
                run_id,
                generation,
                {
                    "side": "blue",
                    "genome": child.model_dump(mode="json"),
                    "harness": compiled.version.model_dump(mode="json"),
                    "parent_id": parent.id,
                },
            )
        return children


def _elite_indices(
    population: list[AttackGenome] | list[DefenseGenome],
    scores: dict[str, float],
    count: int,
) -> list[int]:
    ranked = sorted(
        range(len(population)),
        key=lambda index: (-scores.get(population[index].id, 0.0), index),
    )
    return ranked[:count]
