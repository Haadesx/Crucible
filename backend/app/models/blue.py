"""Blue-side models: BlueAgentVersion and the Blue-authored HarnessPatch DSL (§9, §10)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.harness.compiler import supported_stage_names

HarnessPatchOp = Literal[
    "ADD_STAGE",
    "REMOVE_STAGE",
    "MOVE_STAGE",
    "SET_PARAMETER",
    "SET_TOOL_PERMISSION",
    "SET_CONTEXT_POLICY",
    "SET_MEMORY_POLICY",
    "SET_SYSTEM_POLICY",
]

# Typing/JSON-schema mirror of the compiler's stage table. ``tests`` pins it to
# ``harness.compiler.supported_stage_names()``; the authority is that table, and
# ``HarnessOperation.validate_target_for_op`` consults it rather than this list.
KnownStage = Literal[
    "ContextBoundary",
    "ProvenanceBoundary",
    "MemoryFilter",
    "GoalBinding",
    "ToolPermission",
    "ArgumentValidator",
    "ApprovalGate",
    "SecondaryVerifier",
    "RiskGate",
]

StageParameter = Literal[
    "isolation_mode",
    "risk_threshold",
    "input_classifier_enabled",
    "input_classifier_threshold",
    "recipient_validation",
    "amount_validation",
    "resource_validation",
    "trust_threshold",
    "filter_mode",
    "trigger_threshold",
    "system_instruction_variant",
]

ToolPermissionMode = Literal["AUTO", "GOAL_BOUND", "REQUIRE_APPROVAL", "DENY"]


class HarnessOperation(BaseModel):
    """One constrained mutation Blue may apply to a harness version."""

    model_config = ConfigDict(extra="forbid")

    op: HarnessPatchOp
    target: str
    value: Any = None
    reason: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def validate_target_for_op(self) -> HarnessOperation:
        # The compiler is the authority on which stages exist; this Literal is only the
        # schema mirror. Validating against the table is what keeps a proposed stage
        # from naming something the compiler would never emit.
        known_stages = set(supported_stage_names())
        parameters = set(get_args(StageParameter))
        tools = {"send_email", "transfer_money", "delete_document"}
        if self.op in {"ADD_STAGE", "REMOVE_STAGE"} and self.target not in known_stages:
            raise ValueError(f"unknown stage target: {self.target}")
        elif self.op == "SET_PARAMETER" and self.target not in parameters:
            raise ValueError(f"unknown parameter target: {self.target}")
        elif self.op == "SET_TOOL_PERMISSION":
            if self.target not in tools and not self.target.startswith("tool_policy.permissions."):
                raise ValueError(f"unknown tool permission target: {self.target}")
        elif self.op == "SET_CONTEXT_POLICY" and self.target not in {
            "isolation_mode",
            "segment_external",
            "system_instruction_variant",
        }:
            raise ValueError(f"unknown context policy target: {self.target}")
        elif self.op == "SET_MEMORY_POLICY" and self.target not in {
            "filter_mode",
            "trust_threshold",
            "retrieve_failure_memories",
            "retrieve_successful_defenses",
        }:
            raise ValueError(f"unknown memory policy target: {self.target}")
        elif self.op == "SET_SYSTEM_POLICY" and self.target not in {"variant", "system_instruction_variant"}:
            raise ValueError(f"unknown system policy target: {self.target}")
        return self


class HarnessPatch(BaseModel):
    """Blue's structured proposal, validated by the application before compilation (§10)."""

    model_config = ConfigDict(extra="forbid")

    analysis: str = Field(min_length=1, max_length=1_200)
    operations: list[HarnessOperation] = Field(min_length=1, max_length=6)
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    expected_effect: str = Field(default="", max_length=800)


class BlueAgentVersion(BaseModel):
    """The defending agent: executor role plus harness-engineer role over one model (§9)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    run_id: str = ""
    generation: int = Field(ge=0)
    parent_ids: list[str] = Field(default_factory=list)

    base_model: str
    executor_system_policy: str = Field(min_length=1, max_length=2_000)
    harness_engineer_policy: str = Field(default="", max_length=2_000)
    harness_version_id: str
    memory_policy_id: str = "default"
    fitness: float | None = Field(default=None, ge=0, le=1)
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


CandidateStatus = Literal[
    "PROPOSED",
    "VALIDATED",
    "COMPILED",
    "DEPLOYED_FOR_EVAL",
    "EVALUATED",
    "PROMOTED",
    "REJECTED",
]

# The only legal moves (§31). A candidate may be rejected from any unfinished stage;
# PROMOTED and REJECTED are final, so they have no entry.
_NEXT_STATUS: dict[str, set[str]] = {
    "PROPOSED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"COMPILED", "REJECTED"},
    "COMPILED": {"DEPLOYED_FOR_EVAL", "REJECTED"},
    "DEPLOYED_FOR_EVAL": {"EVALUATED", "REJECTED"},
    "EVALUATED": {"PROMOTED", "REJECTED"},
}


class CandidateTransition(BaseModel):
    """One step a candidate actually took, with when and why."""

    model_config = ConfigDict(extra="forbid")

    status: CandidateStatus
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str = ""


class SliceMetrics(BaseModel):
    """Security and utility on one part of the evaluation battery."""

    model_config = ConfigDict(extra="forbid")

    episodes: int = Field(ge=0)
    security: float = Field(ge=0, le=1)
    utility: float = Field(ge=0, le=1)


class BlueMetrics(BaseModel):
    """What §32 collects for one harness: security, utility, latency, cost and the fitness they make."""

    model_config = ConfigDict(extra="forbid")

    fitness: float = Field(default=0.0, ge=0, le=1)
    block_rate: float = Field(default=0.0, ge=0, le=1)
    utility_rate: float = Field(default=0.0, ge=0, le=1)
    latency_penalty: float = Field(default=0.0, ge=0, le=1)
    cost_penalty: float = Field(default=0.0, ge=0, le=1)
    battles: int = Field(default=0, ge=0)
    # current attacks / hall of fame / holdout / benign, so a candidate that only fixes
    # the attack it was shown is visible as such.
    slices: dict[str, SliceMetrics] = Field(default_factory=dict)


class HarnessPatchRecord(BaseModel):
    """Persisted proof that Blue authored a patch, and every step that patch then took (§27, §31).

    ``status`` and ``transitions`` are the candidate lifecycle; ``advance`` is the only
    supported writer, and it is called only after the action it names has happened.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    run_id: str
    generation: int = Field(ge=0)
    parent_harness_id: str
    child_harness_id: str | None = None
    patch: HarnessPatch
    model_call_id: str = ""
    # The engineer's accepted completion verbatim. The ledger row keeps only the first
    # 4000 characters; this is the proof of what Blue actually said.
    raw_response: str = ""
    # Ledger ids of earlier attempts the validator refused before this one was accepted.
    repair_call_ids: list[str] = Field(default_factory=list)
    valid: bool = True
    rejection_reason: str = ""
    status: CandidateStatus = "PROPOSED"
    transitions: list[CandidateTransition] = Field(default_factory=list)
    metrics: BlueMetrics | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def start_the_transition_log(self) -> HarnessPatchRecord:
        if not self.transitions:
            self.transitions.append(CandidateTransition(status=self.status, at=self.created_at))
        return self

    @property
    def decision(self) -> str:
        """Why the candidate ended as it did; empty while it is still in flight."""
        return self.transitions[-1].detail if self.status in {"PROMOTED", "REJECTED"} else ""

    def advance(self, status: CandidateStatus, detail: str = "") -> None:
        if status not in _NEXT_STATUS.get(self.status, set()):
            raise ValueError(f"illegal candidate transition {self.status} -> {status}")
        self.status = status
        self.transitions.append(CandidateTransition(status=status, detail=detail))
