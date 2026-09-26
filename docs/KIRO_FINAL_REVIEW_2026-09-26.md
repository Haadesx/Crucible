# DarwinGuard — Kiro Final Review (Product, Safety & UI)

**Date:** 2026-09-26 · **Reviewed HEAD:** `2795934` (one commit past `01fbba1`; adds only `backend/experiments/DEMO-LIVE-PROOF-20260926/state.json` — 5 calls, 0 generations, no secrets)

## KIRO VERDICT

```text
DO NOT DEMO YET
```

The backend and the evidence hold up. Three UI and demo-script problems could make a judge see the wrong thing, and each is under 30 minutes to fix. Fix them, then freeze.

## BACKEND CRITICAL CHECKS

```text
Historical snapshot safety:   PASS
Atlas persistence integrity:  PASS
No silent fallback:           PASS
Nemotron shipping path:       PASS
Historical attribution:       PASS
Demo commands:                FAIL
Secrets exposed/committed:    NO
```

What I checked:

- **Historical safety:** I served copies of both historical snapshots on :8010 and :8011. `/arena/start`, `/arena/reset`, `/replay` and `/replay/compare` all returned 409. The source hashes didn't change (`10373cb9…` and `f7d01684…`). The guard sits in the repository's single write path (`_persist`), and every POST route except `/arena/stop` goes through `require_writable`.
- **Atlas:**
  - The observer (pid 33804) started at 13:12 and serves `DARWINGUARD-EVENT-20260926`, which was written at 13:05. That is a real fresh-process readback: 1 generation, 17 episodes, 21 calls, 1 patch, 1 report.
  - Both vector indexes (`attack_embedding_index`, `memory_embedding_index`) are READY and hold 1,536-dim embeddings. A direct `$vectorSearch` returned rows.
  - `/harnesses/active` correctly returns B0.
- **No silent fallback:** a REAL run with `PERSISTENCE=atlas` fails with `PERSISTENCE_UNAVAILABLE` (covered by tests). A DEV observer does fall back, but it logs a warning and its persistence label says so honestly.
- **Nemotron:** the patch's model call in both the VENUE smoke run and the Atlas run is `blue_harness_engineer` / `nvidia/nemotron-3-super-120b-a12b:free`, with no error.
  - `VENUE-SHIPPING-SMOKE-20260926-125109`: 1 × `SET_PARAMETER`, 9-battle replay, PROMOTED at fitness 0.720.
  - Atlas run: 1 × `SET_PARAMETER`, REJECTED with reason "utility fell from 0.62 to 0.50".
- **Historical claims:**
  - All 6 historical patches trace to `inclusionai/ling-3.0-flash-fin:free` model calls.
  - Overnight is 7 generations and 256 calls (142 executor / 81 attacker / 29 mutator / 4 engineer).
  - Two-sided ASR is `[0.0, 0.333, 0.667, 0.0]`, with 132 calls.
  - I found no cross-run leakage in model calls.
- **Gates:** pytest 206 passed, 1 skipped. mypy is clean (77 files), ruff is clean (app + tests), and `tsc -b` exits 0.
- **Secrets:** a `git grep` for credential patterns found nothing, and `backend/.env` is ignored. The tracked `CONFIG.env` has an empty `MONGODB_URI` and no keys.

## UI PRODUCT VERDICT

```text
UI PARTIALLY FITS DARWINGUARD
```

```text
October.dev spatial feel:                         PASS
Harness stages represented:                       PASS
Red evolution visible:                            PASS
Blue evolution visible:                           PASS
Attack → sandbox → evaluator causality:           PASS
Breach → patch → replay → promotion causality:    PASS (checked in viewmodel.ts; not screenshotted)
Historical vs live distinction:                   FAIL
Atlas live-state visibility:                      PARTIAL
Backend-truth data binding:                       PARTIAL
Demo navigation:                                  PARTIAL
```

The canvas is the real harness. It has windows for Red, attack, sandbox, evaluator, Blue engineer, harness patch, candidate, replay/judge, champion and generation. Every connecting line is built from persisted records (candidate → episodes → patch → child harness → status), not decoration. Sandbox windows show a per-stage pass/fail/skipped trace, and patch windows list the actual operations. The lineage view shows Red mutations with promoted/rejected edges, and Blue champion → patch → candidate → promoted.

## STRANDS HARNESS OPTIMIZER COMPARISON

Source: [Introducing Harness Optimizer](https://strandsagents.com/blog/introducing-harness-optimizer/). In that framework, a Formula is a tunable piece of the harness, a RewardFunction scores rollouts, and a FormulaOptimizer updates the Formula. By default the optimizer is an LLM that compares winning and losing traces ("contrastive reflection").

1. **"The harness itself evolves":** the idea is present but you have to infer it. The only cue is a 10px footer, "TARGET MODEL UNCHANGED".
2. **What changed in the harness:** yes. The patch window shows +/−/~ operations with target → value. The `/harnesses/{a}/diff/{b}` API exists, but the frontend never calls it.
3. **What a judge can inspect:** parent, patch, operations, candidate fitness, block rate, utility, replay battles, PROMOTED/REJECTED with reason, and the champion. Everything is inspectable.
4. **Model evolution vs harness evolution:** not stated. Red evolves its *prompt strategy* while model weights stay frozen; Blue evolves the harness. Nothing on screen says this.
5. **No fine-tuning:** only implied by the footer. Change it to "MODEL WEIGHTS FROZEN · HARNESS EVOLVES".
6. **"Adversarial empirical harness optimization":** yes, that is an accurate description. The mapping to Strands:

   | Strands Harness Optimizer | DarwinGuard |
   |---|---|
   | Formula (tunable harness part) | Harness graph: stages and parameters, not only prompt text |
   | Rollouts | Sandbox episodes |
   | RewardFunction | Deterministic evaluator (security + utility) |
   | Optimizer step (reflection agent reading traces) | Blue engineer reading breach traces → HarnessPatch |
   | Update | Gated: promoted only if replay beats the champion |

   Two real differences: DarwinGuard's training distribution is adversarial and co-evolving (Red generates it) rather than a fixed dataset, and its updates can be rejected.
7. **Terminology to borrow:** "harness", "rollouts", "reward", "optimizer step", "trace-driven reflection", "tunable harness components". Frame it as "the same harness-as-parameters idea, under adversarial pressure, with gated promotion". Don't say or imply that DarwinGuard uses Strands.
8. **Interop under 30 minutes:** a read-only MCP server exposing runs, patches and champions is feasible. It adds nothing to the demo and adds risk, so skip it. No Strands SDK integration is needed.

## FINDINGS

### 1. BLOCKER — three START controls start a fake run and write it into Atlas

- **Area:** frontend data integrity / Atlas
- **Claim:** `▶ START` in the top bar, `▶` in the command bar, and "+ Start new run" in the run list all start a fake run.
- **Evidence:**
  - All three call `api.start` → `/arena/start` → the old `EvolutionLoop`. That uses `FakeAgent` (`/health` reports `agent_provider: fake`) and deterministic mutations, and creates a `RUN-…` id.
  - The Atlas observer is writable (the Mongo repository has no read-only mode), so the fake run would land in `darwinguard` next to the real evidence.
  - The tooltip says "Start a 3-generation co-evolution run", which is untrue.
  - On historical servers the click is safe (409) but shows an error banner.
- **Recommended action:** hide or disable all three controls, with a tooltip saying live runs start from the CLI. Optionally, make `require_writable` refuse `/arena/start` when the agent is `FakeAgent` and the mode isn't TEST.
- **Estimated effort:** 10–15 minutes

### 2. HIGH — nothing in the UI says HISTORICAL / READ ONLY

- **Area:** historical vs live distinction
- **Evidence:**
  - The frontend contains no "HISTORICAL" or "READ ONLY" string, and `/system/status` doesn't expose `read_only`.
  - The top-right pill reads "DEV" on both the historical snapshot and the Atlas observer (both run in `run_mode=DEV`). Only the tiny footer label differs.
  - START looks active on a frozen run.
- **Recommended action:** add `read_only` to `/system/status`. Show a top-bar chip: "HISTORICAL · READ ONLY" or "LIVE · ATLAS CONNECTED". Reword the footer to "MODEL WEIGHTS FROZEN · HARNESS EVOLVES".
- **Estimated effort:** 20 minutes

### 3. HIGH — the demo scripts can show the wrong run

- **Area:** demo commands
- **Evidence:**
  - The historical scripts bind :8000, which the Atlas observer (pid 33804) already holds. Their uvicorn fails quietly (it runs in the background and logs to a file), and the health `curl` then answers from the Atlas observer. The frontend would show the Atlas run instead of Overnight or Two-sided.
  - The scripts run plain `npm run dev`. The report says to use :5175, and :5173 belongs to another project, so Vite silently moves to another port while the scripts print 5173.
- **Recommended action:** in each script, fail fast if :8000 is already listening, and use `npm run dev -- --port 5175 --strictPort`. Or, operationally, stop 33804 before each historical segment.
- **Estimated effort:** 10 minutes

### 4. MEDIUM — the Blue Engineer subtitle names the wrong model

- **Area:** model attribution
- **Evidence:** `frontend/src/lib/viewmodel.ts:435` uses `blueVersions[0].base_model` (the executor, Ling) first. In the Atlas run the subtitle reads Ling while the window body says "engineer: nemotron…". A judge sees a contradiction on exactly the Nemotron claim.
- **Recommended action:** prefer the model of the engineer's successful call, as `BlueContent` already does.
- **Estimated effort:** 5 minutes

### 5. MEDIUM — the first view is awkward

- **Area:** demo navigation
- **Evidence:** initial focus is set before the data loads, so it lands on the G00 Red window, partly hidden behind the run list. Meanwhile the run list highlights G06.
- **Recommended action:** no code change. The presenter presses FIT, or clicks a generation, first.
- **Estimated effort:** none

### 6. MEDIUM — "harness evolves, models don't" is never stated

- **Area:** product story
- **Evidence:** the "TARGET MODEL UNCHANGED" footer is the only cue, and `api.harnessDiff` is unused.
- **Recommended action:** the footer rewording (inside Finding 2) is enough. Leave the diff view for after the demo.
- **Estimated effort:** covered by Finding 2

### 7. LOW — minor record and report inaccuracies

- **Area:** Atlas records and the final report
- **Evidence:**
  - The rejected candidate's Blue version record (`BLUE-…G01-C1`) still says `status=ACTIVE`. That field defaults to ACTIVE and is never updated. The UI doesn't display it, and `/harnesses/active` correctly returns B0.
  - The final report lists a `runs` collection that doesn't exist in Atlas; run state lives in `runtime_state`.
  - The report's "56 events" doesn't match: Atlas now has 68 `arena_events`.
  - HEAD has moved past `01fbba1`.
- **Recommended action:** documentation only; no code.
- **Estimated effort:** none

### 8. LOW — the status endpoint under-reports vector search

- **Area:** Atlas status
- **Evidence:** `/system/status` reports vector search `observed: unverified` on the Atlas observer, even though a direct `$vectorSearch` works.
- **Recommended action:** don't point at that field during the demo.
- **Estimated effort:** none

## REQUIRED CHANGES BEFORE DEMO

1. Disable or hide the three START controls (Finding 1).
2. Add `read_only` to `/system/status`, a HISTORICAL · READ ONLY / LIVE · ATLAS CONNECTED chip in the top bar, and the footer text "MODEL WEIGHTS FROZEN · HARNESS EVOLVES" (Finding 2).
3. Make the demo scripts fail if :8000 is taken, and use `--port 5175 --strictPort` (Finding 3).
4. Use the engineer's model in the Blue Engineer subtitle (Finding 4).

## IDEAL DEMO FLOW

1. Stop the Atlas observer, then run `scripts/demo-overnight.sh --api-only` and `cd frontend && npm run dev -- --port 5175 --strictPort`. Open :5175 and press FIT. State that this run is historical and read-only.
2. Click G00 in the run list. Open the RED AGENT window (model, strategy, fitness).
3. Follow "generated" to a DIRECT OVERRIDE attack window marked BREACH and show the injected content.
4. Follow "execute" to SANDBOX and show the stage trace (Tool permission gate FAIL, 1 executed / 8 proposed).
5. Follow "evidence" to EVALUATOR · BREACH, then "breach" to BLUE ENGINEER (engineer model; fallback not used).
6. Open the HARNESS PATCH window. Show the operations, parent, validation and author (Ling, historical).
7. Open CANDIDATE, then REPLAY / JUDGE. Show fitness, block rate, utility, replay battles and PROMOTED. Then CHAMPION.
8. Click G01–G06: ASR 0.0 while Red keeps mutating. Use the RED EVO button to show promoted and rejected mutations.
9. Switch to LINEAGE to show Red and Blue ancestry side by side.
10. Restart with `scripts/demo-two-sided.sh --api-only`. Show ASR 0 → 0.333 → 0.667 → 0 and the G02 rejections versus the G03 promotion.
11. Restart the Atlas observer. The footer shows ATLAS CONNECTED. Open `DARWINGUARD-EVENT-20260926`: the Nemotron patch, REJECTED on the utility floor.
12. Optionally, run the one-generation command from `FINAL_REPORT_2026-09-26.md` §10C and press ⟳ when it finishes.

## FINAL FREEZE RECOMMENDATION

```text
FIX THESE ITEMS THEN FREEZE
```

The four fixes are all small edits in the frontend, the scripts, and `/system/status`, totalling about 45–60 minutes. Don't touch models, fitness, persistence or evidence. After the fixes, re-run `tsc`/build and pytest, then freeze.
