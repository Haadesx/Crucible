"""§20/§42 — which Blue harnesses a Red candidate is measured against, and what that means.

Red is normally scored against the current champion alone, which quietly rewards
attacks tuned to one exact defense. This module draws a small, deterministic sample of
previously promoted Blue champions from the run's own hall of fame and replays the
same candidates against them, so a strategy that breaks today's harness but not last
generation's is visible as such instead of looking like progress.

The policy lives here, apart from the co-evolution loop, because it is a measurement
rule rather than a step of the experiment: it reads the hall of fame, replays battles
it is handed, and returns evidence. It decides nothing — no promotion, no fitness, no
mutation — and it invents nothing, drawing only from harnesses this run promoted.

Determinism is the other half of the contract. The sample is drawn from a pool sorted
by harness id, because repository listing order differs between adapters and an
unsorted draw would silently produce a different sample per backend for one seed.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.harness.registry import DeployedHarness, HarnessRegistry
from app.memory.repository import MemoryRepository
from app.models.attack import AttackGenome
from app.models.audit import AntiOverfittingSignal, ChampionComparison, HallOfFameEntry
from app.models.episode import Episode
from app.models.red import AttackCandidate

# §42 asks for "current Blue champion + one or two historical Blue champions". Two
# keeps the extra battles per generation bounded while still putting Red against a
# second and third defense rather than one.
HISTORICAL_CHAMPION_SAMPLE_SIZE = 2

# The hall of fame is read in full and sampled from, so the read has to cover every
# champion the run could promote, not an arbitrary top-N.
BLUE_HOF_LIMIT = 50

# Plays one attack against one deployed harness for a given run and generation.
# The context travels with the call rather than being read from ambient state, so a
# replay can never be filed under the wrong run because of who invoked it.
RunBattle = Callable[[AttackGenome, DeployedHarness, str, int], Awaitable[Episode]]


def stable_run_seed(run_id: str) -> int:
    """Reproducible seed derived from the run id when the caller supplies none.

    Same ``run_id`` gives the same champion sample, so a run replays exactly without
    the caller having to remember to pass a seed.

    The digest is masked into the signed 64-bit range because the seed is reported in
    the run report, and MongoDB — the experiment's memory (§27) — cannot store an
    unsigned 64-bit integer. It is used only as a deterministic sample key, so the
    width costs nothing and the same ``run_id`` still replays exactly.
    """
    digest = int.from_bytes(hashlib.sha256(run_id.encode("utf-8")).digest()[:8], "big")
    return digest & ((1 << 63) - 1)


def sample_champions(
    entries: list[HallOfFameEntry],
    *,
    count: int,
    sample_key: str,
    exclude_id: str,
) -> list[HallOfFameEntry]:
    """Deterministically draw ``count`` historical champions, never the current one."""
    pool = sorted(
        (entry for entry in entries if entry.ref_id != exclude_id),
        key=lambda entry: entry.ref_id,
    )
    if not pool or count <= 0:
        return []
    return random.Random(sample_key).sample(pool, k=min(count, len(pool)))


@dataclass
class ChampionJudgement:
    """The evidence one generation produced about Red's generalisation."""

    comparisons: list[ChampionComparison] = field(default_factory=list)
    signals: list[AntiOverfittingSignal] = field(default_factory=list)
    sampled: list[str] = field(default_factory=list)

    def extend(self, other: ChampionJudgement) -> None:
        """Fold another generation's judgement into this one (the run's accumulator)."""
        self.comparisons.extend(other.comparisons)
        self.signals.extend(other.signals)
        for champion_id in other.sampled:
            if champion_id not in self.sampled:
                self.sampled.append(champion_id)


class ChampionJudge:
    """Measures Red candidates against the current champion and sampled history.

    The judge is handed a :func:`RunBattle` rather than owning an arena runner: the
    measurement rule needs battles played, not a way to play them. That keeps the
    fairness requirement honest, because every champion is measured by calling the
    same battle function over the same candidate genomes.
    """

    def __init__(
        self,
        repository: MemoryRepository,
        registry: HarnessRegistry,
        run_battle: RunBattle,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.run_battle = run_battle

    async def blue_hall_of_fame(self, run_id: str) -> list[HallOfFameEntry]:
        """Champions promoted by *this* run, read once and reused by the caller."""
        return [entry for entry in await self.repository.list_hof("blue", limit=BLUE_HOF_LIMIT) if entry.run_id == run_id]

    async def measure(
        self,
        *,
        candidates: list[AttackCandidate],
        champion: DeployedHarness,
        champion_episodes: dict[str, Episode],
        blue_hof: list[HallOfFameEntry],
        run_id: str,
        generation: int,
        run_seed: int,
    ) -> ChampionJudgement:
        """Score every candidate against the current champion and the sampled history.

        Current-champion results are reused from the episodes this generation already
        ran, and each historical champion is replayed over exactly the same candidate
        genomes, scenarios and execution path. A historical champion is therefore never
        judged on a different battery than the current one, so a difference in outcome
        is a difference in defense rather than in measurement.

        Historical harnesses are replayed through ``registry.rehearse``, which compiles
        an isolated runtime and leaves deployment state and persisted metrics alone, so
        an old champion's promotion-time numbers cannot drift because Red was measured
        against it.
        """
        judgement = ChampionJudgement()
        entries = sample_champions(
            blue_hof,
            count=HISTORICAL_CHAMPION_SAMPLE_SIZE,
            sample_key=f"{run_seed}:{generation}",
            exclude_id=champion.id,
        )
        replays: list[tuple[HallOfFameEntry, DeployedHarness]] = []
        for entry in entries:
            record = await self.repository.get_harness(entry.ref_id)
            if record is None:
                # Promoted but no longer registered: it cannot be replayed honestly.
                continue
            replays.append((entry, self.registry.rehearse(record.version)))
            judgement.sampled.append(entry.ref_id)

        champion_fitness = next(
            (entry.fitness for entry in blue_hof if entry.ref_id == champion.id),
            0.0,
        )
        for candidate in candidates:
            genome = candidate.to_genome(genome_id=f"GN-{candidate.id}")
            beat_current = champion_episodes[genome.id].attack_success
            judgement.comparisons.append(
                ChampionComparison(
                    candidate_id=candidate.id,
                    generation=generation,
                    champion_id=champion.id,
                    champion_kind="current",
                    champion_generation=generation,
                    broken=beat_current,
                    hof_fitness=champion_fitness,
                )
            )
            broken: list[str] = []
            survived: list[str] = []
            for entry, replay in replays:
                episode = await self.run_battle(genome, replay, run_id, generation)
                (broken if episode.attack_success else survived).append(entry.ref_id)
                judgement.comparisons.append(
                    ChampionComparison(
                        candidate_id=candidate.id,
                        generation=generation,
                        champion_id=entry.ref_id,
                        champion_kind="historical",
                        champion_generation=entry.generation,
                        broken=episode.attack_success,
                        hof_fitness=entry.fitness,
                    )
                )
            # No historical champion means no generalisation is claimed at all: the
            # engine would otherwise be asserting a conclusion it has no evidence for.
            generalizes = bool(judgement.sampled) and beat_current and not survived
            judgement.signals.append(
                AntiOverfittingSignal(
                    candidate_id=candidate.id,
                    generation=generation,
                    current_champion_id=champion.id,
                    beat_current_champion=beat_current,
                    sampled_champion_ids=[entry.ref_id for entry, _ in replays],
                    broken_champion_ids=broken,
                    survived_champion_ids=survived,
                    generalizes=generalizes,
                )
            )
        return judgement
