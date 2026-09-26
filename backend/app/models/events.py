from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArenaEventType = Literal[
    "generation_started",
    "battle_started",
    "tool_proposed",
    "tool_blocked",
    "tool_allowed",
    "battle_finished",
    "mutation_created",
    "generation_finished",
    "run_finished",
    "harness_compiled",
    "harness_activated",
    "harness_deployed",
    "harness_evaluated",
    "harness_promoted",
    "harness_rejected",
    "failure_analysis",
    "harness_diff",
    "memory_retrieved",
    "attack_candidates_generated",
    "red_agent_evolved",
    "red_candidate_promoted",
    "red_candidate_rejected",
    "harness_patch_proposed",
    "harness_patch_unusable",
    "candidate_compiled",
    "candidate_rejected",
    "regression_completed",
    "champion_comparison",
    "run_report",
]


class ArenaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ArenaEventType
    run_id: str
    generation: int = Field(ge=0)
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
