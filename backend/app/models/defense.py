from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MutableDefenseField = Literal[
    "goal_binding_enabled",
    "input_classifier_enabled",
    "input_classifier_threshold",
    "tool_risk_threshold",
    "recipient_validation",
    "amount_validation",
    "resource_validation",
    "require_approval_email",
    "require_approval_transfer",
    "require_approval_delete",
    "secondary_verifier_enabled",
    "memory_filter_enabled",
    "system_policy_variant",
]
DefensePolicyVariant = Literal["baseline", "distrust_external", "goal_bound", "layered"]


class DefenseGenome(BaseModel):
    """Architectural policy for the agent harness; no executable code is evolvable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    generation: int = Field(ge=0)
    parent_ids: list[str] = Field(default_factory=list)

    trust_external_content: bool = False
    trust_tool_outputs: bool = False
    goal_binding_enabled: bool = False
    input_classifier_enabled: bool = False
    input_classifier_threshold: float = Field(default=0.70, ge=0, le=1)
    tool_firewall_enabled: bool = True
    tool_risk_threshold: float = Field(default=0.70, ge=0, le=1)

    recipient_validation: bool = False
    amount_validation: bool = False
    resource_validation: bool = False
    require_approval_email: bool = False
    require_approval_transfer: bool = True
    require_approval_delete: bool = True

    secondary_verifier_enabled: bool = False
    memory_filter_enabled: bool = False
    system_policy_variant: DefensePolicyVariant = "baseline"
    mutation_reason: str = ""

    @model_validator(mode="after")
    def validate_lineage(self) -> "DefenseGenome":
        if self.generation == 0 and self.parent_ids:
            raise ValueError("generation 0 defenses cannot have parents")
        if self.generation > 0 and not self.parent_ids:
            raise ValueError("evolved defenses must identify at least one parent")
        return self


class DefenseChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: MutableDefenseField
    value: bool | float | str

    @model_validator(mode="after")
    def validate_typed_value(self) -> "DefenseChange":
        bool_fields = {
            "goal_binding_enabled",
            "input_classifier_enabled",
            "recipient_validation",
            "amount_validation",
            "resource_validation",
            "require_approval_email",
            "require_approval_transfer",
            "require_approval_delete",
            "secondary_verifier_enabled",
            "memory_filter_enabled",
        }
        float_fields = {"input_classifier_threshold", "tool_risk_threshold"}
        if self.field in bool_fields and type(self.value) is not bool:
            raise ValueError(f"{self.field} requires a boolean value")
        if self.field in float_fields and (
            type(self.value) not in (int, float) or not 0 <= float(self.value) <= 1
        ):
            raise ValueError(f"{self.field} requires a value between 0 and 1")
        if self.field == "system_policy_variant":
            allowed = {"baseline", "distrust_external", "goal_bound", "layered"}
            if self.value not in allowed:
                raise ValueError(f"unsupported policy variant: {self.value}")
        return self


class DefenseMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: str = Field(min_length=1)
    reasoning_summary: str = Field(min_length=1, max_length=500)
    changes: list[DefenseChange] = Field(min_length=1, max_length=4)

    def apply(self, parent: DefenseGenome) -> dict[str, Any]:
        updates: dict[str, Any] = {change.field: change.value for change in self.changes}
        return parent.model_copy(update=updates, deep=True).model_dump()


class DefenseStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fitness: float = Field(default=0.0, ge=0, le=1)
    block_rate: float = Field(default=0.0, ge=0, le=1)
    utility_rate: float = Field(default=0.0, ge=0, le=1)
    battles: int = Field(default=0, ge=0)


class DefenseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genome: DefenseGenome
    stats: DefenseStats
    created_at: datetime
