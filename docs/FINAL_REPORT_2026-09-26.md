# DarwinGuard — Final Hardening + Atlas Sprint Report

**Date:** 2026-09-26 · **HEAD:** `01fbba1` · **Verdict:** READY FOR JUDGES (see §12 for operational notes)

This is the authoritative close-out report for the 5-hour hardening + MongoDB Atlas sprint.
Five OpenCode + DeepSeek Flash workers (observer-safety, demo-evidence, atlas-migration,
shipping-smoke, verifier) ran under Apollo (orchestrator) through October Bus; the
independent verifier reproduced every claim with raw evidence. No historical evidence was
modified; no secrets were committed.

---

## 1. TOPOLOGY

```text
Canvas nodes:            8 (7 terminals + 1 browser)
Healthy terminals:       6 (Apollo + 5 workers; all OpenCode + DeepSeek Flash)
Stale terminals:         3 (guard-backend/runtime-proof/demo-path — stopped and replaced; removed from canvas)
Disconnected terminals:  1 (kiro-review — agent never started; review skipped)
OpenCode workers:        5
Provider/model:          deepseek / deepseek/deepseek-flash (all verified via BUS_READY)
Active kernels/execs:    0 (no co-evolution process running)
Orphaned claims:         2 (t-c1aad7ba, t-a1701374 on removed terminals; superseded by new tasks)
October Bus:             connected — tasks, claims, peer messaging, node-ID routing all used
Kiro:                    CLI present; review attempt queued, agent offline → skipped (doc time-box rule)
```

| Node | Terminal | Role | Model | Status | Task |
|---|---|---|---|---|---|
| Apollo | term-muik9q4k-0 | Orchestrator | deepseek-flash | working | integrator/commits |
| observer-safety | term-muiln1ij-14 | Worker A | deepseek-flash | idle/done | t-826813d5 done |
| demo-evidence | term-muiln1u2-16 | Worker B | deepseek-flash | idle/done | t-497b9ea6 done |
| atlas-migration | term-muiljcgc-x | Worker C | deepseek-flash | idle/done | t-d8125838 done |
| shipping-smoke | term-muiln21e-18 | Worker D | deepseek-flash | idle/done | t-5593c0d8 done |
| verifier | term-muin24ry-1u | Worker E | deepseek-flash | idle/done | t-f1c1ad32 done |
| kiro-review | term-muinfudj-23 | Kiro | — | offline | skipped |

## 2. SWARM EXECUTION

| Worker | Spawn/reuse | Bus | Claimed | Completed | Result |
|---|---|---|---|---|---|
| A observer-safety | reused (after replacing a stuck terminal) | OK | yes | yes | guard + 4 tests, suite green |
| B demo-evidence | reused (after replacing a stuck terminal) | OK | yes | yes | rebuilt report, runbook, 3 launch scripts, UI labels |
| C atlas-migration | fresh spawn | OK | yes | yes | Atlas verified incl. vector search + readback |
| D shipping-smoke | reused (after replacing a stuck terminal) | OK | yes | yes | real Nemotron smoke, promotion |
| E verifier | fresh spawn (replaced a stuck verifier) | OK | yes | yes | matrix A–H all PASS with raw evidence |

Operator notes: three reopened terminals were unresponsive (messages queued "mid-task"
indefinitely); they were stopped and replaced. October canvas renames do not change Bus
routing — node IDs were used throughout. All five workers self-verified as
`deepseek/deepseek-flash` before assignment.

## 3. OBSERVER SAFETY

```text
Historical Start blocked:    YES (409 READ_ONLY_SNAPSHOT)
Historical Reset blocked:    YES (409 READ_ONLY_SNAPSHOT)
Historical state unchanged:  YES (sha256 10373cb9… before=after; /replay and /replay/compare also 409)
Live state writable:         YES (ALLOW_SNAPSHOT_WRITES=true on a dedicated snapshot; CLI writable)
```

## 4. ATLAS

```text
Atlas connected:          YES — label "ATLAS CONNECTED" (backend=mongodb, atlas_connected=true)
Database:                 darwinguard
Collections:              runs, generations, red_agent_versions, blue_agent_versions, attacks, defenses,
                          episodes, attack_candidates, harnesses, harness_patches, harness_diffs,
                          model_calls, hall_of_fame, run_reports, memories, arena_events, scenarios
Required indexes:         normal indexes verified; 2 vector indexes READY (attack_embedding_index, memory_embedding_index)
Vector Search:            VERIFIED — real 1536-dim embedding + $vectorSearch returned 2 rows (scores 0.6476, 0.5596)
Live write:               YES — DARWINGUARD-EVENT-20260926 (1 gen, 21 calls, 56 events, 1 patch, report)
Fresh-process readback:   PASS — new interpreter reconstructed run/generations/lineages/champions/events/calls/report
Resume/reconstruct:       PASS
Silent fallback disabled: YES — REAL+atlas with no URI → PERSISTENCE_UNAVAILABLE exit 2; unreachable URI → exit 2
```

## 5. OVERNIGHT EVIDENCE

```text
Run:                       OVERNIGHT-COEV-20260926-022643
Generations:               7 (G00–G06)
Model calls:               256 (81 attacker / 29 mutator / 142 executor / 4 engineer)
Report reconciled:         derived FINAL = 7 gens / 256 calls; phase-A export (3/102) kept and labelled PHASE-A CHECKPOINT
UI reconciled:             YES — derived snapshot served; original snapshot labels the checkpoint explicitly
Historical file unchanged: sha256 10373cb9… (state), 39a5ef64… (phase-A export)
```

## 6. TWO-SIDED RUN

```text
Loads:                     YES — COEV-SEL-20260926-011123 (4 gens / 132 calls)
Lineage correct:           Red champion R-…-G02-6992fd0c; Blue champion B-…-G03-C1
ASR progression:           [0.0, 0.333, 0.667, 0.0]
Blue response:             G01-boundary patches rejected on utility floor; PATCH-G03-1 promoted (fit 0.683/11 battles) → holds
Historical file unchanged: f7d01684… before=after
```

## 7. SHIPPING CONFIG

```text
Red:                             qwen3.8-flash-next-heretic2 @ ai-rig (REAL, origin guard passed)
Blue executor:                   inclusionai/ling-3.0-flash-fin:free
Blue engineer configured:        nvidia/nemotron-3-super-120b-a12b:free (fallback Ling)
Blue engineer actually exercised: Nemotron — VENUE-SHIPPING-SMOKE patch (1 call, 15.1s) and Atlas run patch
Fallback:                        NOT used in either real run
Patch/Compile/Replay:            smoke: 1 op SET_PARAMETER → C1 compiled 8 nodes → 9-battle replay block 1.0
Decision:                        smoke PROMOTED fitness 0.7202; Atlas run candidate REJECTED on utility floor
Persistence backend:             smoke = dedicated JSON snapshot; Atlas run = MongoDB Atlas (ATLAS CONNECTED)
```

## 8. TESTS

```text
pytest:          206 passed, 1 skipped (live-gated)
mypy:            Success, 77 files
ruff:            All checks passed (app + tests)
frontend tsc:    exit 0
frontend build:  exit 0 (419.64 kB / 130.75 kB gzip)
```

## 9. SOURCE CONTROL

```text
HEAD:              01fbba1
commits:           a62ecde fix: protect historical observer snapshots
                   d5d9c4d feat: enable Atlas persistence for event live runs
                   1909092 demo: reconcile persisted run evidence and launch flow
                   e4554ed test: record venue shipping smoke and Atlas event run evidence
                   01fbba1 docs: hardening sprint spec and current-state synthesis
working tree:      clean except untracked backend/experiments/DEMO-LIVE-PROOF-20260926/ (abandoned run from an earlier prompt; not referenced)
historical evidence modified: NO
secrets committed: NO (.env ignored; credential scan clean on every staged wave)
```

## 10. EXACT DEMO COMMANDS

**A. Overnight historical demo**

```bash
scripts/demo-overnight.sh            # serves derived 7/256 evidence on :8000; starts frontend too
# or API only:  scripts/demo-overnight.sh --api-only
```

**B. Two-sided historical demo**

```bash
scripts/demo-two-sided.sh            # 4 gens / 132 calls, ASR 0.0→0.333→0.667→0.0
```

**C. Fresh Atlas-backed live demo** (observer is already running on :8000, pid 33804)

```bash
# observer (Atlas, already up):
# cd backend && RUN_MODE=DEV .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# one short REAL generation persisted to Atlas:
cd backend && RUN_MODE=REAL PERSISTENCE=atlas .venv/bin/python -u -m app.coevolution \
  --mode real --generations 1 --red-versions 1 --attacks-per-version 1 \
  --red-eval-attacks 1 --blue-candidates 1 --baseline naked \
  --run-id DARWINGUARD-EVENT-$(date +%H%M%S)
```

**D. AI-rig readiness**

```bash
tailscale ping ai-rig
curl -s http://ai-rig.tail6d5242.ts.net:11500/v1/models | head -c 300
```

**E. Frontend** — port note: `:5173` is occupied by an unrelated project on this machine;
DarwinGuard's frontend is running on `:5175`.

```bash
cd frontend && npm run dev -- --port 5175 --strictPort
```

`scripts/demo-live.sh` remains the JSON-snapshot live variant; for the Atlas-backed live
segment use the commands in C.

## 11. JUDGE STORY (60–90 seconds)

Red is an attacker model on a local GPU rig. It writes prompt-injection and tool-output
attacks against a security harness, one scenario at a time. Blue is the defender: a fast
executor model answers tool calls under the harness, and an engineer model reads the
failures and writes a small HarnessPatch — a change to the rules that decide which tool
calls are allowed. Every attack is executed in a deterministic sandbox and scored: an
attack either gets through or is blocked, and the harness is measured on security and on
task utility. Red mutations are promoted or rejected by child-versus-parent measured
fitness; Blue patches are compiled, replayed against a fixed battery, and promoted only if
they beat the current champion. That is why this is evolution, not two chatbots talking:
every decision is a measured comparison persisted with its evidence, and the losing
candidates are kept as rejections. The overnight run shows the full loop: two real breaches
against the baseline, a Blue patch promoted, then six generations where the patch holds
every attack while Red keeps mutating and mostly losing. The two-sided run shows both sides
adapting — Red breaks through, Blue answers. Atlas persists the live runs — runs,
generations, lineages, episodes, model calls, patch decisions, champion pointers — and a
fresh process can rebuild the run state from the database. The persisted snapshots prove
the history; Atlas proves the live path.

## 12. FINAL VERDICT

**READY FOR JUDGES.**

Operational notes (not blockers):

1. Frontend runs on `:5175` because `:5173` is held by another project on this machine.
2. The Atlas live run writes to the event namespace via the exact command in §10C;
   historical demos never touch Atlas (scripts pin `MONGODB_URI=`).
3. The stray `backend/experiments/DEMO-LIVE-PROOF-20260926/` untracked folder can be
   deleted at will — it is an abandoned run from an earlier prompt and is not referenced.
