# MongoDB Atlas persistence — configuration and verification

This document is the operator checklist for running DarwinGuard with real MongoDB Atlas
instead of the labelled local DEV backend. The strict path is enforced by
`app.coevolution.runtime.build_stack` / `assert_real_run` and by `python -m app.audit_runtime`;
nothing here weakens those guards.

## Status on this machine (2026-09-25)

- **No Atlas connection string is configured.** `backend/.env` has `MONGODB_URI=` empty; no
  `mongodb+srv` URI exists in the repo, the shell environment, or home config files; there is no
  `atlas` CLI and no Atlas account configured. October's Company Brain (which mentions
  `mongodb+srv` in its local facts DB) is **disabled**, so no credential can be retrieved through
  the authorised memory interface.
- **Embedding provider: resolved through OpenRouter.** No `OPENAI_API_KEY` is set, so the runtime
  now uses the OpenRouter key for `/embeddings`; verified live with
  `openai/text-embedding-3-small` (1536 dims) and `baai/bge-m3` (1024). OpenRouter publishes no
  `:free` embedding endpoints, but the listed models cost ~$0.02/M tokens or less, which is
  negligible at DarwinGuard's volumes.
- The only reachable MongoDB deployments are local Docker containers `hackmongo-mongo` (`mongo:7`,
  port 27017) and `hackmongo-rs` (`mongo:7`, port 27018). These are **standalone Community
  MongoDB**, not Atlas: they cannot serve `$vectorSearch`, and they must never be labelled Atlas.
- Therefore `RUN_MODE=REAL + PERSISTENCE=atlas` still fails closed: without a URI it stops at
  `PERSISTENCE_UNAVAILABLE`; pointed at a non-Atlas MongoDB it stops at `VECTOR_SEARCH_UNAVAILABLE`.
  No REAL run has used Atlas.

## Embedding providers (verified 2026-09-25)

`OPENAI_API_KEY` wins when set; otherwise the runtime routes embeddings through OpenRouter on the
Blue key and provider-qualifies a bare model id (`text-embedding-3-small` → `openai/text-embedding-3-small`).
Verified working through `POST {base_url}/embeddings`:

| Model | Dimensions | Approx. cost |
| --- | --- | --- |
| `openai/text-embedding-3-small` (default; honours `dimensions`) | 1536 (default) | ~$0.02 / M tokens |
| `baai/bge-m3` | 1024 | ~$0.04 / M tokens |
| `perplexity/pplx-embed-v1-0.6b` | 1024 | ~$0.004 / M tokens |
| `intfloat/multilingual-e5-large` | 1024 | ~$0.04 / M tokens |
| `qwen/qwen3-embedding-8b` | 4096 | ~$0.02 / M tokens |
| `google/gemini-embedding-001` | 3072 | ~$0.15 / M tokens |

For any non-OpenAI choice set `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` and the Atlas index
`numDimensions` together; a mismatch is rejected by the server at query time.

## Prerequisites checklist

| Setting | Value | Why |
| --- | --- | --- |
| `RUN_MODE` | `REAL` | REAL requires real Red/Blue providers and the ai-rig Tailnet origin. |
| `PERSISTENCE` | `atlas` | Turns on the strict persistence assertions. |
| `MONGODB_URI` | `mongodb+srv://…` (Atlas) | `has_mongodb`; connection is attempted in REAL. |
| `MONGODB_DATABASE` | e.g. `darwinguard` | Database name; collections are created on first write. |
| `USE_VECTOR_SEARCH` | `true` (default) | Routes novelty/failure retrieval through `$vectorSearch`. |
| `OPENAI_API_KEY` or `OPENROUTER_API_KEY` | embedding provider key | REAL + atlas requires an embedding provider (`EMBEDDING_PROVIDER_UNAVAILABLE` otherwise). `OPENAI_API_KEY` wins; without it the runtime uses the OpenRouter `/embeddings` route on the Blue key. `blue_api_key` is only the fallback when `BLUE_PROVIDER=openai`. |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | `text-embedding-3-small` / `1536` | Must match the vector index dimensions exactly. |
| `RED_BASE_URL` | ai-rig Tailnet address | REAL-mode origin guard (`RED_ORIGIN_UNVERIFIED` otherwise). |
| `BLUE_PROVIDER` / `BLUE_MODEL` | `openrouter` / `inclusionai/ling-3.0-flash-fin:free` | Intended Blue runtime model. |

## Atlas Vector Search indexes

`ensure_indexes()` creates only regular indexes. The two vector indexes must be created in Atlas
(UI → Atlas Search → JSON editor, or the Atlas Admin API / `atlas` CLI). Both use the same shape;
the names and collections are read from `backend/app/memory/vector.py`.

- Collection **`attacks`**, index name **`attack_embedding_index`**
- Collection **`memories`**, index name **`memory_embedding_index`**

```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine" }
  ]
}
```

The query pipeline (`MongoRepository.vector_search`, `backend/app/memory/mongodb.py`) runs
`$vectorSearch` with `path="embedding"`, `numCandidates=max(100, limit*10)` and projects
`{"score": {"$meta": "vectorSearchScore"}}`. If `EMBEDDING_DIMENSIONS` is changed, the index
`numDimensions` must be changed with it.

Note: `USE_CHANGE_STREAMS=true` uses `MongoChangeStreamBridge`; change streams require a replica
set / Atlas deployment. On standalone local MongoDB the bridge degrades best-effort; on Atlas it
is a supported path.

## Collections the adapter persists

`attacks`, `defenses`, `episodes`, `generations`, `red_agent_versions`, `blue_agent_versions`,
`attack_candidates`, `harness_patches`, `model_calls`, `hall_of_fame`, `run_reports`, `harnesses`,
`harness_diffs`, `memories`, `arena_events`, `runtime_state`, `scenarios` (plus `command` for the
ping). All reads/writes go through `MongoRepository`; the engine never issues ad-hoc queries.

## Verification commands

```bash
# 1. Strict preflight: REAL + atlas. Exit 0 prints REAL/ATLAS state; failure is loud.
RUN_MODE=REAL PERSISTENCE=atlas MONGODB_URI='mongodb+srv://…' OPENROUTER_API_KEY='…'  # or OPENAI_API_KEY='…' \
  backend/.venv/bin/python -m app.audit_runtime

# 2. A real experiment persisted to Atlas
cd backend && RUN_MODE=REAL PERSISTENCE=atlas MONGODB_URI='mongodb+srv://…' OPENROUTER_API_KEY='…'  # or OPENAI_API_KEY='…' \
  .venv/bin/python -m app.coevolution --mode real --generations 3 \
  --red-versions 2 --attacks-per-version 1 --blue-candidates 3 --baseline naked --run-id ATLAS-1

# 3. Read back from a separate process (counts must match the run report)
RUN_MODE=REAL PERSISTENCE=atlas MONGODB_URI='mongodb+srv://…' OPENROUTER_API_KEY='…'  # or OPENAI_API_KEY='…' \
  backend/.venv/bin/python -m app.audit_runtime
```

`assert_real_run` refuses to start if the repository is not reachable, and `CoevolutionEngine.run`
resumes a re-entered run id from its persisted generation records — an interrupted experiment
continues instead of becoming a new, unrelated one.

## Fail-closed map

| Condition | Error code | Behaviour |
| --- | --- | --- |
| `PERSISTENCE=atlas` without `MONGODB_URI` | `PERSISTENCE_UNAVAILABLE` | Refuses to build; no DEV fallback. |
| Atlas unreachable / connection fails | `PERSISTENCE_UNAVAILABLE` | REAL refuses; DEV logs and uses snapshot. |
| Atlas connected but neither embedding key set | `EMBEDDING_PROVIDER_UNAVAILABLE` | Refuses to substitute hash embeddings. |
| Vector search index missing / query fails | `VECTOR_SEARCH_UNAVAILABLE` | Strict mode raises; never silently falls back to local cosine. |
| Retrieval backend never observed as `atlas` | `VECTOR_SEARCH_UNAVAILABLE` | `assert_real_run` fails before any model call. |
| Red base URL not the online ai-rig Tailnet peer | `RED_ORIGIN_UNVERIFIED` | Refuses the REAL run. |

The API's observatory reports `atlas_connected = mongodb_connected and ("mongodb.net" in uri or
uri.startswith("mongodb+srv"))` (`backend/app/api/generations.py:206`); this is a display
heuristic, not a substitute for the runtime assertions above.
