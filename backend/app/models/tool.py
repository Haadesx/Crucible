from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ToolName = Literal["send_email", "transfer_money", "delete_document"]
InstructionSource = Literal["user", "document", "email", "tool_output", "model"]


class UserGoal(BaseModel):
    """Provenance-preserving representation of the user's authorized intent."""

    model_config = ConfigDict(extra="forbid")

    requested_action: str
    permitted_tools: list[str]
    permitted_recipients: list[str] = Field(default_factory=list)
    permitted_destinations: list[str] = Field(default_factory=list)
    permitted_document_ids: list[str] = Field(default_factory=list)
    max_transfer_amount: float | None = Field(default=None, ge=0)


class ProposedToolCall(BaseModel):
    """A model proposal that has not crossed the policy boundary yet."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    name: ToolName
    arguments: dict[str, Any]
    instruction_source: InstructionSource = "model"


class GatewayDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["allow", "deny", "require_approval"]
    risk_score: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ExecutedToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    name: ToolName
    arguments: dict[str, Any]
    instruction_source: InstructionSource
    result: ToolResult
