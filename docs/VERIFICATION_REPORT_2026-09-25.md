# DarwinGuard / HackMongo — Independent Verification Report

- **Date:** 2026-09-25
- **Verifier:** OpenCode / Orion (single verifier pass)
- **Repository:** `/Volumes/Auxilary/Side_Projects/HackMongo`
- **Branch/HEAD at audit:** `main` @ `9b1e335` (working tree clean)
- **Method:** repository inspection (git log/status/diffs/file introductions), task-board notes, agent activity journals, targeted and full test execution, `RUN_MODE=REAL` runtime audit, read-only MongoDB inspection. Agent summaries were not trusted where a repository artifact could confirm or contradict them.

---

## AGENT STATUS

| Agent | Task | What it changed | Integrated? | Working? | Problems |
|---|---|---|---|---|---|
| **Apollo** | RED-01 (`t-64577d39`): real Red provider path + fail-closed audit | `providers.py`: bounded retry/backoff, empty-completion retry with `max_tokens` escalation, `PROVIDER_TIMEOUT_SECONDS` override; `scripts/audit_red_provider.py`, `scripts/verify_red_acceptance.py`; `docs/RED_PROVIDER_AUDIT.md` | Yes — `c8e97ac` + `d27e80e` (providers +411) | Yes — retry/escalation/timeout tests exist and pass (`test_provider_failclosed.py`, 30+ cases); `audit_runtime` REAL exits 0 | Acceptance was against Mac Ollama because ai-rig was offline at the time; ai-rig is now online and was used by the real run. `.env.example` still says `thinkingmachines/inkling:free` (stale vs the intended Ling model in `.env`). Removed `ab_causality_proof.py` — confirmed absent |
| **Atlas** | RUNTIME-01 (`t-3136baeb`): executable compiler/runtime + verification | `harness/compiler.py`: stage table, duplicate-stage-id and anchor-collision guards, execution-ordered graph, GRAY_BOX `disclosure`/`node_id`; pinned runtime tests; verification checklists (no files) | Yes — graph hardening `c8e97ac`, disclosure `d27e80e`; `test_harness_runtime.py` (10 tests) | Yes — 10/10 runtime tests pass; its DEF-ACCEPT-1 promotion checklist (C1 0.7115 vs B0 0.4209) reproduces | Flagged two real residuals, both reproduced here: orphan `C2` (compiled, 1 episode, no metrics, harness left `ACTIVE`) and `final_red_champion` tie-break with all-red fitness `None` |
| **Helios** | `t-c81c815c`: historical-champion arm end-to-end; `t-ef575bb0` doc follow-up | `tests/test_coevolution.py::test_two_same_run_promotions_produce_a_historical_comparison_end_to_end`; `docs/HISTORICAL_CHAMPION_SAMPLING.md` (CLOSED) | Was **uncommitted** at handoff; committed in `b907748`/`8b13a2f`. Now integrated | Yes — test passes in suite (4 selected pass) | Claimed a "PROMO-ACCEPT-1 relaunch" that **never happened** (no run report exists; Hades/Atlas corrected it; DEF-ACCEPT-1 was the only run). Patch-count overcount anomaly around their report was real (see Repository Status) |
| **Hades** | AUDIT-01 (`t-43dbbe4e`): reality audit | `docs/REALITY_AUDIT.md` (369 lines, docs-only) | Yes — `d27e80e` | Content accurate for its date; classifications and residuals verified | Now **partially stale**: "no Blue promotion" is superseded by REAL-ACCEPT-2; "Mongo/Atlas unexercised" is half-true — local Mongo *was* exercised (`darwinguard_final` exists), Atlas proper still isn't |

**Current lane (OpenCode/Orion, not one of the four):** `b907748` (checkpoint of Helios artifacts + DEF-ACCEPT-1), `8b13a2f` (Blue engineer sees the benign regression suite; benign forbidden/required conflict fixed; +2 tests), `9b1e335` (REAL-ACCEPT-2 evidence).

---

## REPOSITORY STATUS

- **Branch/HEAD:** `main` @ `9b1e335`; working tree **clean**; single worktree; **no unmerged branches, no conflicts**.
- **Agent integration:** all four agents worked in the *same checkout*; their changes were squashed by October into `c8e97ac` and `d27e80e` ("Update from October", authored by Haadesx). Per-agent commit provenance is not preserved — attribution relies on task notes plus file-level inspection. Only the final Helios artifacts survived uncommitted (now committed).
- **Key commits:**
  - `de45f67` — initial executable harness runtime
  - `c8e97ac` — bulk import + Atlas compiler hardening + provider fail-closed tests
  - `d27e80e` — integration commit (provider retry work, audits, DEF/RED run exports)
  - `b907748` — Helios checkpoint (verdict doc + DEF-ACCEPT-1 artifacts)
  - `8b13a2f` — engine fixes (regression context for Blue, benign forbidden/required conflict)
  - `9b1e335` — REAL-ACCEPT-2 evidence
- **Duplicates/dead code:** none found. `mongo_probe_a.py` deleted; `ab_causality_proof.py` gone (it had been wiping `darwinguard_final`).
- **Confirmed anomaly:** DEF-ACCEPT-1 report/state say `patches=3, compiled=3, blue_versions=3`, but the repository holds **2 patches, 2 blue versions**, with C2 stranded mid-battery. REAL-ACCEPT-2's report and state agree exactly (3/3/1).

---

## SYSTEM STATUS

| Component | Status | Evidence |
|---|---|---|
| Red generation | WORKING | REAL-ACCEPT-2: 7 attacker + 6 mutator calls to ai-rig `qwen3.8-flash-next-heretic2`; 6 candidates persisted |
| Attack parsing | WORKING | Every candidate has `model_call_id`; contract test passes |
| Sandbox execution | WORKING | Episodes carry executed calls + snapshots; runner tests pass |
| Deterministic evaluation | WORKING | `DeterministicEvaluator` tests; REJECT decisions carry measured reasons |
| Blue model call | WORKING | 49 executor + 7 engineer calls to `inclusionai/ling-3.0-flash-fin:free` |
| HarnessPatch generation/validation | WORKING | 3 patches in REAL-ACCEPT-2; invalid ops repaired/rejected fail-closed |
| Candidate harness creation | WORKING | 3 compiled; graph diffs persisted |
| Replay / regression | WORKING | C1 battery: 9 battles, block 1.0, utility 0.667; benign fix verified |
| Promotion / rejection | WORKING | 1 promoted (fitness 0.760), 2 rejected (utility floor 0.444; lost on fitness) |
| Next-generation continuity | WORKING | gen1/gen2 champion + active = C1; same breach attack replayed blocked |
| Persistence (DEV snapshot) | WORKING | State file round-trips; `audit_runtime` reads counters |
| Persistence (local MongoDB) | WORKING | Read-only check: `darwinguard_final` etc. with consistent collections (39 calls, 2 patches, 2 harnesses) |
| Persistence (Atlas) | NOT TESTED | No `MONGODB_URI` in current config; all real runs are labelled DEV |
| REAL-mode / AI-rig | WORKING | `RUN_MODE=REAL python -m app.audit_runtime` exit 0; ai-rig online; Tailnet origin guard passed |
| Historical champion A/B | PARTIAL | Deterministic test passes; never fires in a real run (only 1 promotion per run) |
| Run-report counter integrity | BROKEN (interrupted runs only) | DEF overcount +1 vs persisted records; stranded ACTIVE C2 |
| Frontend | NOT TESTED | No changes by these agents; Hades classified EVOLVE workbench UI-ONLY |

---

## END-TO-END STATUS

```
Red → sandbox → evaluator → Blue → patch → candidate → replay → promotion → next generation
```

**Fully succeeds with real models** (REAL-ACCEPT-2): gen0 breach (ASR 0.5) → Ling patch → C1 promoted → gen1/gen2 attack C1 and get ASR 0.0.

It does **not** stop on the core path. It stops at:
- Atlas persistence (DEV snapshot labelled, no credentials), and
- Blue is never re-consulted after the promotion because the defense held (no new breach).

---

## TEST RESULTS

| Check | Result |
|---|---|
| Full backend suite (`pytest -q`) | **167 passed**, 1 warning (2.80s) |
| `test_harness_runtime.py` + `test_provider_failclosed.py` + `test_blue_search.py` | **80 passed** |
| Historical / benign / engineer-sees selection | **4 passed**, 50 deselected |
| Contract / causality selection | **2 passed**, 52 deselected |
| `ruff check app tests` | clean |
| `mypy app` | clean, 76 source files |
| `RUN_MODE=REAL python -m app.audit_runtime` | **exit 0** — RED/BLUE `REAL`, models named, origin guard passed |
| Local MongoDB (read-only) | `darwinguard_final`: harnesses 2, harness_patches 2, model_calls 39, run_reports 1 (plus 3 further DarwinGuard DBs) |
| Not run | Atlas, frontend build, new real-model experiment |

---

## BIGGEST BLOCKERS

1. **Atlas persistence is unexercised** — every real run uses the labelled DEV snapshot; no `MONGODB_URI`/Atlas credentials configured.
2. **Interrupted-search bookkeeping is not self-healing** — a search re-entered after a process interruption leaves a stranded `ACTIVE` candidate and inflated ledger counters (DEF-ACCEPT-1: report 3 patches/3 blue versions vs 2 persisted; C2 with 1 episode, no metrics).
3. **Stale configuration/documentation actively misleads** — `.env.example` still names `thinkingmachines/inkling:free` as Blue; `docs/REALITY_AUDIT.md` still says no Blue promotion. Both are false for the current tree.

---

## RECOMMENDED NEXT ACTION

**Fix run-ledger/report counter integrity and settle stranded candidates on re-entered searches** — make report counters derive from persisted records (or reset per search) and ensure every compiled candidate ends `PROMOTED`/`REJECTED`, so a real run's numbers are always reproducible from its own state. This is the only confirmed defect in the otherwise-complete real loop, and it protects the evidentiary value of every future REAL run.

Second priority: wire a real MongoDB (`MONGODB_URI`) into a REAL run to move persistence off the DEV label.
