"""Apply a Blue-authored HarnessPatch to produce a child HarnessVersion (§10, §11).

Every operation is translated into a real policy switch that the HarnessCompiler
turns into executing runtime stages. An operation that cannot be honoured is
recorded as skipped with a reason instead of being silently dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.harness.compiler import stage_spec, supported_stage_names
from app.models.blue import HarnessPatch
from app.models.harness import HarnessVersion

_TOOLS = ("send_email", "transfer_money", "delete_document")

# ``approval_policy`` is keyed by capability, not by tool name. Writing the tool
# name straight into it produced keys the model forbids, so every ADD_STAGE
# ApprovalGate silently failed validation instead of adding a gate.
_APPROVAL_TARGETS = {
    "send_email": "email",
    "transfer_money": "transfer",
    "delete_document": "delete",
}

_PARAMETER_TARGETS: dict[str, tuple[str, str]] = {
    "isolation_mode": ("context_policy", "isolation_mode"),
    "segment_external": ("context_policy", "segment_external"),
    "system_instruction_variant": ("system_instruction_policy", "variant"),
    "risk_threshold": ("tool_policy", "risk_threshold"),
    "input_classifier_enabled": ("validation_policy", "input_classifier_enabled"),
    "input_classifier_threshold": ("validation_policy", "input_classifier_threshold"),
    "recipient_validation": ("validation_policy", "recipient_validation"),
    "amount_validation": ("validation_policy", "amount_validation"),
    "resource_validation": ("validation_policy", "resource_validation"),
    "trust_threshold": ("memory_policy", "trust_threshold"),
    "filter_mode": ("memory_policy", "filter_mode"),
    "retrieve_failure_memories": ("memory_policy", "retrieve_failure_memories"),
    "retrieve_successful_defenses": ("memory_policy", "retrieve_successful_defenses"),
    "trigger_threshold": ("verifier_policy", "trigger_threshold"),
}

_CONTEXT_TARGETS = {"isolation_mode", "segment_external", "system_instruction_variant"}
_MEMORY_TARGETS = {
    "filter_mode",
    "trust_threshold",
    "retrieve_failure_memories",
    "retrieve_successful_defenses",
}
_SYSTEM_TARGETS = {"system_instruction_variant", "variant"}


def _set(values: dict[str, Any], section: str, field: str, value: Any) -> None:
    values[section][field] = value


def _ok(stage: str) -> str:
    return f"{stage} policy switch updated"


def _unknown_stage_reason(stage: str) -> str:
    return (
        f"unknown stage {stage!r}: the compiler can only emit "
        f"{', '.join(supported_stage_names())}. Use one of those exact names."
    )


def _normalise_permissions(value: Any) -> dict[str, str] | None:
    if isinstance(value, str) and value in _TOOLS:
        return {value: "REQUIRE_APPROVAL"}
    if isinstance(value, dict):
        modes: dict[str, str] = {}
        for tool, mode in value.items():
            if tool in _TOOLS and isinstance(mode, str):
                modes[tool] = mode
        return modes or None
    if value in (None, True, "all", "all_tools"):
        return {tool: "REQUIRE_APPROVAL" for tool in _TOOLS}
    return None


def _apply_stage(values: dict[str, Any], stage: str, value: Any, enable: bool) -> tuple[bool, str]:
    """Translate ADD_STAGE/REMOVE_STAGE into the policy switches the compiler reads.

    The stage must be one the compiler can actually emit. That set is owned by
    ``app.harness.compiler`` and looked up here rather than copied, so a name this
    function accepts is by construction a name that compiles to a real stage. An
    unknown name is refused with the supported set spelled out, because the caller's
    next move is to propose a real stage instead of retrying the same no-op.
    """
    if stage_spec(stage) is None:
        return False, _unknown_stage_reason(stage)
    if stage == "ContextBoundary":
        if enable:
            if values["context_policy"]["isolation_mode"] == "FLAT":
                _set(values, "context_policy", "isolation_mode", "SEGMENTED")
            _set(values, "context_policy", "segment_external", True)
        else:
            _set(values, "context_policy", "isolation_mode", "FLAT")
            _set(values, "context_policy", "segment_external", False)
        return True, _ok(stage)
    if stage == "ProvenanceBoundary":
        _set(values, "trust_policy", "enabled", enable)
        if enable:
            _set(values, "trust_policy", "external_content_trusted", False)
            _set(values, "trust_policy", "tool_outputs_trusted", False)
            _set(values, "trust_policy", "provenance_required", True)
        return True, _ok(stage)
    if stage == "MemoryFilter":
        _set(values, "memory_policy", "filter_mode", "TRUSTED_ONLY" if enable else "OFF")
        return True, _ok(stage)
    if stage == "GoalBinding":
        _set(values, "tool_policy", "goal_binding_enabled", enable)
        return True, _ok(stage)
    if stage == "ToolPermission":
        modes = _normalise_permissions(value)
        if modes is None:
            return False, f"{stage}: no supported tool permissions in value={value!r}"
        for tool, mode in modes.items():
            values["tool_policy"]["permissions"][tool] = mode if enable else "AUTO"
        return True, _ok(stage)
    if stage == "ArgumentValidator":
        checks = (
            value
            if isinstance(value, list)
            else ["recipient_validation", "amount_validation", "resource_validation"]
        )
        applied = False
        for check in checks:
            if check in {
                "recipient_validation",
                "amount_validation",
                "resource_validation",
                "input_classifier_enabled",
            }:
                _set(values, "validation_policy", check, bool(enable))
                applied = True
        if not applied:
            return False, f"{stage}: no supported checks in value={value!r}"
        return True, _ok(stage)
    if stage == "ApprovalGate":
        tools = value if isinstance(value, list) else list(_TOOLS)
        applied = False
        for tool in tools:
            target = _APPROVAL_TARGETS.get(tool) if isinstance(tool, str) else None
            if target is not None:
                values["approval_policy"][target] = bool(enable)
                applied = True
        if not applied:
            return False, f"{stage}: no supported tools in value={value!r}"
        return True, _ok(stage)
    if stage == "SecondaryVerifier":
        _set(values, "verifier_policy", "enabled", enable)
        return True, _ok(stage)
    if stage == "RiskGate":
        _set(values, "tool_policy", "gateway_enabled", enable)
        return True, _ok(stage)
    return False, _unknown_stage_reason(stage)


def uncompiled_stages(child: HarnessVersion, patch: HarnessPatch) -> list[str]:
    """Stages the patch asked to add that the compiler will not actually emit.

    The authority is the compiler's own ``present`` predicate applied to the resulting
    child, so this also catches a correctly named stage whose value fails to switch the
    policy on — ``ADD_STAGE ArgumentValidator`` with no recognised check, say. A patch
    that would only add decoration is not a patch, so the caller rejects it outright
    instead of scoring and promoting a child that enforces nothing new.
    """
    missing: list[str] = []
    for operation in patch.operations:
        if operation.op != "ADD_STAGE":
            continue
        spec = stage_spec(operation.target)
        if spec is None or not spec.present(child):
            missing.append(operation.target)
    return missing


def describe_rejection(records: list[dict[str, Any]]) -> str:
    """A message the harness engineer can act on, naming the operations that failed."""
    failed = [record for record in records if not record["applied"]]
    if not failed:
        return "the patch produced no applicable change"
    details = "; ".join(f"{record['op']} {record['target']}: {record['reason']}" for record in failed)
    return f"no operation could be applied: {details}"


def apply_patch(
    parent: HarnessVersion,
    patch: HarnessPatch,
    *,
    version_id: str,
    generation: int,
) -> tuple[HarnessVersion | None, list[dict[str, Any]]]:
    """Return the child version produced by ``patch`` (None if nothing applied)."""
    values = parent.model_dump(mode="python")
    values.pop("runtime_graph", None)
    records: list[dict[str, Any]] = []
    for operation in patch.operations:
        target = operation.target
        value = operation.value
        applied = False
        reason = operation.reason
        if operation.op in {"ADD_STAGE", "REMOVE_STAGE"}:
            applied, reason = _apply_stage(values, target, value, enable=operation.op == "ADD_STAGE")
        elif operation.op == "SET_TOOL_PERMISSION":
            modes = _normalise_permissions({target: value} if value is not None else None)
            if modes:
                for tool, mode in modes.items():
                    values["tool_policy"]["permissions"][tool] = mode
                applied = True
        elif operation.op == "SET_PARAMETER":
            path = _PARAMETER_TARGETS.get(target)
            if path is not None:
                _set(values, path[0], path[1], value)
                applied = True
        elif operation.op == "SET_CONTEXT_POLICY":
            if target in _CONTEXT_TARGETS:
                _set(values, "context_policy", target, value)
                applied = True
        elif operation.op == "SET_MEMORY_POLICY":
            if target in _MEMORY_TARGETS:
                _set(values, "memory_policy", target, value)
                applied = True
        elif operation.op == "SET_SYSTEM_POLICY":
            if target in _SYSTEM_TARGETS:
                _set(values, "system_instruction_policy", "variant", value)
                _set(values, "context_policy", "system_instruction_variant", value)
                applied = True
        elif operation.op == "MOVE_STAGE":
            reason = "stage order is compiler-owned; express reordering with ADD_STAGE/SET_* operations"
        records.append(
            {
                "op": operation.op,
                "target": target,
                "value": str(value)[:120] if value is not None else "",
                "reason": reason[:300],
                "applied": applied,
            }
        )
    if not any(record["applied"] for record in records):
        return None, records
    values.update(
        {
            "id": version_id,
            "generation": generation,
            "parent_id": parent.id,
            "parent_ids": [parent.id],
            "mutation_reason": patch.analysis[:400],
            "mutation_set": records,
            "mutation_evidence": patch.retrieved_memory_ids,
            "historical_matches": patch.retrieved_memory_ids,
            "expected_effect": patch.expected_effect,
            "status": "CANDIDATE",
            "created_at": datetime.now(UTC),
            "fitness": None,
            "activated_at": None,
            "promoted_at": None,
        }
    )
    try:
        child = HarnessVersion.model_validate(values)
    except ValueError:
        # Invalid values (out-of-range thresholds, bad literals) fail validation here.
        return None, records
    # An ADD_STAGE the compiler will not emit is decoration, not defense. Rejecting
    # here is what stops a no-op patch from being persisted, scored and promoted as if
    # it had added an executing stage.
    missing = uncompiled_stages(child, patch)
    if missing:
        detail = ", ".join(missing)
        return None, [
            *records,
            {
                "op": "ADD_STAGE",
                "target": detail,
                "value": "",
                "reason": (
                    "these stages would not appear in the compiled harness graph, so the "
                    f"patch adds no executing stage; use one of {', '.join(supported_stage_names())} "
                    "with a value the compiler recognises"
                ),
                "applied": False,
            },
        ]
    if child.context_policy.system_instruction_variant == "strict":
        child = child.model_copy(update={"context_policy": child.context_policy.model_copy(update={"isolation_mode": "STRICT"})})
    return child, records
