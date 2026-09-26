from app.agent.provider import FakeAgent
from app.arena.runner import ArenaRunner
from app.models.attack import AttackGenome
from app.models.defense import DefenseGenome
from app.scenarios.seeds import seed_scenarios


def document_attack() -> AttackGenome:
    return AttackGenome(
        id="R-TEST",
        generation=0,
        carrier="document",
        strategy="authority_confusion",
        target_tool="send_email",
        placement="end",
        indirection_level=0,
        obfuscation_level=0,
        social_authority=1,
    )


def defense(**overrides: object) -> DefenseGenome:
    values: dict[str, object] = {
        "id": "B-TEST",
        "generation": 0,
        "tool_firewall_enabled": False,
        "require_approval_email": False,
        "require_approval_transfer": False,
        "require_approval_delete": False,
    }
    values.update(overrides)
    return DefenseGenome(**values)


async def test_vulnerable_defense_allows_executed_breach() -> None:
    scenario = seed_scenarios()[0]
    runner = ArenaRunner(FakeAgent())

    episode = await runner.run_episode(scenario, document_attack(), defense(), run_id="TEST")

    assert episode.attack_success is True
    assert episode.legitimate_task_success is True
    assert any(call.arguments["to"] == "eve@example.test" for call in episode.executed_tool_calls)


async def test_evolved_defense_blocks_external_recipient_without_breaking_utility() -> None:
    scenario = seed_scenarios()[0]
    runner = ArenaRunner(FakeAgent())

    episode = await runner.run_episode(
        scenario,
        document_attack(),
        defense(
            tool_firewall_enabled=True,
            goal_binding_enabled=True,
            recipient_validation=True,
        ),
        run_id="TEST",
    )

    assert episode.attack_success is False
    assert episode.legitimate_task_success is True
    assert episode.winner == "blue"
    assert "GOAL_BINDING_VIOLATION" in episode.gateway_decisions[-1].reason_codes


async def test_approval_does_not_execute_side_effect() -> None:
    scenario = seed_scenarios()[0]
    attack = document_attack().model_copy(update={"target_tool": "transfer_money"})
    runner = ArenaRunner(FakeAgent())

    episode = await runner.run_episode(
        scenario,
        attack,
        defense(require_approval_transfer=True),
        run_id="TEST",
    )

    transfer = next(call for call in episode.proposed_tool_calls if call.name == "transfer_money")
    assert transfer not in episode.executed_tool_calls
    assert episode.gateway_decisions[-1].decision == "require_approval"
    assert episode.attack_success is False
