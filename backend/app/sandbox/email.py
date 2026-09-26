import re
from typing import Any
from uuid import uuid4

from app.models.tool import ToolResult
from app.sandbox.state import SandboxState

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def send_email(state: SandboxState, arguments: dict[str, Any]) -> ToolResult:
    """Store a fake email after validating its arguments."""

    to = arguments.get("to")
    subject = arguments.get("subject")
    body = arguments.get("body")
    if not isinstance(to, str) or not _EMAIL_PATTERN.fullmatch(to):
        return ToolResult(success=False, error="invalid recipient")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
        return ToolResult(success=False, error="invalid subject")
    if not isinstance(body, str) or not body.strip() or len(body) > 20_000:
        return ToolResult(success=False, error="invalid body")

    email = {
        "id": f"email-{uuid4().hex[:12]}",
        "to": to,
        "subject": subject,
        "body": body,
        "status": "delivered_to_sandbox",
    }
    state.emails.append(email)
    state.audit_log.append({"tool": "send_email", "arguments": dict(arguments)})
    return ToolResult(success=True, output={"email_id": email["id"], "to": to})
