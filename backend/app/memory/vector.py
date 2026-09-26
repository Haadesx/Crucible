import hashlib
import math
import re
from typing import Any, Protocol

from app.models.attack import AttackGenome, AttackRecord
from app.models.memory import FailureMemory
from app.coevolution.providers import ProviderError
from app.memory.repository import MemoryRepository


class EmbeddingService(Protocol):
    dimensions: int

    async def embed(self, text: str) -> list[float]: ...


class HashEmbedding:
    """Credential-free fallback with stable bag-of-features cosine similarity."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        if not any(vector):
            digest = hashlib.blake2b(text.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] = 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAIEmbedding:
    """Embeddings over any OpenAI-compatible endpoint, including OpenRouter.

    OpenRouter reaches embedding models through the same ``/embeddings`` endpoint
    even though they do not appear in its ``/models`` catalogue; ``base_url`` is
    what selects the provider.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        dimensions: int = 1536,
        base_url: str | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding


def attack_text(attack: AttackGenome) -> str:
    return (
        f"carrier {attack.carrier}; strategy {attack.strategy}; target {attack.target_tool}; "
        f"placement {attack.placement}; indirection {attack.indirection_level}; "
        f"obfuscation {attack.obfuscation_level}; authority {attack.social_authority}"
    )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


class VectorMemory:
    def __init__(
        self,
        repository: MemoryRepository,
        embeddings: EmbeddingService,
        use_atlas_vector_search: bool = False,
        strict_atlas: bool = False,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.use_atlas_vector_search = use_atlas_vector_search
        self.strict_atlas = strict_atlas
        if strict_atlas and use_atlas_vector_search and repository.backend != "mongodb":
            raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", "Atlas Vector Search requires MongoDB")
        self.observed_retrieval_backend = (
            "unverified" if use_atlas_vector_search and repository.backend == "mongodb" else "local"
        )

    @property
    def retrieval_backend(self) -> str:
        if self.use_atlas_vector_search and self.repository.backend == "mongodb":
            return "atlas"
        return "local"

    async def novelty(self, attack: AttackGenome, records: list[AttackRecord]) -> float:
        query = await self.embeddings.embed(attack_text(attack))
        if self.retrieval_backend == "atlas":
            try:
                documents = await self.repository.vector_search(
                    "attacks",
                    "attack_embedding_index",
                    query,
                    limit=100,
                )
                nearest = 0.0
                for document in documents:
                    record_id = str(document.get("_id") or document.get("attack_id") or "")
                    if not record_id or record_id == attack.id:
                        continue
                    nearest = max(nearest, self._document_similarity(document, query))
                self.observed_retrieval_backend = "atlas"
                return max(0.0, min(1.0, 1.0 - nearest))
            except Exception as exc:
                if self.strict_atlas:
                    raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", f"Atlas attack query failed: {exc}") from exc

        self.observed_retrieval_backend = "local"
        nearest = 0.0
        for record in records:
            if record.genome.id == attack.id:
                continue
            candidate = record.embedding or await self.embeddings.embed(attack_text(record.genome))
            nearest = max(nearest, cosine_similarity(query, candidate))
        return max(0.0, min(1.0, 1.0 - nearest))

    async def similar_failures(
        self,
        summary: str,
        limit: int = 5,
    ) -> list[FailureMemory]:
        query = await self.embeddings.embed(summary)
        if self.retrieval_backend == "atlas":
            try:
                documents = await self.repository.vector_search(
                    "memories",
                    "memory_embedding_index",
                    query,
                    limit=limit,
                )
                matches: list[FailureMemory] = []
                for document in documents:
                    failure_id = str(document.get("_id") or "")
                    if not failure_id:
                        continue
                    failure = await self.repository.get_failure(failure_id)
                    if failure is None:
                        continue
                    score = self._document_similarity(document, query)
                    if score > 0.1:
                        matches.append(failure.model_copy(update={"similarity": score}))
                self.observed_retrieval_backend = "atlas"
                return matches
            except Exception as exc:
                if self.strict_atlas:
                    raise ProviderError("VECTOR_SEARCH_UNAVAILABLE", f"Atlas memory query failed: {exc}") from exc

        self.observed_retrieval_backend = "local"
        failures = await self.repository.list_failures(limit=100)
        scored: list[tuple[float, FailureMemory]] = []
        for failure in failures:
            candidate = failure.embedding or await self.embeddings.embed(failure.summary)
            score = cosine_similarity(query, candidate)
            scored.append((score, failure.model_copy(update={"similarity": score})))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [failure for score, failure in scored[:limit] if score > 0.1]

    @staticmethod
    def _document_similarity(document: dict[str, Any], query: list[float]) -> float:
        score = document.get("score")
        if isinstance(score, (int, float)):
            return max(0.0, min(1.0, float(score)))
        embedding = document.get("embedding")
        if isinstance(embedding, list) and all(isinstance(value, (int, float)) for value in embedding):
            return max(0.0, min(1.0, cosine_similarity(query, [float(value) for value in embedding])))
        return 0.0

    async def embed_text(self, text: str) -> list[float]:
        return await self.embeddings.embed(text)

    async def embed_attack_record(self, record: AttackRecord) -> AttackRecord:
        if not record.embedding:
            record = record.model_copy(update={"embedding": await self.embeddings.embed(attack_text(record.genome))})
        return record
