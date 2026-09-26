"""Rendering of a finished run into its training-data files (§49).

This module is the only place that turns persisted records into files. It reads the
repository and the run report and writes JSONL; it never computes a score, decides a
promotion, or holds run state. Everything here is presentation, so the experiment can
be reasoned about without it and the files can be regenerated from a saved run.

    exports/red_training.jsonl        Red: context, attack, outcome, feedback
    exports/blue_training.jsonl       Blue: breach traces, history, patch, metrics
    exports/champion_comparisons.jsonl  §20/§42 candidate-vs-champion evidence

Rows are built only from records the run actually persisted. A run that produced
nothing still gets a well-formed empty file, because a missing export and an empty
one mean very different things to whatever consumes it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.memory.repository import MemoryRepository
from app.models.audit import RunReport

RED_TRAINING = "red_training.jsonl"
BLUE_TRAINING = "blue_training.jsonl"
CHAMPION_COMPARISONS = "champion_comparisons.jsonl"


def _write_jsonl(path: Path, rows: list[str]) -> int:
    """Write ``rows`` as JSONL, creating an empty file when there are none."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(rows)


async def write_red_training(repository: MemoryRepository, report: RunReport, export_dir: Path) -> int:
    """One row per Red attack candidate, with the §20/§42 verdict attached.

    The anti-overfitting signal travels with the attack on purpose: a training set
    that records only "beat today's champion" teaches Red to overfit, which is the
    exact failure the champion sampling exists to detect.
    """
    signal_by_candidate = {signal.candidate_id: signal for signal in report.anti_overfitting}
    candidates = await repository.list_attack_candidates(report.run_id)
    rows = [
        json.dumps(
            {
                "run_id": report.run_id,
                "generation": candidate.generation,
                "red_agent_version_id": candidate.red_agent_version_id,
                "red_team_mode": report.red_team_mode,
                "context": {
                    "scenario_id": candidate.scenario_id,
                    "carrier": candidate.carrier,
                    "attack_family": candidate.attack_family,
                    "target_capability": candidate.target_capability,
                },
                "attack": candidate.payload,
                "attack_plan": candidate.attack_plan,
                "outcome": {
                    "fitness": candidate.fitness,
                    "novelty": candidate.novelty_score,
                },
                "model": candidate.generated_by_model,
                "model_call_id": candidate.model_call_id,
                "anti_overfitting": signal_by_candidate[candidate.id].model_dump(mode="json")
                if candidate.id in signal_by_candidate
                else None,
            }
        )
        for candidate in candidates
    ]
    return _write_jsonl(export_dir / RED_TRAINING, rows)


def write_champion_comparisons(report: RunReport, export_dir: Path) -> int:
    """Every Red candidate measured against every champion it faced, current and historical."""
    rows = [json.dumps(comparison.model_dump(mode="json")) for comparison in report.champion_comparisons]
    return _write_jsonl(export_dir / CHAMPION_COMPARISONS, rows)


def _breach_trace(episode: Any) -> dict[str, Any]:
    """The observable evidence Blue reasoned from for one breach."""
    return {
        "episode_id": episode.id,
        "scenario_id": episode.scenario_id,
        "attack_id": episode.attack_id,
        "harness_id": episode.harness_id or "",
        "executed_tool_calls": [
            {"tool": call.name, "arguments": call.arguments} for call in episode.executed_tool_calls
        ],
        "runtime_trace": [
            {"stage": step.stage, "status": step.status, "details": step.details} for step in episode.runtime_trace
        ],
    }


async def write_blue_training(repository: MemoryRepository, report: RunReport, export_dir: Path) -> int:
    """One row per patch Blue actually proposed (§49's Blue training data).

    Each row answers four questions the run report cannot: which breach traces the
    patch was written against, which earlier failures Blue was shown, what it changed,
    and what the compiled candidate then measured. Rows come from persisted patch and
    harness records only, so promotion and rejection are both legible and nothing is
    padded in to make the export look fuller than the run was.
    """
    run_id = report.run_id
    breaches_by_defense: dict[tuple[str, int], list[Any]] = {}
    for episode in await repository.list_episodes(run_id):
        if episode.attack_success and episode.harness_id:
            breaches_by_defense.setdefault((episode.harness_id, episode.generation), []).append(episode)
    memories = await repository.list_failures(run_id, limit=200)

    rows: list[str] = []
    for record in await repository.list_patch_records(run_id):
        if record.id.endswith("-RESULT"):
            continue
        # A patch is proposed in generation G from breaches observed in G-1 against the
        # parent harness, so that is exactly the trace set it answers.
        traces = breaches_by_defense.get((record.parent_harness_id, max(0, record.generation - 1)), [])
        child = await repository.get_harness(record.child_harness_id) if record.child_harness_id else None
        parent = await repository.get_harness(record.parent_harness_id)
        metrics = child.metrics if child is not None else None
        rows.append(
            json.dumps(
                {
                    "run_id": run_id,
                    "patch_record_id": record.id,
                    "generation": record.generation,
                    "parent_harness_id": record.parent_harness_id,
                    "child_harness_id": record.child_harness_id,
                    "valid": record.valid,
                    "rejection_reason": record.rejection_reason,
                    "breach_traces": [_breach_trace(episode) for episode in traces],
                    "historical_memories": [
                        {
                            "id": entry.id,
                            "defense_id": entry.defense_id,
                            "summary": entry.summary,
                            "similarity": entry.similarity,
                            "patch_followed": ", ".join(entry.analysis.candidate_changes) if entry.analysis else "",
                        }
                        for entry in memories
                        if entry.defense_id == record.parent_harness_id
                    ],
                    "patch": record.patch.model_dump(mode="json"),
                    "post_patch_metrics": {
                        "fitness": child.version.fitness if child is not None else None,
                        "block_rate": metrics.block_rate if metrics is not None else None,
                        "utility_rate": metrics.utility_rate if metrics is not None else None,
                        "battles": metrics.battles if metrics is not None else None,
                        "candidate_status": metrics.candidate_status if metrics is not None else None,
                        "deployment_status": child.deployment.status if child is not None else None,
                    },
                    "parent_metrics": {
                        "fitness": parent.version.fitness if parent is not None else None,
                        "attack_coverage": parent.version.attack_coverage if parent is not None else None,
                        "utility_score": parent.version.utility_score if parent is not None else None,
                    },
                    "model_call_id": record.model_call_id,
                    "authored_by": report.blue_model,
                }
            )
        )
    return _write_jsonl(export_dir / BLUE_TRAINING, rows)


async def write_all(repository: MemoryRepository, report: RunReport, export_dir: Path) -> dict[str, int]:
    """Write every §49 export for a finished run and report how many rows each got."""
    return {
        RED_TRAINING: await write_red_training(repository, report, export_dir),
        CHAMPION_COMPARISONS: write_champion_comparisons(report, export_dir),
        BLUE_TRAINING: await write_blue_training(repository, report, export_dir),
    }
