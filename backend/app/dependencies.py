import logging
from dataclasses import dataclass

from app.agent.provider import FakeAgent, OpenAIAgent, TargetAgent
from app.arena.runner import ArenaRunner
from app.coevolution.providers import OpenAICompatibleProvider, ProviderConfig, ProviderError
from app.config import Settings
from app.events import ArenaEventBus
from app.evolution.loop import EvolutionLoop
from app.harness.gateway import PolicyGateway
from app.memory.change_stream import MongoChangeStreamBridge
from app.memory.mongodb import MongoRepository
from app.memory.repository import InMemoryRepository, MemoryRepository
from app.memory.vector import HashEmbedding, OpenAIEmbedding, VectorMemory
from app.scenarios.loader import ScenarioCatalog

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    settings: Settings
    repository: MemoryRepository
    event_bus: ArenaEventBus
    vector_memory: VectorMemory
    catalog: ScenarioCatalog
    agent: TargetAgent
    runner: ArenaRunner
    evolution: EvolutionLoop
    change_stream: MongoChangeStreamBridge | None = None
    red_provider: OpenAICompatibleProvider | None = None
    blue_provider: OpenAICompatibleProvider | None = None

    async def close(self) -> None:
        if self.change_stream is not None:
            await self.change_stream.stop()
        await self.repository.close()


async def build_container(settings: Settings) -> AppContainer:
    repository: MemoryRepository
    change_stream: MongoChangeStreamBridge | None = None
    # The API process must read the same DEV snapshot the CLI runtime writes, or the
    # observer UI can never show the run the engine actually persisted. TEST runs stay
    # ephemeral by design, and a REAL run falls back to the snapshot only when its
    # MongoDB connection fails and DEV persistence is the configured fallback.
    snapshot_path = (
        settings.dev_state_path or None if settings.effective_run_mode != "TEST" else None
    )
    # A snapshot served to an observer is evidence: it opens read-only unless the
    # operator explicitly opts a dedicated live snapshot into writes. The capability is
    # carried by the repository, not inferred from the file name.
    snapshot_read_only = bool(snapshot_path) and not settings.allow_snapshot_writes
    if settings.has_mongodb:
        mongo: MongoRepository | None = None
        try:
            mongo = MongoRepository(
                settings.mongodb_uri,
                settings.mongodb_database,
                settings.embedding_dimensions,
            )
            await mongo.start()
            await mongo.ensure_indexes()
            repository = mongo
            if settings.use_change_streams:
                change_stream = MongoChangeStreamBridge(
                    mongo.client,
                    settings.mongodb_database,
                    # The bridge is wired after the bus is created below.
                    publish=lambda event: _publish_placeholder(event),
                )
        except Exception as exc:
            if settings.effective_run_mode == "REAL":
                if mongo is not None:
                    await mongo.close()
                raise ProviderError("PERSISTENCE_UNAVAILABLE", f"MongoDB connection failed: {exc}") from exc
            logger.warning("MongoDB unavailable; using in-memory lineage: %s", exc)
            if mongo is not None:
                await mongo.close()
            repository = InMemoryRepository(snapshot_path=snapshot_path, read_only=snapshot_read_only)
    else:
        if settings.effective_run_mode == "REAL":
            raise ProviderError("PERSISTENCE_UNAVAILABLE", "REAL runs require MONGODB_URI")
        repository = InMemoryRepository(snapshot_path=snapshot_path, read_only=snapshot_read_only)
    await repository.start()
    await repository.ensure_indexes()

    event_bus = ArenaEventBus()
    if isinstance(repository, MongoRepository) and change_stream is not None:
        change_stream.publish = event_bus.publish
        change_stream.start()
    embeddings = (
        OpenAIEmbedding(
            settings.embedding_model,
            settings.openai_api_key.get_secret_value(),
            settings.embedding_dimensions,
        )
        if settings.has_openai
        else HashEmbedding(settings.embedding_dimensions)
    )
    vector_memory = VectorMemory(
        repository,
        embeddings,
        use_atlas_vector_search=settings.use_vector_search,
    )
    agent: TargetAgent
    if settings.agent_provider == "openai" and settings.has_openai:
        agent = OpenAIAgent(settings.openai_model, settings.openai_api_key.get_secret_value())
    elif settings.effective_run_mode != "REAL":
        # DEV/TEST processes may be observation-only (serving a persisted DEV snapshot),
        # so they are allowed to boot without a target model. A REAL run still fails
        # closed below rather than silently falling back to the deterministic stand-in.
        agent = FakeAgent()
    else:
        raise ProviderError(
            "BLUE_PROVIDER_UNAVAILABLE",
            "No Blue model configured. Set BLUE_PROVIDER/BLUE_BASE_URL/BLUE_MODEL (or OPENAI_API_KEY with "
            "AGENT_PROVIDER=openai), or start with TEST_MODE=true for a labelled mock run.",
        )
    red_provider = None if settings.effective_run_mode == "TEST" else OpenAICompatibleProvider(ProviderConfig.red(settings))
    blue_provider = None if settings.effective_run_mode == "TEST" else OpenAICompatibleProvider(ProviderConfig.blue(settings))
    catalog = ScenarioCatalog()
    runner = ArenaRunner(agent=agent, gateway=PolicyGateway())
    evolution = EvolutionLoop(
        repository,
        runner,
        event_bus,
        vector_memory,
        catalog,
        max_parallel_episodes=settings.max_parallel_episodes,
    )
    return AppContainer(
        settings=settings,
        repository=repository,
        event_bus=event_bus,
        vector_memory=vector_memory,
        catalog=catalog,
        agent=agent,
        runner=runner,
        evolution=evolution,
        change_stream=change_stream,
        red_provider=red_provider,
        blue_provider=blue_provider,
    )


async def _publish_placeholder(event: object) -> None:
    """Replaced with the real bus publisher during container construction."""

    del event
