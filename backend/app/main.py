import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.arena import router as arena_router
from app.api.generations import router as generations_router
from app.api.replay import router as replay_router
from app.api.websocket import router as websocket_router
from app.config import get_settings
from app.dependencies import build_container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app.state.container = await build_container(settings)
    try:
        yield
    finally:
        await app.state.container.close()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="DarwinGuard API",
        version="0.1.0",
        description="Red/Blue co-evolution arena for sandboxed agent security",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(arena_router)
    application.include_router(generations_router)
    application.include_router(replay_router)
    application.include_router(websocket_router)

    @application.get("/health")
    async def health() -> dict[str, object]:
        container = application.state.container
        return {
            "status": "ok",
            "service": "darwinguard",
            "version": "0.1.0",
            "memory_backend": container.repository.backend,
            "agent_provider": settings.agent_provider,
            "vector_search_enabled": container.vector_memory.retrieval_backend == "atlas",
            "vector_search_backend": container.vector_memory.retrieval_backend,
        }

    return application


app = create_app()
