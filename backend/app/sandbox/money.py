import math
from typing import Any
from uuid import uuid4

from app.models.tool import ToolResult
from app.sandbox.state import SandboxState


async def transfer_money(state: SandboxState, arguments: dict[str, Any]) -> ToolResult:
    """Record a fake transfer; this function cannot initiate a real payment."""

    destination = arguments.get("destination")
    amount = arguments.get("amount")
    if not isinstance(destination, str) or not destination.strip() or len(destination) > 200:
        return ToolResult(success=False, error="invalid destination")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return ToolResult(success=False, error="invalid amount")
    numeric_amount = float(amount)
    if not math.isfinite(numeric_amount) or numeric_amount <= 0 or numeric_amount > 1_000_000_000:
        return ToolResult(success=False, error="amount out of range")

    transaction = {
        "id": f"txn-{uuid4().hex[:12]}",
        "destination": destination,
        "amount": numeric_amount,
        "status": "settled_in_sandbox",
    }
    state.transactions.append(transaction)
    state.audit_log.append({"tool": "transfer_money", "arguments": dict(arguments)})
    return ToolResult(
        success=True,
        output={"transaction_id": transaction["id"], "amount": numeric_amount},
    )
