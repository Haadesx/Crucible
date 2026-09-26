from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.attack import AttackGenome
from app.models.defense import DefenseGenome


class GenerationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=0)
    run_id: str
    red_population: list[AttackGenome]
    blue_population: list[DefenseGenome]
    red_champion: str
    # The matchup this generation actually ran (§10): which Red agent version attacked,
    # the best breach-producing attack id, and the measured fitness of every Red version
    # that played. Added after the first REAL run, so old records default to empty.
    red_agent_champion: str = ""
    red_fitness_by_version: dict[str, float] = Field(default_factory=dict)
    blue_champion: str
    active_harness_id: str | None = None
    harness_status: str = "ACTIVE"
    attack_success_rate: float = Field(ge=0, le=1)
    utility_rate: float = Field(ge=0, le=1)
    red_mean_fitness: float = Field(ge=0, le=1)
    blue_mean_fitness: float = Field(ge=0, le=1)
    total_battles: int = Field(ge=0)
    created_at: datetime


class ArenaStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generations: int = Field(default=5, ge=2, le=12)
    red_population: int = Field(default=6, ge=4, le=24)
    blue_population: int = Field(default=6, ge=4, le=24)
    matchups_per_genome: int = Field(default=3, ge=2, le=8)


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attack_id: str
    defense_id: str
    scenario_id: str
    run_id: str = "REPLAY"


class HarnessComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attack_id: str
    scenario_id: str
    harness_a_id: str | None = None
    harness_b_id: str
    run_id: str = "REPLAY"


class RunStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    status: str
    generation: int = Field(default=0, ge=0)
    total_generations: int = Field(default=0, ge=0)
    red_population: int = Field(default=0, ge=0)
    blue_population: int = Field(default=0, ge=0)
    completed_battles: int = Field(default=0, ge=0)
    latest_event: str | None = None
    error: str | None = None
