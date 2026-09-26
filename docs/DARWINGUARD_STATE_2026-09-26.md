# DarwinGuard — Current State & Improvement Roadmap

**Date:** 2026-09-26 · **HEAD:** `64732c3` · **Audit type:** read-only (no code changed, no commits, no historical evidence modified)

This document is the team-shareable synthesis of a full system audit run on 2026-09-26.
One orchestrator plus four workers (all OpenCode on DeepSeek Flash, coordinated through
October Bus) independently inspected the repository, the runtime, the frontend, and the
persisted experiments. The independent verifier cross-checked the other three workers'
claims against code, tests, and persisted records.

Everything below is stated with its evidence. Where a claim is unproven, it says so.

---

## TL;DR

- **The core claim is real.** Red and Blue genuinely co-evolve on real models, decisions are
  measured and persisted, and there is a complete real breach → patch → promotion cycle in
  the overnight run. This is not a mock.
- **The demo has three showstoppers, all operational, none of them the science:**
  1. The observer UI's Start button writes a new run into the snapshot the server was
     booted with; the Reset endpoint wipes the snapshot entirely. Do not click them on an
     evidence snapshot.
  2. The backend is not running, and the default snapshot (`backend/.dev-state.json`) has
     no co-evolution evidence — the demo must be booted with the overnight or COEV-SEL
     snapshot explicitly.
  3. The overnight run's exported "RUN REPORT" is a stale phase-A checkpoint (3 generations,
     102 calls) while the actual run has 7 generations and 256 calls. The UI shows both.
- **The biggest unproven item** is the current Blue engineer model (Nemotron): it is wired
  in config but no persisted run has ever used it. All real Blue patches to date were
  authored by Ling.

---

## What DarwinGuard is

Two AI agents fight and adapt inside one loop:

- **Red** is the attacker. It generates attacks (prompt injections and tool-output
  manipulation) against the system's security harness.
- **Blue** is the defender. Its executor answers tool calls under the harness; its engineer
  reads the failures and writes a **HarnessPatch** — a small set of changes to the rules
  that decide which tool calls are allowed.
- A **sandbox** runs each attack scenario deterministically; an **evaluator** scores what
  actually happened. **ASR** (attack success rate) is how often attacks get through.
- After every round, Red mutations are promoted or rejected based on measured fitness, and
  Blue patches are compiled, replayed against a fixed battery, and promoted only if they
  beat the current champion. The promoted champions feed the next generation.

Everything runs against real models and every decision is written to a persisted snapshot
(JSON), so a run can be reloaded, inspected, and resumed.

---

## Verified runtime configuration (live probes, 2026-09-26)

| Thing | Current value | Verified how |
|---|---|---|
| Red model | `qwen3.8-flash-next-heretic2` @ `http://ai-rig.tail6d5242.ts.net:11500/v1` | Tailscale peer Online (100.116.103.79); `/v1/models` lists it; readiness chat "READY" in 1121 ms |
| Red origin guard | fail-closed (`runtime.py:26-61`, enforced at `runtime.py:221-256`) | rejects non-rig endpoints; passed live; proven by a real fail-closed incident in the overnight run log |
| Reasoning-token fix | active at HEAD (`providers.py:523-560`) | 7/7 `test_provider_reasoning.py`; live escalation confirmed during the Red bake-off |
| Blue executor | `inclusionai/ling-3.0-flash-fin:free` (OpenRouter) | endpoint reachable; 142 persisted executor calls in the overnight run |
| Blue engineer primary | `nvidia/nemotron-3-super-120b-a12b:free` | present in OpenRouter catalogue; wired at `runtime.py:186-194` — **no production run has used it** |
| Blue engineer fallback | `inclusionai/ling-3.0-flash-fin:free`, `json_mode=never` | all real patches so far were authored by Ling |
| Persistence | DEV durable snapshot (JSON file) | run banners say "DEV / ATLAS NOT CONNECTED (durable snapshot)"; `MONGODB_URI` empty everywhere |
| MongoDB Atlas | absent | no URI in config or `.env`; never exercised; strict fail-closed guards exist but are untested |
| Frontend | typecheck + build green | `tsc -b` exit 0; build 418.40 kB / 130.36 kB gzip |

---

## System status

Vocabulary: **WORKING** = proven with live or persisted evidence · **PARTIAL** = works with a named gap · **BROKEN** = fails as specified · **NOT TESTED** = no evidence either way.

| System | Status | Evidence | Remaining work |
|---|---|---|---|
| Repository | WORKING | HEAD `64732c3`; worktree only had `.gitignore` + the audit spec untracked | decide what to commit |
| Tests | WORKING | pytest 201 passed; mypy 77 files clean; ruff clean on `app` + `tests` | ruff: 25 errors + 52 unformatted files in `experiments/` + `scripts/` |
| Red provider | WORKING | live rig probe above; 110 Red calls persisted | — |
| Reasoning-token handling | WORKING | fix + 7 tests + live confirmation | — |
| Red empirical evolution | WORKING | 23 persisted decisions (11 promoted / 12 rejected); `red_selection.py:120-179` | after ASR hits 0, selection is novelty-dominated (small margins) |
| Sandbox | WORKING | deterministic execution, `runner.py:122-160`; block reasons persisted | — |
| Evaluator | WORKING | episode-level results; fitness = 0.7·success + 0.3·novelty verified on 57 candidates | — |
| Blue executor | WORKING | 142 persisted calls; real tool-call decisions | — |
| Blue engineer | PARTIAL | current primary (Nemotron) is config-only; Ling fallback proven | one real run on the current config |
| HarnessPatch lifecycle | WORKING | PROPOSED → VALIDATED → COMPILED → DEPLOYED_FOR_EVAL recorded | — |
| Candidate compilation | WORKING | compiled children; same attack denied after patch | — |
| Replay / regression | WORKING | 10-battle batteries with per-slice metrics | — |
| Blue promotion | WORKING | C1 promoted (0.702 vs 0.698), deterministic policy `blue_search.py:84-112` | every run promotes exactly one patch; search only starts after a breach |
| Next-generation inheritance | WORKING | champion re-read each generation (`engine.py:332,716-722`); 113/139 episodes ran against C1 | — |
| Persistence | PARTIAL | DEV snapshot only, labelled in every report | Atlas has no URI; not in the evidence chain |
| Historical run loading | WORKING | both runs load GET-only; file hashes unchanged after loading | no snapshot picker in the UI; the boot-time snapshot decides what you see |
| Resume / recovery | PARTIAL | survived 5 process aborts; counters reconciled; orphan settling works | generation-boundary label duplication; patch-id overwrite on re-run; one stranded candidate |
| Observer read-only safety | **BROKEN** | `api/arena.py:18-31` → `evolution/loop.py:66-92` writes on Start; `repository.py:452-470` Reset wipes; endpoints unauthenticated | read-only guard and/or dedicated live snapshot |
| Frontend | WORKING | build green; all displayed values come from persisted records | two benign inferred labels (`Inspector.tsx:479-483, 622`); counter/report reconciliation |
| October Bus | WORKING | this audit: 4/4 workers spawned, tasked, reported | canvas renames don't change bus routing; use node IDs (see Appendix) |
| AI rig | WORKING | reachable, model present, calls persisted | — |
| Demo launch path | PARTIAL | frontend dev server up on `[::1]:5175`; no backend on `:8000`; default snapshot has no evidence | boot recipe below; fix P0 items 1–3 |

---

## What is done (evidence-backed only)

- Real co-evolution loop end to end, with persistence, resume, and counter reconciliation.
- Red empirical selection: every mutation promoted or rejected by measured fitness, never by
  model opinion; lineages carry parent/child links.
- Blue breach → patch → compile → replay → deterministic promotion, producing a real
  runtime difference: the attack that breached baseline B0 was blocked by C1 at the tool
  permission gate.
- Reasoning-token fix: reasoning-only model outputs are detected and retried with a larger
  budget (3 calls worst case instead of 9), then fail closed; live-confirmed.
- REAL origin guard refuses non-rig Red endpoints; provider failures never fabricate results.
- 201 backend tests, strict mypy clean, lint clean on app + tests; frontend typecheck and
  production build green.
- Both target historical runs load read-only without changing their files; the UI reads
  champions, ASR, decisions, attribution, and lineage from persisted data.
- Incident durability: the overnight run survived five process aborts with no evidence loss.
- Multi-agent coordination through October Bus proven (Appendix).

---

## What remains, in priority order

### P0 — could break or embarrass the demo

1. **Observer write hazard (still present, now with the full picture).**
   `POST /arena/start` runs the *deterministic* evolution loop and writes a new run into
   whatever repository the server booted with; `POST /arena/reset` wipes every collection
   in it; neither endpoint is guarded or authenticated. Extra finding: because Start runs
   the deterministic loop, an observation server **cannot show real co-evolution at all** —
   live co-evolution only happens through the `python -m app.coevolution` CLI.
   *Direction:* make snapshot-backed servers read-only, keep a separate writable live
   snapshot for any live demo, add a test that clicking Start cannot mutate an evidence
   snapshot; protect Reset.

2. **Demo launch path is not ready.**
   No backend is listening on `:8000`. The default snapshot `backend/.dev-state.json`
   contains one old generation, zero run reports, zero patch records — it shows nothing.
   *Direction:* boot the observer with an evidence snapshot (below) and add a snapshot
   picker so switching runs doesn't require a restart.

3. **The overnight run report is stale.**
   `exports/run_report_OVERNIGHT….json` is a mid-run checkpoint: 3 generations, 102 calls.
   The snapshot has 7 generations and 256 calls. The UI shows both (rail: 256 calls;
   report window: 102) without reconciliation.
   *Direction:* regenerate the report from the snapshot (the run folder already has
   `finalize.py`, `generation_table.csv`, `evidence.json`) or label the checkpoint clearly
   in the UI.

### P1 — important, demo can survive

4. **Nemotron engineer path has zero production evidence.**
   Current config says primary Nemotron, fallback Ling. Every persisted engineer call is
   Ling; the overnight run even hit the OpenRouter 400 "structured-outputs" error twice on
   the old path that today's fallback exists to avoid. *Direction:* one small REAL run on
   current HEAD to prove the exact shipping configuration.

5. **Historical-champion generalization is cold, not missing.**
   The comparison code exists and has an end-to-end test, but it is cold in production
   because every run so far promoted exactly one Blue champion in a run, and the sample
   pool excludes the current champion. Blue is also breach-reactive: no breach, no patch,
   so quiet generations do nothing on the Blue side.
   *Direction:* decide whether to accept this or engineer a two-promotion run to produce
   real historical comparison rows.

6. **Resume duplication and one stranded candidate.**
   After a crash inside a generation boundary, that boundary is replayed whole — the
   overnight run's G05 ended with four decisions instead of three. A crashed Blue search
   can overwrite same-index patch ids. One candidate,
   `R-…-G08-cc4699b5`, is ACTIVE with no evaluation (a resume would evaluate it first).
   *Direction:* dedupe boundary re-entry, make patch ids unique per attempt, settle the
   stranded candidate before any live resume.

### P2 — post-demo improvements

7. **Repo hygiene:** fix the 25 ruff errors in `experiments/` and `scripts/`, and decide
   whether to enforce formatting (52 files in `app`/`tests` would be reformatted).
8. **UI polish:** snapshot picker; reconcile run-report counters with snapshot totals;
   make `/model-calls` require an explicit `run_id` (without it, it spans runs).
9. **Label the utility numbers:** there are three different utility measures in evidence
   (0.667 = 3-task benign suite, 0.5 = candidate promotion battery, 0.333 = C1's last full
   battery). They are not comparable; the UI should say which is which.

---

## Next 3 actions

1. **Make the demo safe:** boot the observer on a dedicated live snapshot and add a
   read-only guard (or hard lock) so evidence snapshots can never be written or reset.
2. **Prepare the demo:** point `DEV_STATE_PATH` at the overnight or COEV-SEL snapshot,
   start the backend, and regenerate the overnight run report from the snapshot so the UI
   stops showing the stale 3-generation checkpoint.
3. **Prove the shipping config:** run one small REAL generation on current HEAD (Nemotron
   engineer + reasoning fix, few Red versions) to confirm breach → patch → promotion and
   settle the stranded G08 candidate.

---

## How to verify and run (exact commands used in this audit)

Backend, from `backend/` (the audit used `uv run`; the README uses `python -m`):

```bash
uv run pytest -q                     # 201 passed, 1 warning
uv run mypy app                      # clean, 77 files
uv run ruff check app tests          # clean
uv run ruff check .                  # 25 errors, all in experiments/ and scripts/
```

Frontend, from `frontend/`:

```bash
npx tsc -b                           # exit 0
npm run build                        # exit 0, 418.40 kB / 130.36 kB gzip
```

Observer API (needs an explicit snapshot; without this it serves the evidence-less default):

```bash
DEV_STATE_PATH=experiments/OVERNIGHT-COEV-20260926-022643/state.json \
  uvicorn app.main:app --port 8000
```

Read-only sanity check that loading an evidence run does not rewrite it:

```bash
shasum -a 256 backend/experiments/OVERNIGHT-COEV-20260926-022643/state.json
# load the UI, then run the same command again — hashes must match
```

The exact co-evolution CLI invocation for the overnight run is recorded in
`docs/OVERNIGHT_COEV_VERDICT_2026-09-26.md`.

---

## Evidence index

Reports (all in `docs/`):

| File | What it establishes |
|---|---|
| `CURRENT_DEMO_STATE_2026-09-26.md` | Latest current-state reconciliation, written at the venue |
| `OVERNIGHT_COEV_VERDICT_2026-09-26.md` | The overnight run's authoritative record (7 generations) |
| `VENUE_AUDIT_2026-09-26.md` | October Bus, reasoning fix, Red bake-off, demo readiness |
| `COEVOLUTION_ACCEPTANCE_2026-09-26.md` | Red selection acceptance (note: its "189 passed" is stale) |
| `BLUE_BAKEOFF_2026-09-26.md` | Why Nemotron is primary and Ling the fallback |
| `HISTORICAL_CHAMPION_SAMPLING.md` | Historical-champion arm verdict (closed with a test) |
| `REALITY_AUDIT.md`, `RED_PROVIDER_AUDIT.md`, `ATLAS_PERSISTENCE.md` | Dated audits — accurate for their dates, partially superseded |

Persisted runs:

- `backend/experiments/OVERNIGHT-COEV-20260926-022643/` — `state.json` (authoritative:
  7 generations, 256 calls, 139 episodes, 2 patches), `summary.json`, `evidence.json`,
  journal, `generation_table.csv`.
- `backend/.dev-state-coevo-20260926-011123.json` — COEV-SEL (4 generations; shows Red
  breaching again after Blue held).
- `backend/exports/run_report_REAL-ACCEPT-2.json` — real breach → patch → promotion.
- `backend/experiments/red-bakeoff/results.json` — the Red model bake-off data.

Code map (where the real logic lives):

- `backend/app/coevolution/engine.py` — the loop, resume, settling, generation records.
- `backend/app/coevolution/red_selection.py` — empirical Red promotion/rejection.
- `backend/app/coevolution/blue_search.py` — candidate search, battery replay, selection.
- `backend/app/coevolution/champions.py` — champion judging and historical sampling.
- `backend/app/coevolution/providers.py` — Red/Blue model clients, reasoning-token fix.
- `backend/app/coevolution/runtime.py` — config, origin guard, engineer provider order.
- `backend/app/harness/`, `backend/app/sandbox/`, `backend/app/arena/` — compile, execute,
  score.
- `backend/app/api/arena.py`, `backend/app/evolution/loop.py` — the observer Start/Reset
  path (the hazard).
- `backend/app/memory/repository.py` — snapshot read/write/reset.
- `frontend/src/...` — `useRunData.ts`, `viewmodel.ts`, `Inspector.tsx` for data loading
  and the two inferred labels.

---

## Warnings: don't get fooled by these

1. **Quote the snapshot, not the exported report, for overnight totals.** The report is a
   phase-A checkpoint (3/102); the snapshot is 7 generations / 256 calls. Anything citing
   102 understates the run.
2. **The overnight run's "6 breaches" is not 6 generation breaches.** Four of the six are
   mutation-evaluation episodes against the *already-replaced* B0; only 2 are generation-0
   attacks. (`finalize.py:138` counts any attack success.)
3. **Overnight Blue patches were authored by Ling, not Nemotron.** The Nemotron switch
   landed after the run. "Current config is Nemotron" is true; "Nemotron produced those
   patches" is false.
4. **Utility numbers are not comparable across sources** (see P2-9).
5. **Candidate-level fitness is not refreshed on replay.** A candidate keeps the fitness it
   measured against the champion of its day (e.g. a Hall-of-Fame Red entry with fitness 1.0
   measured against B0, though it later held against C1). Cite version fitness and ASR.
6. **The Start button is not co-evolution.** The API's Start runs a deterministic loop; the
   real engine is only reachable through the CLI. Don't demo "live co-evolution" from the
   observer.
7. **REAL-ACCEPT-2 predates the selection rework.** Its Red versions are all ACTIVE with no
   measured fitness; treat its Red-selection claims as lineage-only.
8. **Historical sampling is cold, not missing.** It has an end-to-end test; it never runs
   in production because no run has promoted two Blue champions.
9. **Atlas is absent from the chain, not merely untested.** No URI, no run ever used it.

---

## Appendix — how this audit was produced (multi-agent test)

This audit doubled as a swarm test: one OpenCode orchestrator (`Apollo`,
`deepseek/deepseek-flash`) spawned four OpenCode workers over October Bus, all on the same
DeepSeek Flash model.

- Spawned 4/4 · correct provider 4/4 · correct model 4/4
- Correlated liveness replies 4/4 (`BUS_READY`)
- Board tasks claimed 4/4 · completed 4/4
- Reports delivered over the Bus by all four; the independent verifier then challenged the
  other reports' claims and resolved one discrepancy (overnight call count: 256, where the
  255th-vs-256th question turned out to be the 29th mutator call, `CALL-592f38e7…`,
  09:09:24Z, the last inference before the volume incident).

Operational quirks worth knowing for next time:

- The live `add_terminal` tool rejects `model` and `cwd` arguments; workers inherit the
  orchestrator's workspace and model.
- Renaming a canvas node does not change Bus routing — address workers by node ID
  (`send_to_node`), not display name.
- Terminal restarts (for auto-approve) interrupted two workers mid-task; their board claims
  survived and re-kicking resumed them cleanly.

No Claude, Codex, Kiro, GPT, or Gemini was used, and no code, commit, or historical
evidence was touched during the audit.
