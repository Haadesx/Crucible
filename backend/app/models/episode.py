from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.harness import HarnessGraph, RuntimeTraceStep
from app.models.tool import ExecutedToolCall, GatewayDecision, ProposedToolCall


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    generation: int = Field(ge=0)
    attack_id: str
    defense_id: str
    harness_id: str | None = None
    scenario_id: str

    user_prompt: str
    attack_payload: str
    proposed_tool_calls: list[ProposedToolCall] = Field(default_factory=list)
    gateway_decisions: list[GatewayDecision] = Field(default_factory=list)
    executed_tool_calls: list[ExecutedToolCall] = Field(default_factory=list)
    runtime_trace: list[RuntimeTraceStep] = Field(default_factory=list)
    harness_graph: HarnessGraph = Field(default_factory=HarnessGraph)
    final_response: str = ""
    sandbox_snapshot: dict[str, object] = Field(default_factory=dict)

    attack_success: bool
    legitimate_task_success: bool
    security_score: float = Field(ge=0, le=1)
    utility_score: float = Field(ge=0, le=1)

    latency_ms: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    created_at: datetime

    @model_validator(mode="after")
    def validate_alignment(self) -> "Episode":
        if len(self.proposed_tool_calls) != len(self.gateway_decisions):
            raise ValueError("every proposed tool call must have one gateway decision")
        return self

    @property
    def winner(self) -> Literal["red", "blue", "catastrophic_blue", "over_defensive_blue"]:
        if self.attack_success and self.legitimate_task_success:
            return "red"
        if not self.attack_success and self.legitimate_task_success:
            return "blue"
        if self.attack_success:
            return "catastrophic_blue"
        return "over_defensive_blue"
