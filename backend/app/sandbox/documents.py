from typing import Any

from app.models.tool import ToolResult
from app.sandbox.state import SandboxState


async def delete_document(state: SandboxState, arguments: dict[str, Any]) -> ToolResult:
    """Delete a document only from the per-episode in-memory sandbox."""

    document_id = arguments.get("document_id")
    if not isinstance(document_id, str) or not document_id:
        return ToolResult(success=False, error="invalid document_id")
    if document_id not in state.documents:
        return ToolResult(success=False, error="document not found")

    deleted = state.documents.pop(document_id)
    state.audit_log.append({"tool": "delete_document", "arguments": {"document_id": document_id}})
    return ToolResult(success=True, output={"deleted_document": deleted["id"]})
