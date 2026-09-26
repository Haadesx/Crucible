"""REAL means real model calls; persistence is DEV unless PERSISTENCE=atlas (§27, §35)."""

import pytest

from app.coevolution.providers import ProviderError
from app.coevolution.runtime import build_stack
from app.config import Settings
from app.memory.vector import OpenAIEmbedding

REAL_ENV = {
    "run_mode": "REAL",
    "test_mode": False,
    "dev_state_path": "",
    "mongodb_uri": "",
    "red_provider": "openai_compatible",
    "red_base_url": "http://ai-rig.tail6d5242.ts.net:11500/v1",
    "red_model": "qwen3.8-flash-next-heretic2",
    "red_api_key": "k",
    "blue_provider": "openrouter",
    "blue_base_url": "https://openrouter.ai/api/v1",
    "blue_api_key": "k",
    "blue_model": "inclusionai/ling-3.0-flash-fin:free",
    # Explicit so the developer's real .env cannot change what these tests exercise.
    "openai_api_key": "",
    "openrouter_api_key": "k",
}


async def test_real_with_dev_persistence_builds_without_mongo():
    settings = Settings(**REAL_ENV)
    stack = await build_stack(settings)
    try:
        assert stack.repository.backend == "memory"
        assert stack.red_provider is not None and stack.blue_provider is not None
        assert stack.vector_memory.observed_retrieval_backend == "local"
    finally:
        await stack.close()


async def test_real_with_atlas_persistence_requires_mongo():
    settings = Settings(**{**REAL_ENV, "persistence": "atlas"})
    with pytest.raises(ProviderError) as exc:
        await build_stack(settings)
    assert exc.value.code == "PERSISTENCE_UNAVAILABLE"


class _ConnectedMongo:
    """A live-looking MongoRepository whose connection succeeds but does nothing else."""

    backend = "mongodb"

    def __init__(self, uri: str, database: str, embedding_dimensions: int = 1536) -> None:
        self.uri = uri

    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def ensure_indexes(self) -> None: ...

    async def ping(self) -> bool:
        return True


class _UnreachableMongo(_ConnectedMongo):
    async def start(self) -> None:
        raise RuntimeError("connection refused")


async def test_real_with_atlas_persistence_refuses_to_run_without_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connected Atlas deployment is still not enough: REAL + PERSISTENCE=atlas must
    fail closed when no embedding provider key is configured, rather than quietly
    substituting hash embeddings or the DEV snapshot."""

    monkeypatch.setattr("app.coevolution.runtime.MongoRepository", _ConnectedMongo)
    settings = Settings(
        **{
            **REAL_ENV,
            "persistence": "atlas",
            "mongodb_uri": "mongodb://atlas.invalid:27017",
            "openai_api_key": "",
            "openrouter_api_key": "",
        }
    )
    with pytest.raises(ProviderError) as exc:
        await build_stack(settings)
    assert exc.value.code == "EMBEDDING_PROVIDER_UNAVAILABLE"


async def test_real_with_atlas_persistence_never_falls_back_when_mongo_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreachable Atlas URI must surface PERSISTENCE_UNAVAILABLE, not an in-memory
    or snapshot-backed repository labelled as the run's persistence."""

    monkeypatch.setattr("app.coevolution.runtime.MongoRepository", _UnreachableMongo)
    settings = Settings(**{**REAL_ENV, "persistence": "atlas", "mongodb_uri": "mongodb://atlas.invalid:27017"})
    with pytest.raises(ProviderError) as exc:
        await build_stack(settings)
    assert exc.value.code == "PERSISTENCE_UNAVAILABLE"


async def test_the_openrouter_key_serves_embeddings_when_no_openai_key_exists() -> None:
    """OpenRouter's /embeddings endpoint is a real embedding provider, so the Blue key
    doubles as the embedding key instead of forcing hash embeddings."""

    settings = Settings(**{**REAL_ENV, "run_mode": "DEV", "openrouter_api_key": "k"})
    stack = await build_stack(settings)
    try:
        embeddings = stack.vector_memory.embeddings
        assert isinstance(embeddings, OpenAIEmbedding)
        assert embeddings.model == "openai/text-embedding-3-small"
        assert "openrouter.ai" in str(embeddings.client.base_url)
    finally:
        await stack.close()


async def test_real_with_atlas_accepts_openrouter_as_the_embedding_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a live Mongo connection and only the OpenRouter key, the embedding guard
    passes instead of raising EMBEDDING_PROVIDER_UNAVAILABLE."""

    monkeypatch.setattr("app.coevolution.runtime.MongoRepository", _ConnectedMongo)
    settings = Settings(
        **{
            **REAL_ENV,
            "persistence": "atlas",
            "mongodb_uri": "mongodb://atlas.invalid:27017",
            "openrouter_api_key": "k",
        }
    )
    stack = await build_stack(settings)
    try:
        assert stack.repository.backend == "mongodb"
        assert isinstance(stack.vector_memory.embeddings, OpenAIEmbedding)
    finally:
        await stack.close()
