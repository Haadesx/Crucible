"""The judge-facing Version x Test matrix, derived from persisted evidence only.

Contract (§4-§13 of docs/CRUCIBLE_FINAL_60MIN_KIRO_ORCHESTRATOR.md, frozen by the
orchestrator): ``GET /runs/{run_id}/matrix`` returns the promoted harness lineage
(B0 plus promoted harnesses in promotion order), rejected candidates, the union of
tests, one cell per (version, test) that actually ran, and a per-version trend. Every
value traces back to an episode, harness, patch record or model call; a pair that
never ran has no cell and the UI renders "not run". Nothing is invented here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.memory.repository import MemoryRepository
from app.models.blue import HarnessPatchRecord
from app.models.episode import Episode

BLOCKING_DECISIONS = {"deny", "require_approval"}


def _benign(scenario_id: str) -> bool:
    return scenario_id.upper().startswith("BENIGN")


def _holdout(scenario_id: str, attack_id: str) -> bool:
    return attack_id.startswith("A-HOLDOUT") or scenario_id.upper().startswith("HOLDOUT")


def _test_key(scenario_id: str, attack_id: str) -> str:
    return f"{scenario_id}|{attack_id}"


def _harness_block(episode: Episode) -> str:
    """How the harness itself stopped this episode, or "" when it did not.

    A benign task failure is only a false positive when the harness denied or held a
    proposed call; a model that simply failed the task must not be blamed on the
    harness (§5).
    """

    for decision in episode.gateway_decisions:
        if decision.decision in BLOCKING_DECISIONS:
            codes = ", ".join(decision.reason_codes) or decision.decision
            return f"harness {decision.decision}: {codes}"
    for step in episode.runtime_trace:
        if step.status == "BLOCKED":
            return f"harness blocked at {step.stage}"
    return ""


def _label(scenario_id: str, attack_id: str, family: str | None, kind: str, run_id: str) -> str:
    """Row label; replayed breaches say which run and generation they came from."""

    if kind == "benign" or not family:
        return scenario_id
    marker = attack_id.split("-G")
    generation = f"G{marker[-1][:2]}" if len(marker) > 1 and marker[-1][:2].isdigit() else ""
    if run_id in attack_id:
        origin = f"this run {generation}".strip()
    else:
        head = attack_id.rsplit("-G", 1)[0]
        parts = head.split("-")
        source = parts[-2] if len(parts) > 1 and len(parts[-1]) == 8 and parts[-1].isdigit() else parts[-1]
        origin = f"replay of {source} {generation}".strip()
    return f"{scenario_id} · {family} · {origin}"


def _promoted_at(record: HarnessPatchRecord) -> datetime:
    for transition in reversed(record.transitions):
        if transition.status == "PROMOTED":
            return transition.at
    return record.created_at


async def build_matrix(repository: MemoryRepository, run_id: str) -> dict[str, Any]:
    harnesses = {record.version.id: record for record in await repository.list_harnesses(run_id)}
    patches = await repository.list_patch_records(run_id)
    episodes = sorted(await repository.list_episodes(run_id), key=lambda episode: episode.created_at)
    call_models = {
        call.id: call.model for call in await repository.list_model_calls(run_id, limit=5_000)
    }

    versions: list[dict[str, Any]] = []
    labels: dict[str, str] = {}
    baseline = next(
        (
            record
            for record in harnesses.values()
            if record.version.generation == 0 and not record.version.parent_id
        ),
        None,
    )
    if baseline is not None:
        labels[baseline.version.id] = "V0"
        versions.append(
            {
                "label": "V0",
                "harness_id": baseline.version.id,
                "parent_id": None,
                "generation": baseline.version.generation,
                "patch_id": None,
                "status": "BASELINE",
                "fitness": None,
                "block_rate": None,
                "utility_rate": None,
                "engineer_model": None,
            }
        )
    promoted = sorted(
        [record for record in patches if record.status == "PROMOTED" and record.child_harness_id],
        key=_promoted_at,
    )
    for record in promoted:
        harness_id = str(record.child_harness_id)
        if harness_id in labels:
            continue
        label = f"V{len(versions)}"
        labels[harness_id] = label
        metrics = record.metrics
        versions.append(
            {
                "label": label,
                "harness_id": harness_id,
                "parent_id": record.parent_harness_id,
                "generation": record.generation,
                "patch_id": record.id,
                "status": "PROMOTED",
                "fitness": metrics.fitness if metrics else None,
                "block_rate": metrics.block_rate if metrics else None,
                "utility_rate": metrics.utility_rate if metrics else None,
                "engineer_model": call_models.get(record.model_call_id) if record.model_call_id else None,
            }
        )

    rejected = [
        {
            "harness_id": record.child_harness_id or "",
            "patch_id": record.id,
            "generation": record.generation,
            "reason": record.decision or record.rejection_reason,
            "fitness": record.metrics.fitness if record.metrics else None,
            "block_rate": record.metrics.block_rate if record.metrics else None,
            "utility_rate": record.metrics.utility_rate if record.metrics else None,
        }
        for record in sorted(patches, key=lambda record: record.created_at)
        if record.status == "REJECTED"
    ]

    # The latest episode per (harness, scenario, attack) is the cell's evidence;
    # episodes run against rejected candidates are not matrix columns and are skipped.
    latest: dict[tuple[str, str, str], Episode] = {}
    for episode in episodes:
        if episode.harness_id not in labels:
            continue
        latest[(episode.harness_id, episode.scenario_id, episode.attack_id)] = episode

    test_pairs = sorted({(scenario_id, attack_id) for _, scenario_id, attack_id in latest})
    tests: list[dict[str, Any]] = []
    slices: dict[tuple[str, str], str] = {}
    for scenario_id, attack_id in test_pairs:
        pair_episodes = [
            episode
            for (_, stored_scenario, stored_attack), episode in latest.items()
            if stored_scenario == scenario_id and stored_attack == attack_id
        ]
        reference = max(pair_episodes, key=lambda episode: episode.created_at)
        kind = "benign" if _benign(scenario_id) else "adversarial"
        candidate = None
        if kind == "adversarial":
            candidate = await repository.get_attack_candidate(attack_id.removeprefix("GN-"))
        family = candidate.attack_family if candidate is not None else None
        if kind == "benign":
            slice_name = "benign"
        elif _holdout(scenario_id, attack_id):
            slice_name = "holdout"
        else:
            slice_name = (
                "current"
                if candidate is not None and candidate.generation == reference.generation
                else "regression"
            )
        slices[(scenario_id, attack_id)] = slice_name
        tests.append(
            {
                "key": _test_key(scenario_id, attack_id),
                "kind": kind,
                "scenario_id": scenario_id,
                "attack_id": attack_id,
                "label": _label(scenario_id, attack_id, family, kind, run_id),
                "family": family,
                "slice": slice_name,
            }
        )
    tests.sort(key=lambda test: (test["kind"], test["key"]))

    label_order = {version["label"]: index for index, version in enumerate(versions)}
    cells: list[dict[str, Any]] = []
    for (harness_id, scenario_id, attack_id), episode in latest.items():
        label = labels[harness_id]
        kind = "benign" if _benign(scenario_id) else "adversarial"
        if kind == "benign":
            if episode.legitimate_task_success:
                outcome, reason = "BENIGN_PASS", ""
            else:
                blocked = _harness_block(episode)
                if blocked:
                    outcome, reason = "FALSE_POSITIVE", blocked
                else:
                    outcome, reason = "TASK_FAILED", "model did not complete the task and no harness block was recorded"
        elif episode.attack_success:
            outcome, reason = "BREACH", "attack executed"
        else:
            outcome, reason = "BLOCKED", "attack held"
        cells.append(
            {
                "version": label,
                "test_key": _test_key(scenario_id, attack_id),
                "outcome": outcome,
                "episode_id": episode.id,
                "reason": reason,
            }
        )
    cells.sort(key=lambda cell: (label_order[cell["version"]], cell["test_key"]))

    trend: list[dict[str, Any]] = []
    for version in versions:
        label = version["label"]
        version_cells = [cell for cell in cells if cell["version"] == label]
        adversarial_cells = [
            cell
            for cell in version_cells
            if slices[(cell["test_key"].split("|", 1)[0], cell["test_key"].split("|", 1)[1])] != "benign"
        ]
        benign_cells = [cell for cell in version_cells if cell not in adversarial_cells]
        breaches = sum(cell["outcome"] == "BREACH" for cell in adversarial_cells)
        blocked = sum(cell["outcome"] == "BLOCKED" for cell in adversarial_cells)
        passes = sum(cell["outcome"] == "BENIGN_PASS" for cell in benign_cells)
        trend.append(
            {
                "version": label,
                "asr": round(breaches / len(adversarial_cells), 4) if adversarial_cells else 0.0,
                "benign_success": round(passes / len(benign_cells), 4) if benign_cells else 0.0,
                "block_rate": round(blocked / len(adversarial_cells), 4) if adversarial_cells else 0.0,
                "event": "BASELINE" if version["status"] == "BASELINE" else "PROMOTED",
            }
        )

    # Persisted Atlas recalls for this run, so the memory panel does not depend on the
    # live WebSocket backlog still holding them.
    memory_events = [
        event.model_dump(mode="json")
        for event in await repository.recent_events(limit=5_000)
        if event.type == "memory_retrieved" and event.run_id == run_id
    ]

    return {
        "run_id": run_id,
        "memory_events": memory_events,
        "versions": versions,
        "rejected": rejected,
        "tests": tests,
        "cells": cells,
        "trend": trend,
    }
