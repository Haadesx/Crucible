from app.models.tool import ProposedToolCall, UserGoal


class SecondaryVerifier:
    """Verify a side-effect proposal without asking another language model."""

    def verify(self, call: ProposedToolCall, goal: UserGoal) -> tuple[bool, str | None]:
        if call.instruction_source != "user":
            return False, "EXTERNAL_SOURCE_NOT_AUTHORIZED"
        if call.name not in goal.permitted_tools:
            return False, "TOOL_NOT_IN_USER_GOAL"
        if call.name == "send_email" and call.arguments.get("to") not in goal.permitted_recipients:
            return False, "RECIPIENT_NOT_IN_USER_GOAL"
        if call.name == "transfer_money":
            amount = call.arguments.get("amount")
            if (
                goal.max_transfer_amount is None
                or not isinstance(amount, (int, float))
                or float(amount) > goal.max_transfer_amount
            ):
                return False, "AMOUNT_MISMATCH"
        if call.name == "delete_document" and call.arguments.get("document_id") not in (
            goal.permitted_document_ids
        ):
            return False, "RESOURCE_NOT_AUTHORIZED"
        return True, None
