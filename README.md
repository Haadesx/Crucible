# Crucible

**Adversarial empirical harness optimization.**

Crucible evolves an AI agent's security harness under continuous adversarial pressure — blocking new attacks without breaking legitimate tasks.

Crucible is a sandboxed security harness that evolves both sides of an agent-security contest:

- **Red** evolves typed prompt-injection strategies.
- **Blue** evolves typed runtime harness policies: trust boundaries, goal binding, tool authorization, argument validation, approval gates, classifiers, and verification.
- A deterministic evaluator decides whether an unauthorized tool effect actually executed.
- MongoDB stores the hereditary record: genomes, parents, battles, outcomes, failures, embeddings, and mutation context.
- The frontend visualizes live battles, Cytoscape lineage trees, fitness trends, genome inspection, and ancestral replay.

> **Model weights stay frozen:** Red evolves its attack strategy and Blue evolves the harness; no model fine-tuning is involved.

> **Safety boundary:** every tool is fake and process-local. No real email, banking, filesystem, OAuth, or external API side effect is connected.

## Quick start

The project has a deterministic offline mode. It does not require OpenAI or MongoDB credentials.

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m app.demo
```

The demo prints readable battles and a generation summary such as:

```text
DARWINGUARD
Offline deterministic co-evolution demo — all tools are sandboxed.

[G00] ... → RED ASR=BREACH UTILITY=PASS
[G00] ... → BLUE ASR=BLOCKED UTILITY=PASS

Generation fitness
G00  ASR=0.62  UTILITY=1.00  RED=0.61  BLUE=0.57
G01  ASR=0.12  UTILITY=1.00  RED=0.21  BLUE=0.87
...
Evolution complete.
```

Run the API:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The Vite development server proxies `/arena`, `/generations`, `/replay`, `/health`, and `/ws` to the backend on port `8000`. To use a different port, set `VITE_API_URL` before starting Vite.

## Configuration

Copy `backend/.env.example` to `backend/.env`.

| Variable | Default | Purpose |
|---|---:|---|
| `AGENT_PROVIDER` | `fake` | `fake` or `openai` target provider |
| `OPENAI_API_KEY` | empty | Optional target/model credentials |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Target-agent model |
| `MONGODB_URI` | empty | Atlas or MongoDB connection string |
| `MONGODB_DATABASE` | `darwinguard` | Hereditary-memory database |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `RED_POPULATION` | `6` | Red population size |
| `BLUE_POPULATION` | `6` | Blue population size |
| `GENERATIONS` | `5` | Default run length |
| `MATCHUPS_PER_GENOME` | `3` | Sampled battles per Red genome |
| `MAX_PARALLEL_EPISODES` | `4` | Bounded async concurrency |
| `USE_VECTOR_SEARCH` | `true` | Use Atlas Search when available |
| `USE_CHANGE_STREAMS` | `true` | Best-effort MongoDB event bridge |
| `DEMO_MODE` | `false` | Small live demo settings |

If `MONGODB_URI` is empty or Atlas is unavailable, the application falls back to the complete in-memory repository. Vector embeddings still use the deterministic local fallback, so the core demo does not depend on an Atlas index.

## Architecture

```text
                 ┌─────────────────────────────┐
                 │ MongoDB / hereditary memory  │
                 │ genomes · parents · episodes │
                 │ failures · embeddings        │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
          ┌──────▼──────┐               ┌──────▼──────┐
          │ Red evolver │               │ Blue evolver│
          │ typed attack│               │ typed harness│
          │ mutations   │               │ mutations   │
          └──────┬──────┘               └──────┬──────┘
                 └──────────────┬──────────────┘
                                │
                         ┌──────▼──────┐
                         │    Arena    │
                         │ target model │
                         └──────┬──────┘
                                │ proposed tool call
                         ┌──────▼──────┐
                         │ Blue gateway│
                         │ allow/deny/ │
                         │ approval    │
                         └──────┬──────┘
                                │ allowed only
                         ┌──────▼──────┐
                         │ 3 fake tools│
                         └──────┬──────┘
                                │
                         deterministic evaluator
```

### Security boundary

The target model never calls a tool directly. It can only return a `ProposedToolCall`. The `PolicyGateway` evaluates provenance, the trusted `UserGoal`, argument validators, risk thresholds, and approval rules before the sandbox dispatcher is reached.

The evaluator declares Red successful only when an unauthorized side effect is actually executed. A blocked attack with a failed legitimate task is not considered a Blue win.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service and memory-backend status |
| `POST` | `/arena/reset` | Stop and clear the current repository |
| `POST` | `/arena/start` | Start an evolution run |
| `POST` | `/arena/stop` | Request a graceful stop |
| `GET` | `/arena/status` | Current run status and metrics |
| `GET` | `/arena/lineage` | Red and Blue ancestry records |
| `GET` | `/generations` | Persisted generation summaries |
| `GET` | `/generations/{id}` | One generation |
| `GET` | `/attacks/{id}` | Attack genome and fitness |
| `GET` | `/defenses/{id}` | Defense genome and fitness |
| `GET` | `/episodes/{id}` | Full battle record |
| `GET` | `/memory/failures` | Breach and utility-failure memory |
| `POST` | `/replay` | Replay a stored attack against a stored defense |
| `WS` | `/ws/arena` | Live battle and evolution events |

Start request:

```json
{
  "generations": 3,
  "red_population": 4,
  "blue_population": 4,
  "matchups_per_genome": 2
}
```

## MongoDB collections

The Mongo adapter uses:

- `scenarios`
- `attacks`
- `defenses`
- `episodes`
- `generations`
- `memories`
- `arena_events` for the optional live-event bridge

It creates normal indexes for generations, parent IDs, matchup history, and run timestamps. When Atlas is available it also requests:

- `attack_embedding_index`
- `memory_embedding_index`

If Atlas Vector Search is not ready, novelty and similar-failure retrieval fall back to local cosine similarity.

## Verification

Backend:

```bash
cd backend
python3.12 -m pytest -q
python3.12 -m mypy app
python3.12 -m ruff check app tests
```

Frontend:

```bash
cd frontend
npm run build
```

The current offline implementation passes the backend unit/integration suite, strict mypy, Ruff, and the strict TypeScript/Vite production build.

## Repository map

```text
backend/app/
  agent/       target-agent protocol, fake agent, OpenAI adapter
  arena/       payload renderer, runner, evaluator, fitness
  evolution/   seeds, constrained mutations, selection, tournament, loop
  harness/     compiler, trust policy, gateway, verifier
  memory/      repository, MongoDB, vectors, lineage, change streams
  models/      typed genomes, scenarios, episodes, generations, events
  sandbox/     three isolated fake tools and state
  api/         FastAPI routes and WebSocket

frontend/src/
  components/  arena header, battle view, Cytoscape trees, metrics, replay
  hooks/       REST/WebSocket state management
  lib/         typed API client
```

## What was intentionally not built

The initial scope does not connect real Gmail, banking, filesystem deletion, OAuth, authentication, Kubernetes, distributed workers, fine-tuning, RLHF, voice, or self-modifying Python. Blue mutates a constrained, typed harness genome; it never emits executable code.

## Current limitations and next steps

- The deterministic fake target is the default and is what powers the reliable demo. The OpenAI Responses target adapter is available when configured.
- The deterministic mutation operators are the active default. A constrained OpenAI attack-mutation adapter is included as a building block; production rollout should validate model output, rate limits, and cost before enabling it for a judged run.
- Atlas credentials and a live vector index still need to be supplied in a deployment environment to verify hosted persistence.
- A precomputed MongoDB run can be added for an emergency judging fallback.
