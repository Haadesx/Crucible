from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ContextIsolationMode = Literal["FLAT", "SEGMENTED", "STRICT"]
MemoryFilterMode = Literal["OFF", "TRUSTED_ONLY", "SIMILARITY_TRUSTED"]
PermissionMode = Literal["AUTO", "GOAL_BOUND", "REQUIRE_APPROVAL", "DENY"]
HarnessStatus = Literal["CANDIDATE", "COMPILED", "EVALUATING", "ACTIVE", "ELITE", "REJECTED", "ANCESTOR"]
HarnessDeploymentStatus = Literal["REGISTERED", "COMPILED", "ACTIVE", "REJECTED", "PROMOTED"]
TraceStatus = Literal["PASS", "FAIL", "BLOCKED", "SKIPPED", "EXECUTED", "PENDING"]

# A harness lifecycle position is ONE fact with three renderings, and this table is
# the only thing that says how they relate. `HarnessDeployment.status` is the
# authority: it is the vocabulary the registry writes, the API reads and the stored
# documents carry. `HarnessVersion.status` and `HarnessMetrics.candidate_status` are
# that same position in the richer candidate vocabulary. `HarnessRecord.set_status`
# is the only supported writer and `HarnessRecord.reconcile_status` re-derives the
# two projections on every construction, so the three can no longer drift apart.
LIFECYCLE_RENDERING: dict[HarnessDeploymentStatus, HarnessStatus] = {
    "REGISTERED": "CANDIDATE",
    "COMPILED": "COMPILED",
    "ACTIVE": "ACTIVE",
    "REJECTED": "REJECTED",
    "PROMOTED": "ELITE",
}


class ContextPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isolation_mode: ContextIsolationMode = "FLAT"
    segment_external: bool = False
    system_instruction_variant: Literal["baseline", "provenance_aware", "strict"] = "baseline"


class TrustPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    external_content_trusted: bool = False
    tool_outputs_trusted: bool = False
    untrusted_risk_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    provenance_required: bool = True


class MemoryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filter_mode: MemoryFilterMode = "OFF"
    trust_threshold: float = Field(default=0.80, ge=0, le=1)
    retrieve_failure_memories: bool = False
    retrieve_successful_defenses: bool = False


class ToolPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway_enabled: bool = True
    goal_binding_enabled: bool = False
    risk_threshold: float = Field(default=0.70, ge=0, le=1)
    permissions: dict[str, PermissionMode] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_permissions(self) -> ToolPolicy:
        allowed = {"send_email", "transfer_money", "delete_document"}
        unknown = set(self.permissions) - allowed
        if unknown:
            raise ValueError(f"unknown tool permissions: {sorted(unknown)}")
        return self


class ValidationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_classifier_enabled: bool = False
    input_classifier_threshold: float = Field(default=0.70, ge=0, le=1)
    recipient_validation: bool = False
    amount_validation: bool = False
    resource_validation: bool = False


class ApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: bool = False
    transfer: bool = True
    delete: bool = True


class VerifierPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    verifier_model: str = "deterministic-secondary"
    trigger_threshold: float = Field(default=0.70, ge=0, le=1)


class SystemInstructionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: Literal["baseline", "provenance_aware", "strict"] = "baseline"
    max_policy_chars: int = Field(default=2_400, ge=200, le=10_000)


class HarnessGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    kind: Literal["input", "context", "agent", "policy", "tool", "memory", "verifier"]
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class HarnessGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    condition: str | None = None


class HarnessGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[HarnessGraphNode] = Field(default_factory=list)
    edges: list[HarnessGraphEdge] = Field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {node.id for node in self.nodes}


class HarnessVersion(BaseModel):
    """Executable, versioned description of the target agent's runtime environment."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    generation: int = Field(ge=0)
    parent_id: str | None = None
    parent_ids: list[str] = Field(default_factory=list)

    context_policy: ContextPolicy = Field(default_factory=ContextPolicy)
    trust_policy: TrustPolicy = Field(default_factory=TrustPolicy)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    validation_policy: ValidationPolicy = Field(default_factory=ValidationPolicy)
    approval_policy: ApprovalPolicy = Field(default_factory=ApprovalPolicy)
    verifier_policy: VerifierPolicy = Field(default_factory=VerifierPolicy)
    system_instruction_policy: SystemInstructionPolicy = Field(default_factory=SystemInstructionPolicy)

    mutation_reason: str = ""
    mutation_set: list[dict[str, str | float | bool]] = Field(default_factory=list)
    mutation_evidence: list[str] = Field(default_factory=list)
    expected_effect: str = ""
    historical_matches: list[str] = Field(default_factory=list)
    fitness: float | None = Field(default=None, ge=0, le=1)
    attack_coverage: float = Field(default=0.0, ge=0, le=1)
    utility_score: float = Field(default=0.0, ge=0, le=1)
    status: HarnessStatus = "CANDIDATE"
    runtime_graph: HarnessGraph = Field(default_factory=HarnessGraph)
    run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    compiled_at: datetime | None = None
    activated_at: datetime | None = None
    promoted_at: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lineage(self) -> HarnessVersion:
        if self.generation == 0 and (self.parent_id or self.parent_ids):
            raise ValueError("generation 0 harness versions cannot have parents")
        if self.generation > 0 and not (self.parent_id or self.parent_ids):
            raise ValueError("evolved harness versions must identify a parent")
        if self.parent_id and self.parent_ids and self.parent_id not in self.parent_ids:
            raise ValueError("parent_id must be included in parent_ids")
        return self

    @classmethod
    def naked(cls, *, version_id: str = "HARNESS-OFF", generation: int = 0) -> HarnessVersion:
        """A deliberately unguarded control condition for A/B demonstrations."""

        return cls(
            id=version_id,
            generation=generation,
            context_policy=ContextPolicy(isolation_mode="FLAT", segment_external=False),
            trust_policy=TrustPolicy(enabled=False, provenance_required=False),
            tool_policy=ToolPolicy(
                gateway_enabled=False,
                goal_binding_enabled=False,
                permissions={
                    "send_email": "AUTO",
                    "transfer_money": "AUTO",
                    "delete_document": "AUTO",
                },
            ),
            approval_policy=ApprovalPolicy(email=False, transfer=False, delete=False),
            validation_policy=ValidationPolicy(),
            verifier_policy=VerifierPolicy(enabled=False),
            mutation_reason="Naked agent control: all harness gates disabled.",
            status="ACTIVE",
        )

    @classmethod
    def from_defense(cls, defense: Any) -> HarnessVersion:
        """Adapt the original flat DefenseGenome without losing its semantics."""

        context_mode: ContextIsolationMode
        if defense.goal_binding_enabled or defense.system_policy_variant in {"goal_bound", "layered"}:
            context_mode = "STRICT"
        elif defense.trust_external_content is False or defense.system_policy_variant == "distrust_external":
            context_mode = "SEGMENTED"
        else:
            context_mode = "FLAT"
        permissions: dict[str, PermissionMode] = {}
        for tool, approval in (
            ("send_email", defense.require_approval_email),
            ("transfer_money", defense.require_approval_transfer),
            ("delete_document", defense.require_approval_delete),
        ):
            permissions[tool] = "REQUIRE_APPROVAL" if approval else "AUTO"
        return cls(
            id=defense.id,
            generation=defense.generation,
            parent_id=defense.parent_ids[0] if defense.parent_ids else None,
            parent_ids=list(defense.parent_ids),
            context_policy=ContextPolicy(
                isolation_mode=context_mode,
                segment_external=context_mode != "FLAT",
                system_instruction_variant=(
                    "strict" if context_mode == "STRICT" else "provenance_aware" if context_mode == "SEGMENTED" else "baseline"
                ),
            ),
            trust_policy=TrustPolicy(
                enabled=not defense.trust_external_content or not defense.trust_tool_outputs,
                external_content_trusted=defense.trust_external_content,
                tool_outputs_trusted=defense.trust_tool_outputs,
                untrusted_risk_multiplier=1.0,
                provenance_required=defense.goal_binding_enabled or context_mode != "FLAT",
            ),
            memory_policy=MemoryPolicy(
                filter_mode="TRUSTED_ONLY" if defense.memory_filter_enabled else "OFF",
                retrieve_failure_memories=defense.memory_filter_enabled,
                retrieve_successful_defenses=defense.memory_filter_enabled,
            ),
            tool_policy=ToolPolicy(
                gateway_enabled=defense.tool_firewall_enabled,
                goal_binding_enabled=defense.goal_binding_enabled,
                risk_threshold=defense.tool_risk_threshold,
                permissions=permissions,
            ),
            validation_policy=ValidationPolicy(
                input_classifier_enabled=defense.input_classifier_enabled,
                input_classifier_threshold=defense.input_classifier_threshold,
                recipient_validation=defense.recipient_validation,
                amount_validation=defense.amount_validation,
                resource_validation=defense.resource_validation,
            ),
            approval_policy=ApprovalPolicy(
                email=defense.require_approval_email,
                transfer=defense.require_approval_transfer,
                delete=defense.require_approval_delete,
            ),
            verifier_policy=VerifierPolicy(enabled=defense.secondary_verifier_enabled),
            system_instruction_policy=SystemInstructionPolicy(
                variant=(
                    "strict" if defense.system_policy_variant == "layered" else "provenance_aware" if defense.system_policy_variant in {"distrust_external", "goal_bound"} else "baseline"
                )
            ),
            mutation_reason=defense.mutation_reason,
            status="ACTIVE" if defense.generation == 0 else "CANDIDATE",
        )

    def to_defense(self) -> Any:
        from app.models.defense import DefenseGenome

        return DefenseGenome(
            id=self.id,
            generation=self.generation,
            parent_ids=self.parent_ids,
            trust_external_content=self.trust_policy.external_content_trusted,
            trust_tool_outputs=self.trust_policy.tool_outputs_trusted,
            goal_binding_enabled=self.tool_policy.goal_binding_enabled,
            input_classifier_enabled=self.validation_policy.input_classifier_enabled,
            input_classifier_threshold=self.validation_policy.input_classifier_threshold,
            tool_firewall_enabled=self.tool_policy.gateway_enabled,
            tool_risk_threshold=self.tool_policy.risk_threshold,
            recipient_validation=self.validation_policy.recipient_validation,
            amount_validation=self.validation_policy.amount_validation,
            resource_validation=self.validation_policy.resource_validation,
            require_approval_email=self.approval_policy.email,
            require_approval_transfer=self.approval_policy.transfer,
            require_approval_delete=self.approval_policy.delete,
            secondary_verifier_enabled=self.verifier_policy.enabled,
            memory_filter_enabled=self.memory_policy.filter_mode != "OFF",
            system_policy_variant=(
                "layered" if self.system_instruction_policy.variant == "strict" else "goal_bound" if self.context_policy.isolation_mode == "STRICT" else "distrust_external" if self.context_policy.isolation_mode == "SEGMENTED" else "baseline"
            ),
            mutation_reason=self.mutation_reason,
        )


class HarnessChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: str | float | bool

    @model_validator(mode="after")
    def validate_path(self) -> HarnessChange:
        allowed = {
            "context_policy.isolation_mode",
            "context_policy.segment_external",
            "context_policy.system_instruction_variant",
            "trust_policy.enabled",
            "trust_policy.external_content_trusted",
            "trust_policy.tool_outputs_trusted",
            "trust_policy.untrusted_risk_multiplier",
            "trust_policy.provenance_required",
            "memory_policy.filter_mode",
            "memory_policy.trust_threshold",
            "memory_policy.retrieve_failure_memories",
            "memory_policy.retrieve_successful_defenses",
            "tool_policy.gateway_enabled",
            "tool_policy.goal_binding_enabled",
            "tool_policy.risk_threshold",
            "tool_policy.permissions.send_email",
            "tool_policy.permissions.transfer_money",
            "tool_policy.permissions.delete_document",
            "validation_policy.input_classifier_enabled",
            "validation_policy.input_classifier_threshold",
            "validation_policy.recipient_validation",
            "validation_policy.amount_validation",
            "validation_policy.resource_validation",
            "approval_policy.email",
            "approval_policy.transfer",
            "approval_policy.delete",
            "verifier_policy.enabled",
            "verifier_policy.verifier_model",
            "verifier_policy.trigger_threshold",
            "system_instruction_policy.variant",
        }
        if self.path not in allowed:
            raise ValueError(f"unsupported harness mutation path: {self.path}")
        return self


class HarnessMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: str
    reasoning_summary: str = Field(min_length=1, max_length=800)
    changes: list[HarnessChange] = Field(min_length=1, max_length=6)
    evidence: list[str] = Field(default_factory=list)
    expected_effect: str = ""
    historical_matches: list[str] = Field(default_factory=list)

    def apply(self, parent: HarnessVersion, *, version_id: str, generation: int) -> HarnessVersion:
        values = parent.model_dump(mode="python")
        for change in self.changes:
            cursor: dict[str, Any] = values
            parts = change.path.split(".")
            for part in parts[:-1]:
                cursor = cursor[part]
            cursor[parts[-1]] = change.value
        values.update(
            {
                "id": version_id,
                "generation": generation,
                "parent_id": self.parent_id,
                "parent_ids": [self.parent_id],
                "mutation_reason": self.reasoning_summary,
                "mutation_set": [change.model_dump(mode="python") for change in self.changes],
                "mutation_evidence": list(self.evidence),
                "expected_effect": self.expected_effect,
                "historical_matches": list(self.historical_matches),
                "status": "CANDIDATE",
                "created_at": datetime.now(UTC),
            }
        )
        values.pop("runtime_graph", None)
        return HarnessVersion.model_validate(values)


class HarnessDiffChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    before: Any
    after: Any
    kind: Literal["added", "removed", "changed"]


class HarnessDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_version: str
    to_version: str
    changes: list[HarnessDiffChange] = Field(default_factory=list)
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RuntimeTraceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    status: TraceStatus
    details: dict[str, Any] = Field(default_factory=dict)


class HarnessMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fitness: float = Field(default=0.0, ge=0, le=1)
    block_rate: float = Field(default=0.0, ge=0, le=1)
    utility_rate: float = Field(default=0.0, ge=0, le=1)
    attack_coverage: float = Field(default=0.0, ge=0, le=1)
    battles: int = Field(default=0, ge=0)
    candidate_status: HarnessStatus = "CANDIDATE"


class HarnessDeployment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version_id: str
    status: HarnessDeploymentStatus
    compiled_at: datetime | None = None
    activated_at: datetime | None = None
    promoted_at: datetime | None = None
    reason: str = ""


class HarnessRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: HarnessVersion
    deployment: HarnessDeployment
    metrics: HarnessMetrics = Field(default_factory=HarnessMetrics)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def lifecycle(self) -> HarnessDeploymentStatus:
        """The single authoritative answer to "where is this harness in its life?"."""

        return self.deployment.status

    def set_status(self, status: HarnessDeploymentStatus, *, reason: str | None = None) -> None:
        """Move the record to a lifecycle position, in all three renderings at once.

        Writing `version.status`, `deployment.status` or `metrics.candidate_status`
        directly is what let a rejected candidate keep claiming to be EVALUATING, so
        the lifecycle is only writable through here.
        """

        rendered = LIFECYCLE_RENDERING[status]
        self.deployment.status = status
        if reason is not None:
            self.deployment.reason = reason
        self.version.status = rendered
        self.metrics.candidate_status = rendered

    @model_validator(mode="after")
    def reconcile_status(self) -> HarnessRecord:
        """Re-derive the two projections from the authority, on build and on load."""

        rendered = LIFECYCLE_RENDERING[self.deployment.status]
        if self.version.status != rendered:
            self.version.status = rendered
        if self.metrics.candidate_status != rendered:
            self.metrics.candidate_status = rendered
        return self


class FailureAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str
    harness_id: str
    root_stage: str
    weakness: str
    observed_effect: str
    candidate_changes: list[str] = Field(default_factory=list)
    historical_match_ids: list[str] = Field(default_factory=list)
    historical_similarity: float = Field(default=0.0, ge=0, le=1)
    historical_adaptations: list[str] = Field(default_factory=list)
    # How the historical patch turned out (PROMOTED/REJECTED/...): the engineer must
    # know whether a previously tried fix actually survived selection.
    historical_patch_outcome: str = ""
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
