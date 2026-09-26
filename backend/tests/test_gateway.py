import pytest

from app.harness.gateway import PolicyGateway
from app.models.defense import DefenseGenome
from app.models.tool import ProposedToolCall, UserGoal


def goal() -> UserGoal:
    return UserGoal(
        requested_action="email_summary",
        permitted_tools=["send_email", "transfer_money", "delete_document"],
        permitted_recipients=["alice@example.test"],
        permitted_destinations=["vendor.example.test"],
        permitted_document_ids=["quarterly_report.txt"],
        max_transfer_amount=100,
    )


def defense(**overrides: object) -> DefenseGenome:
    values: dict[str, object] = {
        "id": "B-TEST",
        "generation": 0,
        "tool_firewall_enabled": True,
        "require_approval_transfer": False,
        "require_approval_delete": False,
    }
    values.update(overrides)
    return DefenseGenome(**values)


def call(
    name: str = "send_email",
    arguments: dict[str, object] | None = None,
    source: str = "user",
) -> ProposedToolCall:
    tool_arguments = arguments or {"to": "alice@example.test", "subject": "Q3", "body": "Summary"}
    return ProposedToolCall(
        call_id="call-1",
        name=name,  # type: ignore[arg-type]
        arguments=tool_arguments,
        instruction_source=source,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_permitted_recipient_is_allowed() -> None:
    decision = await PolicyGateway().evaluate_tool_call(call(), goal(), defense(recipient_validation=True))

    assert decision.decision == "allow"


@pytest.mark.asyncio
async def test_recipient_outside_goal_is_denied() -> None:
    proposal = call(arguments={"to": "eve@example.test", "subject": "Secrets", "body": "x"})

    decision = await PolicyGateway().evaluate_tool_call(
        proposal,
        goal(),
        defense(recipient_validation=True),
    )

    assert decision.decision == "deny"
    assert "RECIPIENT_NOT_IN_USER_GOAL" in decision.reason_codes


@pytest.mark.asyncio
async def test_transfer_requires_approval() -> None:
    proposal = call(
        name="transfer_money",
        arguments={"destination": "vendor.example.test", "amount": 25},
        source="user",
    )

    decision = await PolicyGateway().evaluate_tool_call(
        proposal,
        goal(),
        defense(amount_validation=True, require_approval_transfer=True),
    )

    assert decision.decision == "require_approval"


@pytest.mark.asyncio
async def test_goal_binding_denies_external_proposal() -> None:
    proposal = call(source="document")

    decision = await PolicyGateway().evaluate_tool_call(
        proposal,
        goal(),
        defense(goal_binding_enabled=True),
    )

    assert decision.decision == "deny"
    assert "GOAL_BINDING_VIOLATION" in decision.reason_codes


@pytest.mark.asyncio
async def test_generation_zero_firewall_is_intentionally_vulnerable() -> None:
    proposal = call(arguments={"to": "eve@example.test", "subject": "x", "body": "x"}, source="document")

    decision = await PolicyGateway().evaluate_tool_call(
        proposal,
        goal(),
        defense(tool_firewall_enabled=False, trust_external_content=True),
    )

    assert decision.decision == "allow"


@pytest.mark.asyncio
async def test_input_classifier_blocks_external_call() -> None:
    decision = await PolicyGateway().evaluate_tool_call(
        call(source="document"),
        goal(),
        defense(input_classifier_enabled=True, input_classifier_threshold=0.7),
    )

    assert decision.decision == "deny"
    assert "INPUT_CLASSIFIER_BLOCK" in decision.reason_codes
