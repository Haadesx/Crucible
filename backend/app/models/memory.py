from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.harness import FailureAnalysis


class FailureMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    episode_id: str
    type: Literal["breach", "utility_failure"]
    summary: str
    attack_id: str
    defense_id: str
    attack_features: dict[str, Any] = Field(default_factory=dict)
    defense_features: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    analysis: FailureAnalysis | None = None
    historical_match_ids: list[str] = Field(default_factory=list)
    similarity: float = Field(default=0.0, ge=0, le=1)
    created_at: datetime
