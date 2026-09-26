from app.models.defense import DefenseGenome
from app.models.tool import InstructionSource, UserGoal


def is_trusted_source(source: InstructionSource) -> bool:
    return source == "user"


def source_matches_goal(
    source: InstructionSource,
    goal: UserGoal,
    defense: DefenseGenome,
) -> bool:
    """Return whether a proposal is allowed to act under the current goal binding."""

    if source == "user":
        return True
    return not defense.goal_binding_enabled


def policy_trusts_external(defense: DefenseGenome) -> bool:
    return defense.trust_external_content or defense.trust_tool_outputs
