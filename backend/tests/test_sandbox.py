from app.sandbox.state import SandboxState


async def test_send_email_mutates_sandbox() -> None:
    state = SandboxState()

    result = await state.execute(
        "send_email",
        {"to": "alice@example.test", "subject": "Q3", "body": "Summary"},
    )

    assert result.success
    assert state.emails[0]["to"] == "alice@example.test"
    assert state.audit_log[0]["tool"] == "send_email"


async def test_transfer_money_rejects_nan_and_non_finite_amounts() -> None:
    state = SandboxState()

    result = await state.execute(
        "transfer_money",
        {"destination": "vendor", "amount": float("nan")},
    )

    assert not result.success
    assert state.transactions == []


async def test_delete_document_only_mutates_sandbox() -> None:
    state = SandboxState()

    result = await state.execute("delete_document", {"document_id": "quarterly_report.txt"})

    assert result.success
    assert "quarterly_report.txt" not in state.documents


async def test_sandbox_instances_are_isolated() -> None:
    first = SandboxState()
    second = SandboxState()

    await first.execute("delete_document", {"document_id": "quarterly_report.txt"})

    assert "quarterly_report.txt" in second.documents


async def test_dispatcher_rejects_unknown_tools() -> None:
    state = SandboxState()

    result = await state.execute("read_real_secret", {})

    assert not result.success
    assert result.error == "unsupported sandbox tool: read_real_secret"
