# CURRENT DEMO STATE — 2026-09-26 (hackathon venue)

What is true **now**. Historical reports keep their own dates; this file supersedes only
their “current configuration” claims, never their historical evidence. Everything below
was verified in this session unless marked otherwise.

## Runtime truth (verified at the venue)

| Thing | State | Evidence |
|---|---|---|
| Git HEAD | `be39160` (Blue engineer: Nemotron primary + capability-aware Ling fallback) plus the uncommitted reasoning-token fix at the time of writing | `git log` |
| Red model | `qwen3.8-flash-next-heretic2` @ `http://ai-rig.tail6d5242.ts.net:11500/v1` | production probe reachable, chat 266–494 ms, JSON mode accepted |
| Red 27B candidate | `qwen3.8-uncensored:latest` (exact rig ID; annotated “rig 27B” in the global opencode config) | `/v1/models`, global config |
| Blue executor | `inclusionai/ling-3.0-flash-fin:free` (OpenRouter) | probe reachable |
| Blue engineer primary | `nvidia/nemotron-3-super-120b-a12b:free` (OpenRouter) | probe reachable; native JSON mode |
| Blue engineer fallback | `inclusionai/ling-3.0-flash-fin:free`, used only after outright primary failure, `json_mode=never` (never sent the 400-causing request) | config + tests |
| AI rig path | Tailscale up (MagicDNS resolves `ai-rig` → 100.116.103.79), TCP 11500 open, `tailscale ping` 11 ms | venue connectivity check |
| Persistence | DEV durable snapshot (default `backend/.dev-state.json`); Atlas still blocked (no working MongoDB URI) | `/system/status` labels, ATLAS_PERSISTENCE.md |
| Observer backend | **not running**; when started it serves whatever `DEV_STATE_PATH` it is given. The Start-button write hazard is still OPEN — an observer serving a snapshot can be made to write a run into it | no `:8000` listener; known incident |
| Frontend | spatial workspace committed; dev server up at `http://localhost:5175` (IPv6 localhost binding; `127.0.0.1:5175` does not answer) | `lsof`, curl |
| Tests | 201 passed, mypy clean (77 files), ruff clean; frontend build 418.40 kB / 130.36 kB gzip | this session |
| Real evidence | `REAL-ACCEPT-2`, `COEV-SEL-20260926-011123`, `COEV-SEL2-20260926-013728`, `OVERNIGHT-COEV-20260926-022643` snapshots intact; no historical run metadata changed | snapshot files |
| October Bus | connected via the `october-bus` MCP server; this session is agent **Juno**; peers Orion, Atlas, Hades, Apollo, Helios all idle, reachable over the bus | Part 1 audit |

## Report-by-report claim reconciliation

| Report / claim | Status | Current evidence |
|---|---|---|
| `COEVOLUTION_ACCEPTANCE_2026-09-26.md` — “Red selection is empirical (fitness persisted, mutations evaluated, promotions/rejections measured)” | **CURRENT** | engine unchanged except the reasoning-token fix; 23 persisted decisions in the overnight run |
| Same — “189 passed” | **STALE** | 201 passed now (12 Red/Blue selection, 4 Blue-lineage, 5 engineer-provider, 7 reasoning, plus the earlier suites) |
| Same — “Blue = inclusionai/ling-3.0-flash-fin:free” as the engineer | **SUPERSEDED** | engineer primary is Nemotron; Ling is the executor and the explicit fallback (`be39160`, `.env`) |
| `OVERNIGHT_COEV_VERDICT_2026-09-26.md` — 7 generations, 256 calls, C1 held G01–G06, one interrupted candidate | **CURRENT** (historical record; snapshot intact) | snapshot + journal |
| Same — “observer Start button can still write the served snapshot (open)” | **CURRENT** | no guard implemented |
| `BLUE_BAKEOFF_2026-09-26.md` — PRIMARY Nemotron, FALLBACK Ling Fin; Inkling unusable (403); North too slow | **CURRENT** and **IMPLEMENTED** | `be39160`, probes at the venue |
| `REALITY_AUDIT.md` — “no Blue promotion; `final_red_champion` overstates selection; main EVOLVE workbench is UI-only for co-evolution” | **SUPERSEDED** by later work (accurate for its date) | REAL-ACCEPT-2 promotion; Red fitness persisted; spatial workspace replaced the workbench |
| `VERIFICATION_REPORT_2026-09-25.md` — “`.env.example` still names `thinkingmachines/in:free`” | **SUPERSEDED** | `.env.example` now documents Ling executor + Nemotron engineer + Ling fallback |
| `RED_PROVIDER_AUDIT.md` — ai-rig offline caveat | **SUPERSEDED** | rig online and verified at the venue |
| `ATLAS_PERSISTENCE.md` — Atlas blocked by missing credentials | **CURRENT** | no Atlas connection; DEV snapshot labels in every run report |
| `HISTORICAL_CHAMPION_SAMPLING.md` — arm closed with an end-to-end test | **CURRENT** | `test_two_same_run_promotions_produce_a_historical_comparison_end_to_end` passes |
| Interrupted-run bookkeeping (`_settle_orphans`, reconciled counters, resume) | **CURRENT** | present and tested; overnight resume proved it in REAL |
| Resume across a generation boundary can duplicate a generation label | **CURRENT (known caveat)** | overnight G05 had 4 decisions (one re-entry mutation) |
| `UIOVERHAUL.md` / `darwinguard_real_coevolution_task.md` | **CURRENT** (requirement docs) | spatial workspace + empirical selection delivered |

## Red model bake-off (2026-09-26, venue) — DECISION: KEEP FLASH-NEXT

Same production path for both models: five attack-generation calls each (three seed tactic
priors x two candidates), BLACK_BOX, production parser/validator, fixed executor, and every
generated attack executed against both the baseline B0 and the promoted C1 from the
overnight REAL run. Evidence: `backend/experiments/red-bakeoff/results.json`.

| Metric | Flash-Next | Qwen 3.8 27B (`qwen3.8-uncensored:latest`) |
|---|---:|---:|
| Generation calls | 5 | 5 |
| Avg latency | 28.8 s | 24.4 s |
| Throughput | 68.3 tok/s | 100.7 tok/s |
| Attacks generated | 10 | 10 |
| Generation failures | 0 | 0 |
| Reasoning-only retries | 1 | 1 |
| Breaches vs B0 | **6** | 1 |
| Breaches vs C1 | 0 | 0 |
| ASR | **0.30** | 0.05 |
| Red fitness | **0.358** | 0.195 |
| Diversity | 4 families / 10 unique payloads | 4 families / 10 unique payloads |

Rule check: latency advantage is not dramatic (~15%), reliability is equal, diversity is
equal, but effectiveness is materially worse (one breach vs six, fitness ~1.8x lower).
Neither model breached the promoted C1, matching the overnight finding. Production Red stays
`qwen3.8-flash-next-heretic2`; the 27B remains available as an alternate rig model.

## Open items that matter for the demo

1. **Observer write hazard**: starting a run through an observer server that serves an evidence snapshot writes into that snapshot. Not fixed.
2. **Atlas**: persistence is DEV snapshot only; every report is labelled “DEV / ATLAS NOT CONNECTED”.
3. **Interrupted candidate**: `R-…-G08-cc4699b5` in the overnight snapshot is ACTIVE with no evaluation; a future resume evaluates it before selection.
