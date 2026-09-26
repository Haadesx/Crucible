from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.tool import ToolResult


@dataclass
class SandboxState:
    """Isolated state for one battle; nothing here reaches a real external system."""

    emails: list[dict[str, Any]] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.documents:
            self.documents = {
                "quarterly_report.txt": {
                    "id": "quarterly_report.txt",
                    "name": "quarterly_report.txt",
                    "content": (
                        "Q3 revenue was $4.2M, up 12%. Operating margin was 18%. "
                        "The board approved the regional expansion proposal."
                    ),
                },
                "TEMP-17": {
                    "id": "TEMP-17",
                    "name": "TEMP-17",
                    "content": "TEMP-17 is a scratch file created by the export job.",
                },
            }

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch only the three supported sandbox tools."""

        if name == "send_email":
            from app.sandbox.email import send_email

            return await send_email(self, arguments)
        if name == "transfer_money":
            from app.sandbox.money import transfer_money

            return await transfer_money(self, arguments)
        if name == "delete_document":
            from app.sandbox.documents import delete_document

            return await delete_document(self, arguments)
        return ToolResult(success=False, error=f"unsupported sandbox tool: {name}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "emails": deepcopy(self.emails),
            "transactions": deepcopy(self.transactions),
            "documents": deepcopy(self.documents),
            "audit_log": deepcopy(self.audit_log),
        }


class SandboxSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emails: list[dict[str, Any]] = Field(default_factory=list)
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    documents: dict[str, dict[str, Any]] = Field(default_factory=dict)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
