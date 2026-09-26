from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.dependencies import AppContainer

router = APIRouter()


@router.websocket("/ws/arena")
async def arena_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    container: AppContainer = websocket.app.state.container
    try:
        for event in await container.event_bus.history():
            await websocket.send_json(event.model_dump(mode="json"))
        async for event in container.event_bus.subscribe():
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
