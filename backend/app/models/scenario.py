from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.tool import UserGoal


class RequiredAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call", "response_contains"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None


class ForbiddenAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str
    user_prompt: str
    trusted_goal: UserGoal
    content_source: Literal["document", "email", "tool_output"]
    base_content: str
    required_actions: list[RequiredAction] = Field(min_length=1)
    forbidden_actions: list[ForbiddenAction] = Field(min_length=1)
