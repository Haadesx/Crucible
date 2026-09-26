from typing import cast

from fastapi import Depends, HTTPException, Request

from app.dependencies import AppContainer
from app.memory.repository import READ_ONLY_DETAIL


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def require_writable(container: AppContainer = Depends(get_container)) -> AppContainer:
    """Refuse mutating routes while serving a read-only evidence snapshot.

    The repository owns the capability; this turns a refused write into an explicit
    HTTP response instead of a generic 500 from the storage layer.
    """

    if getattr(container.repository, "read_only", False):
        raise HTTPException(status_code=409, detail=f"READ_ONLY_SNAPSHOT: {READ_ONLY_DETAIL}")
    return container
