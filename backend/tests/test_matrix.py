"""Matrix contract: five outcomes, false-positive vs task-failure, missing cells, ordering.

All fixtures are persisted records (no mocks of derivation code); the matrix is asked
for the same way the API asks for it, so a failure here is the contract breaking.
"""

from datetime import UTC, datetime, timedelta

from app.coevolution.matrix import build_matrix
from app.memory.repository import InMemoryRepository
from app.models.audit import ModelCall
from app.models.blue import BlueMetrics, HarnessOperation, HarnessPatch, HarnessPatchRecord
from app.models.episode import Episode
from app.models.harness import HarnessDeployment, HarnessRecord, HarnessVersion
from app.models.red import AttackCandidate
from app.models.tool import GatewayDecision, ProposedToolCall

RUN = "T-MATRIX"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
ENGINEER = "nvidia/nemotron-3-super-120b-a12b:free"


def _minute(offset: int) -> datetime:
    return NOW + timedelta(minutes=offset)


def _harness(harness_id: str, generation: int, parent_id: str | None = None) -> HarnessRecord:
    return HarnessRecord(
        version=HarnessVersion(id=harness_id, generation=generation, parent_id=parent_id, run_id=RUN),
        deployment=HarnessDeployment(
            id=f"DEP-{harness_id}", version_id=harness_id, status="PROMOTED", promoted_at=NOW
        ),
    )


def _patch(
    record_id: str,
    child: str,
    parent: str,
    *,
    status: str,
    created_at: datetime,
    model_call_id: str = "",
    reason: str = "",
) -> HarnessPatchRecord:
    return HarnessPatchRecord(
        id=record_id,
        run_id=RUN,
        generation=2,
        parent_harness_id=parent,
        child_harness_id=child,
        patch=HarnessPatch(
            analysis="bind tools to the user goal",
            operations=[HarnessOperation(op="ADD_STAGE", target="GoalBinding", value=None, reason="bind")],
            expected_effect="blocks the injected recipient",
        ),
        status=status,  # type: ignore[arg-type]
        model_call_id=model_call_id,
        rejection_reason=reason,
        metrics=BlueMetrics(fitness=0.7, block_rate=1.0, utility_rate=0.6, battles=6),
        created_at=created_at,
    )


def _episode(
    episode_id: str,
    harness_id: str,
    scenario_id: str,
    attack_id: str,
    *,
    generation: int,
    attack_success: bool,
    legitimate_task_success: bool,
    created_at: datetime,
    decisions: list[GatewayDecision] | None = None,
) -> Episode:
    gateway = decisions or []
    proposed = [
        ProposedToolCall(
            call_id=f"{episode_id}-{index}",
            name="send_email",
            arguments={"to": "alice@example.test", "subject": "s", "body": "b"},
            instruction_source="user",
        )
        for index in range(len(gateway))
    ]
    return Episode(
        id=episode_id,
        run_id=RUN,
        generation=generation,
        attack_id=attack_id,
        defense_id=f"B-{RUN}-G00-B0",
        harness_id=harness_id,
        scenario_id=scenario_id,
        user_prompt="send the summary",
        attack_payload="",
        proposed_tool_calls=proposed,
        gateway_decisions=gateway,
        attack_success=attack_success,
        legitimate_task_success=legitimate_task_success,
        security_score=1.0 if not attack_success else 0.0,
        utility_score=1.0 if legitimate_task_success else 0.0,
        latency_ms=1,
        model_calls=1,
        created_at=created_at,
    )


async def _seed() -> InMemoryRepository:
    repository = InMemoryRepository()
    await repository.start()
    await repository.save_harness(_harness("B-T-MATRIX-B0", 0))
    await repository.save_harness(_harness("B-T-MATRIX-C1", 1, "B-T-MATRIX-B0"))
    await repository.save_harness(_harness("B-T-MATRIX-C3", 2, "B-T-MATRIX-C1"))
    await repository.save_patch_record(
        _patch("PATCH-1", "B-T-MATRIX-C1", "B-T-MATRIX-B0", status="PROMOTED", created_at=_minute(1), model_call_id="CALL-ENG")
    )
    await repository.save_patch_record(
        _patch("PATCH-2", "B-T-MATRIX-C2", "B-T-MATRIX-C1", status="REJECTED", created_at=_minute(2), reason="utility floor: benign 0.40 < 0.50")
    )
    await repository.save_patch_record(
        _patch("PATCH-3", "B-T-MATRIX-C3", "B-T-MATRIX-C1", status="PROMOTED", created_at=_minute(3), model_call_id="CALL-ENG")
    )
    await repository.save_model_call(
        ModelCall(
            id="CALL-ENG",
            run_id=RUN,
            generation=2,
            provider="openrouter",
            model=ENGINEER,
            role="blue_harness_engineer",
            input_hash="hash",
            prompt_chars=1,
            latency_ms=1,
            created_at=_minute(1),
        )
    )
    await repository.save_attack_candidate(
        AttackCandidate(
            id="A-T-MATRIX-G00-aaa",
            run_id=RUN,
            red_agent_version_id="R-1",
            scenario_id="DOC-001",
            attack_family="tool_output_injection",
            carrier="document",
            target_capability="exfiltrate",
            payload="payload aaa",
            generated_by_model="test-red",
            generation=0,
            created_at=_minute(0),
        )
    )
    await repository.save_attack_candidate(
        AttackCandidate(
            id="A-T-MATRIX-G00-bbb",
            run_id=RUN,
            red_agent_version_id="R-1",
            scenario_id="TOOL-001",
            attack_family="authority_confusion",
            carrier="document",
            target_capability="exfiltrate",
            payload="payload bbb",
            generated_by_model="test-red",
            generation=0,
            created_at=_minute(0),
        )
    )
    attack = "GN-A-T-MATRIX-G00-aaa"
    other = "GN-A-T-MATRIX-G00-bbb"
    await repository.save_episode(
        _episode("EP-1", "B-T-MATRIX-B0", "DOC-001", attack, generation=0, attack_success=True, legitimate_task_success=False, created_at=_minute(1))
    )
    await repository.save_episode(
        _episode("EP-2", "B-T-MATRIX-C1", "DOC-001", attack, generation=1, attack_success=False, legitimate_task_success=True, created_at=_minute(2))
    )
    await repository.save_episode(
        _episode("EP-3", "B-T-MATRIX-B0", "TOOL-001", other, generation=0, attack_success=False, legitimate_task_success=True, created_at=_minute(1))
    )
    await repository.save_episode(
        _episode("EP-4", "B-T-MATRIX-B0", "BENIGN-DOC-001", "BENIGN-BENIGN-DOC-001", generation=0, attack_success=False, legitimate_task_success=True, created_at=_minute(1))
    )
    await repository.save_episode(
        _episode(
            "EP-5",
            "B-T-MATRIX-C1",
            "BENIGN-DOC-002",
            "BENIGN-BENIGN-DOC-002",
            generation=1,
            attack_success=False,
            legitimate_task_success=False,
            created_at=_minute(2),
            decisions=[GatewayDecision(decision="deny", risk_score=0.9, reason_codes=["GOAL_BINDING_VIOLATION"])],
        )
    )
    await repository.save_episode(
        _episode(
            "EP-6",
            "B-T-MATRIX-C1",
            "BENIGN-DOC-003",
            "BENIGN-BENIGN-DOC-003",
            generation=1,
            attack_success=False,
            legitimate_task_success=False,
            created_at=_minute(2),
            decisions=[GatewayDecision(decision="allow", risk_score=0.1, reason_codes=[])],
        )
    )
    return repository


async def test_matrix_reports_versions_rejections_and_all_five_outcomes() -> None:
    repository = await _seed()
    matrix = await build_matrix(repository, RUN)

    versions = matrix["versions"]
    assert [version["label"] for version in versions] == ["V0", "V1", "V2"], "promotion order must drive labels"
    assert versions[0] == {
        "label": "V0",
        "harness_id": "B-T-MATRIX-B0",
        "parent_id": None,
        "generation": 0,
        "patch_id": None,
        "status": "BASELINE",
        "fitness": None,
        "block_rate": None,
        "utility_rate": None,
        "engineer_model": None,
    }
    assert versions[1]["harness_id"] == "B-T-MATRIX-C1" and versions[1]["parent_id"] == "B-T-MATRIX-B0"
    assert versions[1]["patch_id"] == "PATCH-1"
    assert versions[1]["engineer_model"] == ENGINEER
    assert versions[1]["fitness"] == 0.7
    assert versions[2]["harness_id"] == "B-T-MATRIX-C3" and versions[2]["patch_id"] == "PATCH-3"

    assert len(matrix["rejected"]) == 1
    rejected = matrix["rejected"][0]
    assert rejected["harness_id"] == "B-T-MATRIX-C2" and rejected["patch_id"] == "PATCH-2"
    assert "utility floor" in rejected["reason"]
    assert rejected["fitness"] == 0.7 and rejected["block_rate"] == 1.0

    cells = {(cell["version"], cell["test_key"]): cell for cell in matrix["cells"]}
    attack = "DOC-001|GN-A-T-MATRIX-G00-aaa"
    other = "TOOL-001|GN-A-T-MATRIX-G00-bbb"
    assert cells[("V0", attack)]["outcome"] == "BREACH"
    assert cells[("V1", attack)]["outcome"] == "BLOCKED"
    assert cells[("V0", other)]["outcome"] == "BLOCKED"
    assert cells[("V0", "BENIGN-DOC-001|BENIGN-BENIGN-DOC-001")]["outcome"] == "BENIGN_PASS"
    assert cells[("V1", "BENIGN-DOC-002|BENIGN-BENIGN-DOC-002")]["outcome"] == "FALSE_POSITIVE"
    assert "GOAL_BINDING_VIOLATION" in cells[("V1", "BENIGN-DOC-002|BENIGN-BENIGN-DOC-002")]["reason"]
    assert cells[("V1", "BENIGN-DOC-003|BENIGN-BENIGN-DOC-003")]["outcome"] == "TASK_FAILED"
    assert cells[("V1", "BENIGN-DOC-003|BENIGN-BENIGN-DOC-003")]["reason"].startswith("model did not complete the task")

    # A pair that never ran has no cell; the UI renders "not run".
    assert ("V1", other) not in cells
    assert all(cell["episode_id"] for cell in matrix["cells"])


async def test_matrix_tests_carry_kind_family_and_slice_from_the_latest_episode() -> None:
    repository = await _seed()
    matrix = await build_matrix(repository, RUN)

    tests = {test["key"]: test for test in matrix["tests"]}
    attack = "DOC-001|GN-A-T-MATRIX-G00-aaa"
    other = "TOOL-001|GN-A-T-MATRIX-G00-bbb"
    assert tests[attack]["kind"] == "adversarial"
    assert tests[attack]["family"] == "tool_output_injection"
    # The later C1 replay makes the known breach a regression test, not a fresh one.
    assert tests[attack]["slice"] == "regression"
    assert tests[other]["slice"] == "current"
    benign_key = "BENIGN-DOC-002|BENIGN-BENIGN-DOC-002"
    assert tests[benign_key]["kind"] == "benign"
    assert tests[benign_key]["family"] is None
    assert tests[benign_key]["slice"] == "benign"


async def test_matrix_trend_counts_cells_per_version_and_marks_the_baseline() -> None:
    repository = await _seed()
    matrix = await build_matrix(repository, RUN)
    trend = {row["version"]: row for row in matrix["trend"]}

    assert trend["V0"] == {"version": "V0", "asr": 0.5, "benign_success": 1.0, "block_rate": 0.5, "event": "BASELINE"}
    assert trend["V1"] == {"version": "V1", "asr": 0.0, "benign_success": 0.0, "block_rate": 1.0, "event": "PROMOTED"}
    assert trend["V2"]["event"] == "PROMOTED"
    assert trend["V2"]["asr"] == 0.0


async def test_matrix_is_empty_but_well_formed_for_an_unknown_run() -> None:
    repository = InMemoryRepository()
    await repository.start()

    matrix = await build_matrix(repository, "NO-SUCH-RUN")

    assert matrix == {
        "run_id": "NO-SUCH-RUN",
        "memory_events": [],
        "versions": [],
        "rejected": [],
        "tests": [],
        "cells": [],
        "trend": [],
    }
