"""Assembly helper: build the persistence, memory, providers, and engine for headless runs."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

from app.coevolution.engine import CoevolutionEngine, ProgressSink
from app.coevolution.providers import BlueEngineerProvider, OpenAICompatibleProvider, ProviderConfig, ProviderError, probe
from app.config import Settings, get_settings
from app.arena.evaluator import DeterministicEvaluator
from app.coevolution.suite import baseline_harness
from app.harness.compiler import HarnessCompiler
from app.memory.mongodb import MongoRepository
from app.memory.repository import InMemoryRepository, MemoryRepository
from app.memory.vector import EmbeddingService, HashEmbedding, OpenAIEmbedding, VectorMemory
from app.scenarios.loader import ScenarioCatalog

logger = logging.getLogger(__name__)


def _assert_ai_rig_origin(base_url: str) -> None:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if host in {"127.0.0.1", "localhost", "::1"}:
        port = parsed.port
        if port is not None:
            listeners = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            for line in listeners.stdout.splitlines():
                if not line.startswith("p") or not line[1:].isdigit():
                    continue
                process = subprocess.run(
                    ["ps", "-p", line[1:], "-o", "command="],
                    capture_output=True, text=True, timeout=5, check=False,
                ).stdout
                if "ssh" in process and "-L" in process and str(port) in process and (
                    "ai-rig" in process or "hermes-linux" in process
                ):
                    return
        raise ProviderError("RED_ORIGIN_UNVERIFIED", "RED_BASE_URL loopback listener is not an SSH forward to ai-rig")
    try:
        status = subprocess.run(
            ["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5, check=True
        )
        peers = json.loads(status.stdout).get("Peer", {}).values()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ProviderError("RED_ORIGIN_UNVERIFIED", f"cannot verify ai-rig Tailnet peer: {exc}") from exc
    for peer in peers:
        if peer.get("HostName") != "ai-rig" or not peer.get("Online"):
            continue
        names = {peer.get("HostName", ""), peer.get("DNSName", "").rstrip("."), *peer.get("TailscaleIPs", [])}
        if host in names:
            return
    raise ProviderError("RED_ORIGIN_UNVERIFIED", "RED_BASE_URL does not name the online ai-rig Tailnet peer")


@dataclass
class CoevolutionStack:
    settings: Settings
    repository: MemoryRepository
    vector_memory: VectorMemory
    catalog: ScenarioCatalog
    engine: CoevolutionEngine
    red_provider: OpenAICompatibleProvider | None
    blue_provider: OpenAICompatibleProvider | None

    @property
    def is_mock(self) -> bool:
        return self.settings.effective_run_mode == "TEST" or (self.red_provider is None and self.blue_provider is None)

    def describe(self) -> dict[str, str]:
        persistence = (
            "connected" if self.repository.backend == "mongodb"
            else "DEV / ATLAS NOT CONNECTED (durable snapshot)" if self.repository.backend == "dev_snapshot"
            else "TEST / ATLAS NOT CONNECTED (in-memory)" if self.settings.effective_run_mode == "TEST"
            else "DEV / ATLAS NOT CONNECTED (in-memory)"
        )
        engineer = self.engine.engineer_provider
        if engineer is None or engineer is self.blue_provider:
            engineer_description = "same as blue"
        else:
            engineer_description = engineer.description
        return {
            "red": self.red_provider.description if self.red_provider else "TEST_MODE deterministic stand-in",
            "blue": self.blue_provider.description if self.blue_provider else "TEST_MODE deterministic stand-in",
            "blue_engineer": engineer_description,
            "mongodb": persistence,
            "vector_search": self.vector_memory.observed_retrieval_backend,
        }

    async def close(self) -> None:
        await self.repository.close()


async def build_stack(settings: Settings | None = None, progress: ProgressSink | None = None) -> CoevolutionStack:
    settings = settings or get_settings()
    mode = settings.effective_run_mode
    real = mode == "REAL"
    strict_persistence = settings.persistence == "atlas"
    # DEV persistence is the labelled default until Atlas is available: durable through
    # the snapshot path when one is configured. REAL still requires real models; it only
    # requires MongoDB/Atlas when PERSISTENCE=atlas.
    snapshot_path = (settings.dev_state_path or None) if (mode != "TEST" and not strict_persistence) else None
    if real and strict_persistence and not settings.has_mongodb:
        raise ProviderError("PERSISTENCE_UNAVAILABLE", "REAL runs require MONGODB_URI when PERSISTENCE=atlas")
    if real and (not settings.red_base_url.strip() or not settings.red_model.strip()):
        raise ProviderError("RED_PROVIDER_UNAVAILABLE", "REAL runs require explicit ai-rig RED_BASE_URL and RED_MODEL")
    repository: MemoryRepository
    if mode != "TEST" and settings.has_mongodb:
        mongo: MongoRepository | None = None
        try:
            mongo = MongoRepository(settings.mongodb_uri, settings.mongodb_database, settings.embedding_dimensions)
            await mongo.start()
            await mongo.ensure_indexes()
            repository = mongo
        except Exception as exc:
            if real:
                if mongo is not None:
                    await mongo.close()
                raise ProviderError("PERSISTENCE_UNAVAILABLE", f"MongoDB connection failed: {exc}") from exc
            logger.warning("MongoDB unavailable (%s); running with DEV persistence", exc)
            if mongo is not None:
                await mongo.close()
            # The CLI owns its snapshot: it is the writer that produces evidence, so the
            # read-only default for observer snapshot adapters must not apply here.
            repository = InMemoryRepository(snapshot_path=snapshot_path, read_only=False)
    else:
        repository = InMemoryRepository(snapshot_path=snapshot_path, read_only=False)
    await repository.start()
    await repository.ensure_indexes()

    embeddings: EmbeddingService
    # The Atlas embedding requirement is about having a real embedding provider, not
    # specifically OpenAI: OpenRouter serves embedding models on the same key Blue uses.
    openai_embedding_key = settings.openai_api_key.get_secret_value() or (
        settings.blue_api_key if settings.blue_provider == "openai" else ""
    )
    openrouter_embedding_key = settings.openrouter_api_key.get_secret_value()
    embedding_key = openai_embedding_key or openrouter_embedding_key
    if real and strict_persistence and not embedding_key:
        await repository.close()
        raise ProviderError("EMBEDDING_PROVIDER_UNAVAILABLE", "REAL runs require an embedding API key when PERSISTENCE=atlas")
    if settings.effective_run_mode == "TEST":
        embeddings = HashEmbedding(settings.embedding_dimensions)
    elif openai_embedding_key:
        embeddings = OpenAIEmbedding(
            settings.embedding_model,
            openai_embedding_key,
            settings.embedding_dimensions,
        )
    elif openrouter_embedding_key:
        # OpenRouter routes its embedding catalogue by provider-qualified id; the
        # default text-embedding-3-small is the OpenAI route. A model the operator
        # sets explicitly (e.g. baai/bge-m3) is passed through untouched.
        model = settings.embedding_model
        if "/" not in model:
            model = f"openai/{model}"
        embeddings = OpenAIEmbedding(
            model,
            openrouter_embedding_key,
            settings.embedding_dimensions,
            # The OpenRouter key is only ever sent to OpenRouter, whatever BLUE_BASE_URL says.
            base_url="https://openrouter.ai/api/v1",
        )
    else:
        embeddings = HashEmbedding(settings.embedding_dimensions)
    vector_memory = VectorMemory(
        repository,
        embeddings,
        use_atlas_vector_search=settings.use_vector_search,
        strict_atlas=strict_persistence,
    )

    try:
        red_provider = None if settings.effective_run_mode == "TEST" else OpenAICompatibleProvider(ProviderConfig.red(settings))
        blue_provider = None if settings.effective_run_mode == "TEST" else OpenAICompatibleProvider(ProviderConfig.blue(settings))
        # The harness-patch engineer is its own role with its own model and fallback; the
        # executor (blue_provider) is unchanged. Ling's known-unsupported response_format
        # is never sent: the fallback config starts in the validated text/JSON path.
        engineer_provider: BlueEngineerProvider | None = None
        engineer_model = settings.blue_engineer_model.strip()
        if settings.effective_run_mode != "TEST" and engineer_model:
            fallback_model = settings.blue_fallback_model.strip()
            engineer_provider = BlueEngineerProvider(
                OpenAICompatibleProvider(ProviderConfig.blue_engineer(settings, engineer_model, json_mode="auto")),
                OpenAICompatibleProvider(ProviderConfig.blue_engineer(settings, fallback_model, json_mode="never"))
                if fallback_model and fallback_model != engineer_model
                else None,
            )
    except ProviderError:
        await repository.close()
        raise
    catalog = ScenarioCatalog()
    engine = CoevolutionEngine(
        repository,
        vector_memory,
        catalog,
        red_provider=red_provider,
        blue_provider=blue_provider,
        engineer_provider=engineer_provider,
        test_mode=settings.effective_run_mode == "TEST",
        red_team_mode=settings.red_team_mode,
        progress=progress,
    )
    return CoevolutionStack(
        settings=settings,
        repository=repository,
        vector_memory=vector_memory,
        catalog=catalog,
        engine=engine,
        red_provider=red_provider,
        blue_provider=blue_provider,
    )


async def assert_real_run(stack: CoevolutionStack) -> None:
    if stack.settings.effective_run_mode != "REAL":
        raise ProviderError("REALITY_ASSERTION_FAILED", "run mode is not REAL")
    # REAL is about real model calls. MongoDB/Atlas are only asserted when the run
    # explicitly asks for the Atlas persistence backend; the default DEV backend is
    # labelled in the banner and the run report rather than dressed up as Atlas.
    strict_persistence = stack.settings.persistence == "atlas"
    if strict_persistence and (
        stack.repository.backend != "mongodb" or not await stack.repository.ping()
    ):
        raise ProviderError("PERSISTENCE_UNAVAILABLE", "PERSISTENCE=atlas requires connected MongoDB")
    if stack.red_provider is None or stack.blue_provider is None:
        raise ProviderError("REALITY_ASSERTION_FAILED", "Red and Blue must use live model providers")
    _assert_ai_rig_origin(stack.settings.red_base_url)
    if strict_persistence and stack.vector_memory.retrieval_backend != "atlas":
        raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", "PERSISTENCE=atlas requires Atlas Vector Search")
    red, blue = await asyncio.gather(probe(stack.red_provider.config), probe(stack.blue_provider.config))
    for result in (red, blue):
        if not result.reachable:
            raise ProviderError(f"{result.role_name}_PROVIDER_UNAVAILABLE", result.detail)
    if strict_persistence:
        try:
            await stack.vector_memory.similar_failures("Atlas availability probe", limit=1)
            vector = await stack.vector_memory.embed_text("Atlas attack index availability probe")
            await stack.repository.vector_search("attacks", "attack_embedding_index", vector, limit=1)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", f"Atlas preflight failed: {exc}") from exc
        if stack.vector_memory.observed_retrieval_backend != "atlas":
            raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", "Atlas retrieval was not observed")
    if not isinstance(stack.engine.runner.evaluator, DeterministicEvaluator):
        raise ProviderError("REALITY_ASSERTION_FAILED", "scenario evaluator is not deterministic sandbox code")
    compiled = HarnessCompiler().compile(baseline_harness("REALITY-CHECK"))
    if not compiled.graph.nodes or not callable(getattr(compiled.runtime, "execute", None)):
        raise ProviderError("REALITY_ASSERTION_FAILED", "RuntimeHarness is not executable")
