"""Rebuild a run's final RunReport from its persisted snapshot, without writing to it.

A resumed co-evolution run only writes its RunReport when the loop reaches its end. If
the process dies in a later generation, the snapshot keeps the earlier checkpoint report
while the records show more work — the overnight run's report says 3 generations / 102
calls while the snapshot holds 7 / 256, so the observer shows two contradictory finals.

This tool derives the final report from the persisted records alone, using the same
shapes the engine uses (RunLedger counters, the boundary selection for the Red champion,
ChampionJudge's comparisons read back from the episodes it measured). It writes the
report and a *copy* of the snapshot — with only ``run_reports`` replaced — into a new
derived directory. The source snapshot is opened read-only and hashed before and after;
a mismatch aborts the run. Nothing in the source experiment directory is touched.

Usage:
    .venv/bin/python scripts/rebuild_run_report.py \
        --state experiments/OVERNIGHT-COEV-20260926-022643/state.json \
        --run-id OVERNIGHT-COEV-20260926-022643 \
        --out-dir exports/derived/OVERNIGHT-COEV-20260926-022643
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.coevolution.champions import stable_run_seed
from app.coevolution.engine import RunLedger
from app.memory.repository import InMemoryRepository
from app.models.audit import AntiOverfittingSignal, ChampionComparison, HallOfFameEntry, RunReport
from app.models.episode import Episode
from app.models.events import ArenaEvent
from app.models.generation import GenerationRecord
from app.models.red import AttackCandidate, RedAgentVersion

OPENING_HARNESS = "B-{run_id}-G00-B0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role(calls: list[object], field: str, role: str, default: str) -> str:
    for call in calls:
        if getattr(call, "role", None) == role:
            value = getattr(call, field, "")
            return value or default
    return default


def _final_red_champion(
    last_generation_id: int,
    fitness_by_parent: dict[str, float],
    versions: list[RedAgentVersion],
    events: list[ArenaEvent],
    fallback: str,
) -> str:
    """Reproduce the engine's boundary selection for the last completed generation.

    At the end of a generation the loop keeps, per measured parent, its newly promoted
    child or the parent itself, then reports the fittest member. Decision-time child
    fitness comes from the promotion event because a later, interrupted iteration may
    have overwritten the version record's fitness with a re-measurement.
    """

    if not fitness_by_parent:
        return fallback
    decision_fitness: dict[str, float] = {}
    for event in events:
        if event.type != "red_candidate_promoted":
            continue
        child_id = event.payload.get("child_id")
        child_fitness = event.payload.get("child_fitness")
        if isinstance(child_id, str) and isinstance(child_fitness, (int, float)):
            decision_fitness[child_id] = float(child_fitness)
    population: list[tuple[str, float, int]] = []
    for parent_id, parent_fitness in fitness_by_parent.items():
        child = next(
            (
                version
                for version in versions
                if version.generation == last_generation_id + 1
                and parent_id in version.parent_ids
                and version.status == "PROMOTED"
            ),
            None,
        )
        if child is None:
            population.append((parent_id, parent_fitness, last_generation_id))
        else:
            population.append((child.id, decision_fitness.get(child.id, child.fitness or 0.0), child.generation))
    return max(population, key=lambda item: (item[1], item[2]))[0]


def _judgement(
    generations: list[GenerationRecord],
    candidates: list[AttackCandidate],
    episodes: list[Episode],
    blue_hof: dict[str, HallOfFameEntry],
    run_id: str,
) -> tuple[list[ChampionComparison], list[AntiOverfittingSignal], list[str]]:
    """Rebuild ChampionJudge's evidence from the episodes it actually measured.

    The champion a candidate faced at generation G is the run's champion at the start
    of that generation (the previous record's champion; the opening baseline for G0),
    because Blue adapts after Red is measured. Any other hall-of-fame harness in the
    candidate's episodes is a historical replay. Episodes against candidate harnesses
    (Blue's battery) are not comparisons and are ignored.
    """

    by_attack: dict[str, list[Episode]] = defaultdict(list)
    for episode in episodes:
        by_attack[episode.attack_id].append(episode)

    comparisons: list[ChampionComparison] = []
    signals: list[AntiOverfittingSignal] = []
    sampled: list[str] = []
    for index, record in enumerate(generations):
        start_champion = (
            generations[index - 1].blue_champion
            if index > 0
            else OPENING_HARNESS.format(run_id=run_id)
        )
        played = {genome.id for genome in record.red_population}
        for candidate in candidates:
            if candidate.generation != record.id or f"GN-{candidate.id}" not in played:
                continue
            hits = [episode for episode in by_attack.get(f"GN-{candidate.id}", []) if episode.generation == record.id]
            current = next((episode for episode in hits if episode.harness_id == start_champion), None)
            replayed = [
                harness_id
                for harness_id in dict.fromkeys(episode.harness_id for episode in hits)
                if harness_id != start_champion and harness_id in blue_hof
            ]
            broken: list[str] = []
            survived: list[str] = []
            for harness_id in replayed:
                replay = next(episode for episode in hits if episode.harness_id == harness_id)
                entry = blue_hof[harness_id]
                (broken if replay.attack_success else survived).append(harness_id)
                comparisons.append(
                    ChampionComparison(
                        candidate_id=candidate.id,
                        generation=record.id,
                        champion_id=harness_id,
                        champion_kind="historical",
                        champion_generation=entry.generation,
                        broken=replay.attack_success,
                        hof_fitness=entry.fitness,
                    )
                )
                if harness_id not in sampled:
                    sampled.append(harness_id)
            if current is None:
                continue
            comparisons.append(
                ChampionComparison(
                    candidate_id=candidate.id,
                    generation=record.id,
                    champion_id=start_champion,
                    champion_kind="current",
                    champion_generation=record.id,
                    broken=current.attack_success,
                    hof_fitness=blue_hof[start_champion].fitness if start_champion in blue_hof else 0.0,
                )
            )
            signals.append(
                AntiOverfittingSignal(
                    candidate_id=candidate.id,
                    generation=record.id,
                    current_champion_id=start_champion,
                    beat_current_champion=current.attack_success,
                    sampled_champion_ids=replayed,
                    broken_champion_ids=broken,
                    survived_champion_ids=survived,
                    generalizes=bool(replayed) and current.attack_success and not survived,
                )
            )
    return comparisons, signals, sampled


async def rebuild(run_id: str, state_path: Path) -> tuple[RunReport, dict[str, object]]:
    repository = InMemoryRepository(snapshot_path=state_path, read_only=True)
    await repository.start()
    generations = sorted(await repository.list_generations(run_id), key=lambda record: record.id)
    if not generations:
        raise SystemExit(f"no generation records for run {run_id!r} in {state_path}")
    red_versions = await repository.list_red_versions(run_id)
    blue_versions = await repository.list_blue_versions(run_id)
    candidates = await repository.list_attack_candidates(run_id)
    episodes = await repository.list_episodes(run_id)
    patches = [patch for patch in await repository.list_patch_records(run_id) if not patch.id.endswith("-RESULT")]
    harnesses = await repository.list_harnesses(run_id)
    calls = await repository.list_model_calls(run_id, limit=20_000)
    red_hof = await repository.list_hof("red", limit=10)
    blue_hof = await repository.list_hof("blue", limit=2_000)
    active = await repository.get_active_harness(run_id)
    previous = await repository.get_run_report(run_id)

    comparisons, signals, sampled = _judgement(
        generations, candidates, episodes, {entry.ref_id: entry for entry in blue_hof}, run_id
    )

    ledger = RunLedger(
        run_id=run_id,
        seed=previous.run_seed if previous is not None else stable_run_seed(run_id),
        generations=len(generations),
        red_model=previous.red_model if previous is not None else _role(calls, "model", "red_attacker", "unknown"),
        blue_model=previous.blue_model if previous is not None else _role(calls, "model", "blue_executor", "unknown"),
        red_provider=previous.red_provider if previous is not None else _role(calls, "provider", "red_attacker", "unknown"),
        blue_provider=previous.blue_provider if previous is not None else _role(calls, "provider", "blue_executor", "unknown"),
        red_team_mode=previous.red_team_mode if previous is not None else "BLACK_BOX",
        attacks_successful=sum(round(record.attack_success_rate * len(record.red_population)) for record in generations),
        asr_by_generation=[record.attack_success_rate for record in generations],
        utility_by_generation=[record.utility_rate for record in generations],
    )
    ledger.judgement.comparisons = comparisons
    ledger.judgement.signals = signals
    ledger.judgement.sampled = sampled
    ledger.total_model_calls = len(calls)
    ledger.reconcile(
        red_versions=len(red_versions),
        blue_versions=len(blue_versions),
        attacks=len(candidates),
        patches=len(patches),
        compiled=sum(patch.valid and patch.child_harness_id is not None for patch in patches),
        promoted=sum(record.deployment.status == "PROMOTED" for record in harnesses),
    )
    report = ledger.build_report(
        red_hall_of_fame=[entry.ref_id for entry in red_hof],
        blue_hall_of_fame=[entry.ref_id for entry in blue_hof],
        final_red_champion=_final_red_champion(
            generations[-1].id,
            generations[-1].red_fitness_by_version,
            red_versions,
            list(repository.events),
            generations[-1].red_agent_champion or (previous.final_red_champion if previous is not None else ""),
        ),
        final_blue_champion=active.version.id if active is not None else "",
    )
    counts: dict[str, object] = {
        "generations": len(generations),
        "model_calls": len(calls),
        "attacks": len(candidates),
        "attacks_successful": report.attacks_successful,
        "patches": len(patches),
        "candidates_promoted": report.candidates_promoted,
        "red_versions": len(red_versions),
        "blue_versions": len(blue_versions),
        "comparisons": len(comparisons),
        "signals": len(signals),
        "historical_sampled": sampled,
    }
    return report, counts


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path, help="persisted DEV snapshot to read")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True, type=Path, help="new directory for the derived files")
    args = parser.parse_args()

    state_path: Path = args.state
    out_dir: Path = args.out_dir
    if out_dir.resolve() == state_path.resolve().parent:
        raise SystemExit("refusing to write derived files into the evidence snapshot's own directory")

    before = sha256(state_path)
    report, counts = await rebuild(args.run_id, state_path)
    after = sha256(state_path)
    if before != after:
        raise SystemExit("source snapshot changed during the rebuild; aborting")

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"run_report_{args.run_id}-FINAL.json"
    derived_state_path = out_dir / "state.final.json"
    rebuilt_at = datetime.now(UTC).isoformat()

    report_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    raw["run_reports"] = [
        [key, report.model_dump(mode="json")] if key == args.run_id else [key, value]
        for key, value in raw["run_reports"]
    ]
    raw["derived_from"] = str(state_path)
    raw["derived_at"] = rebuilt_at
    derived_state_path.write_text(json.dumps(raw), encoding="utf-8")

    notes = [
        f"# Derived final report — {args.run_id}",
        "",
        f"- Source snapshot: `{state_path}` (sha256 `{before}`; verified byte-identical after the rebuild)",
        f"- Rebuilt at: {rebuilt_at}",
        f"- Final report: `{report_path.name}`",
        f"- Observer snapshot: `{derived_state_path.name}` (same records; `run_reports[{args.run_id}]` replaced)",
        f"- Totals: {counts['generations']} generations, {counts['model_calls']} model calls, "
        f"{counts['attacks']} attacks ({counts['attacks_successful']} successful), {counts['patches']} patches, "
        f"{counts['candidates_promoted']} promoted",
        f"- Judgement rebuilt from persisted episodes: {counts['comparisons']} comparisons, "
        f"{counts['signals']} signals, historical sampled={counts['historical_sampled']}",
        "",
        "Reconstructed read-only by `scripts/rebuild_run_report.py`; no historical evidence bytes were modified.",
        "",
    ]
    (out_dir / "REBUILD_NOTES.md").write_text("\n".join(notes), encoding="utf-8")

    print(f"wrote {report_path}")
    print(f"wrote {derived_state_path}")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
