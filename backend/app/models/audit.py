"""Model-call auditability (§32) and experiment run reports (§48)."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.red import RedTeamMode

ModelRole = Literal["red_attacker", "red_mutator", "blue_executor", "blue_harness_engineer"]


def new_model_call_id() -> str:
    """Ledger identity for one inference call.

    Ids are globally unique (not per provider, not per run counter) so a Red call and
    a Blue call can never share a primary key. The persistence layer still enforces
    uniqueness; this only keeps ids attachable to artifacts before they are stored.
    """
    return f"CALL-{uuid4().hex[:20]}"


class ModelCall(BaseModel):
    """One persisted inference call. Proves a model produced a given artifact.

    ``id`` is assigned by the persistence layer on save (a blank id is minted then);
    artifacts reference the call that produced them via their own ``model_call_id``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    run_id: str
    generation: int = Field(ge=0)
    provider: str
    base_url: str | None = None
    model: str
    role: ModelRole
    agent_version_id: str = ""
    artifact_id: str = ""
    artifact_type: str = ""
    input_hash: str
    prompt_chars: int = Field(ge=0)
    output_text: str = ""
    latency_ms: int = Field(ge=0)
    usage: dict[str, Any] = Field(default_factory=dict)
    retrieval_query: str = ""
    retrieved_ids: list[str] = Field(default_factory=list)
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChampionComparison(BaseModel):
    """One Red candidate replayed against one Blue harness on the shared battery (§20, §42).

    ``champion_kind="historical"`` marks a previously promoted Blue champion drawn from
    this run's own hall of fame, as opposed to the harness currently under promotion.
    ``hof_fitness`` is the champion's fitness as recorded when it was promoted; it is
    never overwritten by these replays so promotion-time numbers stay intact (§26).
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    generation: int = Field(ge=0)
    champion_id: str
    champion_kind: Literal["current", "historical"]
    champion_generation: int = Field(ge=0)
    broken: bool
    hof_fitness: float = Field(ge=0, le=1)


class AntiOverfittingSignal(BaseModel):
    """Whether one Red candidate generalises past the defense it was tuned against.

    A candidate that breaks only the current champion is overfit to that exact defense
    (§42). ``generalizes`` is evidence-backed only when ``sampled_champion_ids`` is
    non-empty: with no historical champion available yet the engine records no
    generalisation claim at all rather than an unproven one.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    generation: int = Field(ge=0)
    current_champion_id: str
    beat_current_champion: bool
    sampled_champion_ids: list[str] = Field(default_factory=list)
    broken_champion_ids: list[str] = Field(default_factory=list)
    survived_champion_ids: list[str] = Field(default_factory=list)
    generalizes: bool


class RunReport(BaseModel):
    """Summary artifact for a completed experiment (§48)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    red_model: str
    blue_model: str
    red_provider: str
    blue_provider: str
    generations: int = Field(ge=0)
    red_versions_created: int = Field(ge=0)
    blue_versions_created: int = Field(ge=0)
    attacks_generated: int = Field(ge=0)
    attacks_successful: int = Field(ge=0)
    harness_patches_generated: int = Field(ge=0)
    candidates_compiled: int = Field(ge=0)
    candidates_promoted: int = Field(ge=0)
    asr_by_generation: list[float] = Field(default_factory=list)
    utility_by_generation: list[float] = Field(default_factory=list)
    red_hall_of_fame: list[str] = Field(default_factory=list)
    blue_hall_of_fame: list[str] = Field(default_factory=list)
    final_red_champion: str = ""
    final_blue_champion: str = ""
    total_model_calls: int = Field(ge=0)
    # §20/§42: candidates are measured against the current champion *and* sampled
    # historical champions, so a strategy that only breaks today's defense is visible.
    # §23: a run whose Red could see the harness is not comparable to one where it
    # could not, so the mode travels with the result.
    red_team_mode: RedTeamMode = "BLACK_BOX"
    run_seed: int = 0
    historical_champions_sampled: list[str] = Field(default_factory=list)
    champion_comparisons: list[ChampionComparison] = Field(default_factory=list)
    anti_overfitting: list[AntiOverfittingSignal] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HallOfFameEntry(BaseModel):
    """Historically strong Red attacks or Blue harnesses (§19, §20)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["red", "blue"]
    ref_id: str
    run_id: str = ""
    generation: int = Field(ge=0)
    label: str = ""
    fitness: float = Field(ge=0, le=1)
    detail: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
