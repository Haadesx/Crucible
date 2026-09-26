# DarwinGuard Venue Audit — 2026-09-26 (hackathon venue)

One focused audit/hardening pass: October Bus MCP, project-evidence reconciliation, the Red
reasoning-token fix, and a controlled Red model bake-off. No redesign; no historical run
evidence modified.

Commit: `a4a2b87` (this audit) · Working tree clean.

---

## OCTOBER BUS

- **Connected:** YES — remote MCP server `october-bus` at `http://127.0.0.1:${OCTOBER_BUS_PORT}/mcp`
  (canvas/node/capability-scoped headers). Its tools are the ones registered in this session.
- **Current agent:** Juno (terminal `term-muhk7m19-3o`, opencode). Workspace folder
  `/Volumes/Auxilary/Side_Projects/HackMongo`, checkout `07a7fbfe-bcc1-461c-b520-b73994800e15`.
  This agent is **not an operation member**, so team-member tools are unavailable; peer
  messaging and the task board work.
- **Peers:** Orion (idle) · Atlas (idle) · Hades (idle) · Apollo (idle) · Helios (idle) —
  all terminals, all reachable via Juno→each canvas edge. No Vulture/October workers present.
- **Pending messages:** none (inbox empty). Nothing was acknowledged, claimed, released,
  completed, or mutated during the audit.
- **Shared tasks:** 7, **all done** — RED-01 (`t-64577d39`), RUNTIME-01 (`t-3136baeb`),
  BLUE-01 (`t-6040f080`), AUDIT-01 (`t-43dbbe4e`), historical-sampling verdict (`t-ef575bb0`),
  historical-arm closure (`t-c81c815c`), ORION-TAKEOVER (`t-a61ebb0b`). No open/claimed/blocked.

### Capability matrix (from the registered tools)

| Capability | Tool(s) | Notes |
|---|---|---|
| Peer discovery | `list_peers`, `list_canvas`, `find_sessions` | canvas shows nodes + edges |
| Inbox / messages | `check_inbox`, `message_peer`, `message_parent`, `message_child` | mode `notify` by default |
| Correlated request/reply | `message_peer` mode `request` → reply mode `response` + `responseTo` | durable delivery to terminals |
| Task board | `add_task`, `list_tasks` | self-contained descriptions |
| Claim / complete | `claim_task`, `complete_task` | no explicit release; stale claims re-claimable |
| Dependencies | `add_task` with `after: [task ids]` | task unblocked when deps complete |
| Progress / status | `get_node_status` (+`history`), `report_assignment`, `get_child_status` | non-interrupting |
| Human escalation | `ask_user` | blocks for a human answer |
| Child agents | `add_terminal`, `add_chat`, `send_to_node`, `wait_for_nodes`, `stop_child` | isolated workspaces available |

**Can OpenCode agents communicate directly:** YES — `message_peer` notify/request/response
with a correlation id, plus the durable task board.
**Can it work without October chat as the orchestrator:** YES for transport and coordination —
the bus injects messages/tasks into each agent session and each session reasons and replies;
October chat is not the reasoning layer. (Team-member tools require operation membership,
which this session does not have.)

---

## MARKDOWN / PROJECT STATE

- **Current git HEAD:** `a4a2b87` (previously `be39160`).
- **Working tree:** clean.
- **Current-state Markdown:** `docs/CURRENT_DEMO_STATE_2026-09-26.md` (created this session;
  claim-by-claim reconciliation plus the Red bake-off decision).

### Claim reconciliation (summary)

| Report / claim | Status | Evidence |
|---|---|---|
| `COEVOLUTION_ACCEPTANCE_2026-09-26.md` — Red selection is empirical | **CURRENT** | engine unchanged except the reasoning-token fix; 23 persisted decisions in the overnight run |
| Same — “189 passed” | **STALE** | 201 passed now |
| Same — Blue engineer = Ling | **SUPERSEDED** | engineer primary Nemotron; Ling is executor + fallback (`be39160`) |
| `OVERNIGHT_COEV_VERDICT_2026-09-26.md` — 7 generations, C1 held G01–G06 | **CURRENT** | snapshot + journal intact |
| Same — observer Start-button write hazard open | **CURRENT** | no guard implemented |
| `BLUE_BAKEOFF_2026-09-26.md` — Nemotron primary, Ling fallback | **CURRENT**, implemented | probes at the venue |
| `REALITY_AUDIT.md` — no promotion / red_champion overstates / workbench UI-only | **SUPERSEDED** (accurate for its date) | REAL-ACCEPT-2 promotion; persisted Red fitness; spatial UI |
| `VERIFICATION_REPORT_2026-09-25.md` — stale `.env.example` model | **SUPERSEDED** | `.env.example` updated |
| `RED_PROVIDER_AUDIT.md` — ai-rig offline caveat | **SUPERSEDED** | rig online and verified |
| `ATLAS_PERSISTENCE.md` — Atlas blocked | **CURRENT** | DEV snapshot labels |
| `HISTORICAL_CHAMPION_SAMPLING.md` — arm closed with test | **CURRENT** | test passes |
| Resume across a boundary can duplicate a generation label | **CURRENT (known caveat)** | overnight G05 had 4 decisions |

---

## REASONING TOKEN FIX

- **Root cause:** the rig's Red model is a reasoning model — an insufficient output budget is
  consumed by `reasoning_content`, returning `finish_reason=length` with empty visible
  `content`. The old provider retried empties at the same budget while the structured-output
  layer escalated from a stale budget copy, producing up to 9 calls and the observed
  empty-completion retry storms.
- **Old behavior:** `empty completion retry 1/2`, `2/2`, `empty completion`, repeated per
  escalated budget; hidden reasoning ignored.
- **New behavior:** explicit conditions — `reasoning-only completion (finish_reason=…, N
  reasoning chars)` vs `empty completion (finish_reason=…)`; hidden reasoning is never used
  as the answer and never persisted (only the condition in the ledger); an empty retry
  raises the final-output budget in place; a length-truncated final answer also raises the
  next repair round's budget; the two escalation paths are unified via the error's
  `output_budget`.
- **Retry/budget:** chat retries ≤2 with 2× budget each; structured-output escalation stays
  as a bounded backstop; worst case is now **3 calls (3000 → 6000 → 12000)** instead of 9;
  then fails closed (`*_PROVIDER_EMPTY_RESPONSE`); malformed output still fails with
  `*_PROVIDER_UNUSABLE_OUTPUT`.
- **Tests:** 7 new in `tests/test_provider_reasoning.py` (normal; reasoning+valid content;
  reasoning-only; length-termination; successful escalation; bounded failure;
  truncated-JSON repair escalation) plus 4 existing fail-closed tests updated to the new
  contract. **201 passed**, mypy (77 files) clean, ruff clean.
- **Live confirmation:** during the bake-off, Flash-Next call 3 hit a reasoning-only
  completion (14,171 reasoning chars) and the new escalation resolved it on the retry with
  `max_tokens=6000`.

---

## RED MODEL BAKE-OFF

Same production path for both models: five generation calls each (three seed tactic priors ×
two candidates), production prompt, BLACK_BOX, production parser/validator, fixed executor,
and every generated attack executed against the baseline **B0** and the promoted **C1** from
the overnight REAL run. Evidence: `backend/experiments/red-bakeoff/results.json`.

| Metric | Flash-Next | Qwen 3.8 27B |
|---|---:|---:|
| Generation calls | 5 | 5 |
| Avg latency | 28.8 s | 24.4 s |
| Throughput | 68.3 tok/s | 100.7 tok/s |
| Valid attacks | 10 / 10 | 10 / 10 |
| Empty completions | 0 | 0 |
| Reasoning-only retries | 1 | 1 |
| Breaches (all episodes) | **6** | 1 |
| Breaches vs B0 | **6** | 1 |
| Breaches vs C1 | 0 | 0 |
| ASR | **0.30** | 0.05 |
| Red fitness | **0.358** | 0.195 |
| Diversity | 4 families / 10 unique payloads | 4 families / 10 unique payloads |
| Generation failures | 0 | 0 |

Model IDs verified from the rig: `qwen3.8-flash-next-heretic2` and
`qwen3.8-uncensored:latest` (annotated rig-27B in the global opencode config).

---

## RED MODEL DECISION

`KEEP FLASH-NEXT`

- The 27B is only ~15 % faster in wall clock (24.4 s vs 28.8 s) despite +47 % tok/s; reasoning
  tokens dominate, so the speed win is not dramatic.
- Effectiveness is materially worse: 1 breach vs 6, ASR 0.05 vs 0.30, fitness 0.195 vs 0.358
  on identical tasks.
- Reliability is equal: 10/10 valid, 0 failures, 1 reasoning-only retry each (handled by the
  new escalation).
- Diversity is equal (4 families, 10 unique payloads), so the difference is attack quality,
  not breadth.
- No switch = no config churn and no dual-path risk; the 27B remains available on the rig.

---

## BLUE

- **Primary:** `nvidia/nemotron-3-super-120b-a12b:free`
- **Fallback:** `inclusionai/ling-3.0-flash-fin:free` (`json_mode=never`; the 400-causing
  request is never sent)
- **Reachability:** executor Ling, engineer primary, and fallback all probed reachable at the
  venue; historical patches remain correctly attributed (overnight patches → Ling).

---

## REAL SMOKE TEST

`PASS`

- Production Red client at the venue: preflight probe reachable, chat `'READY'` in 266–494 ms,
  structured-output JSON accepted in 2.1 s, 3 calls / 0 errors.
- Earlier REAL Blue-engineer smoke (Nemotron patch → compiled 8 graph nodes → 10-battle
  replay → deterministic PROMOTION to `B-SMOKE-…-G01-C1`) remains the end-to-end evidence.
  No Red switch was made, so no new breach smoke was required.

---

## DEMO READINESS

`READY WITH CAVEATS`

1. **Observer write hazard** — clicking Start on a server that serves an evidence snapshot
   writes into it; use a dedicated runtime snapshot for live runs.
2. **Services not running** — start the API with a fresh `DEV_STATE_PATH` and the frontend
   dev server (currently up on `http://localhost:5175`, IPv6 binding).
3. **DEV persistence only** (Atlas blocked) — present as labelled DEV-snapshot evidence, not
   Atlas.
