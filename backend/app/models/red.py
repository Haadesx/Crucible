"""Red-side models: the attacking agent has versions, not just attack strings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.attack import AttackStrategy

if TYPE_CHECKING:
    from app.models.attack import AttackGenome

RedAttackFamily = AttackStrategy


class RedAgentVersion(BaseModel):
    """One evolving attacker strategy. The model weights stay fixed; this changes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    run_id: str = ""
    generation: int = Field(ge=0)
    parent_ids: list[str] = Field(default_factory=list)

    base_model: str
    system_strategy: str = Field(min_length=1, max_length=2_000)
    tactic_prior: dict[str, float] = Field(default_factory=dict)
    carrier_prior: dict[str, float] = Field(default_factory=dict)
    mutation_policy: str = "explore_successful_families_and_retire_failed_ones"
    memory_query_policy: str = "retrieve_similar_attacks_and_their_outcomes"
    exploration_level: float = Field(default=0.4, ge=0, le=1)

    created_from_failure_ids: list[str] = Field(default_factory=list)
    fitness: float | None = Field(default=None, ge=0, le=1)
    model_call_id: str = ""
    status: str = "ACTIVE"
    # Why a mutation exists and how it was judged (§19): the model's own note, the
    # deterministic decision sentence, and the evaluation episodes the decision rests on.
    mutation_note: str = Field(default="", max_length=400)
    decision_reason: str = Field(default="", max_length=800)
    evaluation_episode_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_lineage(self) -> RedAgentVersion:
        if self.generation == 0 and self.parent_ids:
            raise ValueError("generation 0 red agents cannot have parents")
        if self.generation > 0 and not self.parent_ids:
            raise ValueError("evolved red agents must identify at least one parent")
        return self


class RedFeedback(BaseModel):
    """Black-box post-episode information returned to Red (§22). No evaluator internals."""

    model_config = ConfigDict(extra="forbid")

    attacker_goal_success: bool
    user_task_success: bool
    last_successful_stage: str | None = None
    blocked_at: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    visible_tool_behavior: dict[str, str] = Field(default_factory=dict)


RedTeamMode = Literal["BLACK_BOX", "GRAY_BOX"]

# §23: "Default hackathon demo: BLACK_BOX." Unset means Red is told nothing about the
# harness it is attacking; GRAY_BOX is opt-in and has to be asked for.
DEFAULT_RED_TEAM_MODE: RedTeamMode = "BLACK_BOX"


class AttackCandidate(BaseModel):
    """A concrete adversarial payload produced by one Red agent version (§4)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    run_id: str = ""
    red_agent_version_id: str
    scenario_id: str
    parent_attack_ids: list[str] = Field(default_factory=list)

    attack_family: str
    carrier: str
    target_capability: str
    attack_plan: str = ""
    payload: str = Field(min_length=1)

    generated_by_model: str
    generation: int = Field(ge=0)
    model_call_id: str = ""
    novelty_score: float | None = Field(default=None, ge=0, le=1)
    fitness: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_genome(self, *, genome_id: str) -> AttackGenome:
        """Bridge into the existing arena runner contract."""
        from app.models.attack import AttackGenome, AttackPlacement

        carrier = self.carrier if self.carrier in {"document", "email", "tool_output"} else "document"
        family = self.attack_family if self.attack_family in AttackStrategy.__args__ else "tool_output_injection"  # type: ignore[attr-defined]
        placement: AttackPlacement = "middle"
        parents = list(self.parent_attack_ids)[:2]
        return AttackGenome(
            id=genome_id,
            # A candidate with no surviving ancestor is a root seed, not an evolution, so
            # it sits at lineage generation 0. A candidate that names parents is an
            # evolution, so its lineage generation is at least 1 — even when the Red agent
            # itself is on generation 0 and drew those parents from historical memory
            # rather than from this run. Without the floor, a generation-0 candidate with
            # retrieved ancestors would be rejected as "generation 0 with parents".
            generation=max(self.generation, 1) if parents else 0,
            parent_ids=parents,
            carrier=carrier,
            strategy=family,
            target_tool="send_email",
            placement=placement,
            indirection_level=1,
            obfuscation_level=0,
            social_authority=1,
            mutation_reason=self.attack_plan[:200],
            payload=self.payload,
        )


class RetrievedAttackNeighbor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attack_id: str
    similarity: float = Field(ge=0, le=1)
    succeeded: bool
    summary: str = ""
