from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AttackCarrier = Literal["document", "email", "tool_output", "voice_transcript"]
AttackStrategy = Literal[
    "authority_confusion",
    "goal_hijack",
    "instruction_hierarchy",
    "context_poisoning",
    "tool_output_injection",
    "multi_turn_indirection",
]
AttackPlacement = Literal["beginning", "middle", "end"]


class AttackGenome(BaseModel):
    """A strategy-level adversarial genome, independent of rendered payload."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    generation: int = Field(ge=0)
    parent_ids: list[str] = Field(default_factory=list)
    carrier: AttackCarrier
    strategy: AttackStrategy
    target_tool: Literal["send_email", "transfer_money", "delete_document"]
    placement: AttackPlacement
    indirection_level: int = Field(ge=0, le=4)
    obfuscation_level: int = Field(ge=0, le=3)
    social_authority: int = Field(ge=0, le=3)
    persistence: bool = False
    mutation_reason: str = ""
    payload: str | None = None

    @model_validator(mode="after")
    def validate_lineage(self) -> "AttackGenome":
        if self.generation == 0 and self.parent_ids:
            raise ValueError("generation 0 attacks cannot have parents")
        if self.generation > 0 and not self.parent_ids:
            raise ValueError("evolved attacks must identify at least one parent")
        return self


class AttackStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fitness: float = Field(default=0.0, ge=0, le=1)
    success_rate: float = Field(default=0.0, ge=0, le=1)
    novelty: float = Field(default=1.0, ge=0, le=1)
    battles: int = Field(default=0, ge=0)


class AttackRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genome: AttackGenome
    stats: AttackStats
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime
