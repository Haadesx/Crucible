# DEMO RUNBOOK — 2026-09-26 (venue)

Product: **Crucible** (internal identifiers keep the DarwinGuard name; the scripts' READY banner
and run ids are runtime output and are quoted verbatim).

Three demo targets, in the order to show them. The first two are persisted REAL evidence
and never merge: different runs, different snapshots, different numbers. The third starts
a fresh live run. Everything here was executed and verified in this session unless marked
otherwise; the evidence snapshots were hashed before and after and did not change.

Launch scripts live in `scripts/`; run them from the repo root.

| Target | Script | Persistence source | Mode | API | Frontend |
|---|---|---|---|---|---|
| 1. Long-horizon run (~3 h; 7 gens / 256 calls; 2h42m wall clock) | `scripts/demo-overnight.sh` | derived DEV snapshot (final report rebuilt read-only) | read-only evidence | `:8000` | Vite `:5175` |
| 2. Two-sided (4 gens / 132 calls) | `scripts/demo-two-sided.sh` | copy of `.dev-state-coevo-20260926-011123.json` | read-only evidence | `:8000` | Vite `:5175` |
| 3. Live (optional, real spend) | `scripts/demo-live.sh [--run]` | fresh disposable snapshot under `$TMPDIR/darwinguard-demo/` | CLI writes; observer read-only | `:8000` | Vite `:5175` |

Both read-only scripts copy the snapshot to `$TMPDIR/darwinguard-demo/` and serve the
copy, so no click can touch a repository artifact even if the writer guard is absent.
With the guard present, `POST /arena/start` and `POST /arena/reset` return `409
READ_ONLY_SNAPSHOT` and the served copy stays byte-identical (verified below).

The scripts also pin the observer to snapshot mode explicitly
(`MONGODB_URI= RUN_MODE=DEV`): `backend/.env` may carry a real Atlas `MONGODB_URI`, and
`build_container` prefers Mongo whenever `has_mongodb` is true — the historical demos
must never connect to Atlas. (`PERSISTENCE` is not read by `build_container`;
`RUN_MODE=DEV` is the mode guard that also prevents a REAL-mode `.env` from failing the
snapshot boot.) `scripts/demo-live.sh` pins its observer the same way to the tmp JSON
state its CLI writes; swapping the live demo to Atlas is a later, separate change.

Frontend: `cd frontend && npm run dev -- --port 5175 --strictPort` → `http://localhost:5175`.
Vite proxies `/arena`, `/runs`, `/generations`, `/system`, … to `:8000`, so the API must stay on
port 8000. `--strictPort` makes Vite fail instead of silently moving to another port; `:5173`
belongs to another project. The scripts start the frontend for you; `--api-only` starts just
the API, detached in the background, so it survives the script exiting.

## Startup safety checks (Kiro finding 3)

Both historical scripts now refuse to present anything until they have proven it is the right
run, and the live script refuses to boot on top of a foreign observer:

1. **Port ownership.** Before starting anything they check `:8000` (and `:5175` in full mode)
   with `lsof`; if a process already listens there, the script prints the owning PID/command
   and exits non-zero. This is what prevents the Atlas observer on `:8000` from being mistaken
   for the historical run.
2. **Identity + health.** The API is started detached (`nohup` + `disown`), then the script
   waits for `/health` of the process it started. Dead process or 30 s without health → kill
   our own API, exit non-zero.
3. **Read-only + run id.** `GET /system/status` must report `read_only: true`, and
   `GET /runs` must list the expected run id (`latest_run_id` must equal it too). Any mismatch
   → kill our own API, exit non-zero.
4. **READY last.** Only after all checks pass it prints:

   ```text
   DARWINGUARD HISTORICAL DEMO READY
   Run: OVERNIGHT-COEV-20260926-022643      (or COEV-SEL-20260926-011123)
   Backend: http://127.0.0.1:8000
   Frontend: http://localhost:5175
   Mode: HISTORICAL · READ ONLY
   ```

   A failed check never prints READY. In `--api-only` mode the API keeps running (detached);
   in full mode Ctrl-C tears down both API and Vite.

---

## Target 1 — Long-horizon run (~3 hours; 7 generations / 256 model calls; 2h42m wall clock): G00 breach, C1 promoted, six held generations

**Launch:** `scripts/demo-overnight.sh` (Ctrl-C tears down API and Vite).

**Persistence:** `backend/exports/derived/OVERNIGHT-COEV-20260926-022643/state.final.json`
is the derived snapshot the script serves. It was rebuilt read-only from the authoritative
snapshot `backend/experiments/OVERNIGHT-COEV-20260926-022643/state.json`
(sha256 `10373cb9…0c35`) by `backend/scripts/rebuild_run_report.py`; the source was re-hashed
after the rebuild and is byte-identical. Only `run_reports[OVERNIGHT-COEV-20260926-022643]`
and two metadata keys (`derived_from`, `derived_at`) differ from the source.

**Why a derived snapshot:** the formal CLI export on disk
(`backend/experiments/OVERNIGHT-COEV-20260926-022643/exports/run_report_OVERNIGHT-COEV-20260926-022643.json`)
is the **PHASE-A CHECKPOINT** — it was written after 3 generations / 102 calls, then the run
continued to 7 / 256 before the volume incident killed it mid-generation 7. It is kept
untouched as historical evidence. The derived final report says 7 generations / 256 calls,
so the UI no longer presents 102 and 256 as two contradictory finals. If anyone boots the
*original* snapshot instead, the UI labels the report "export checkpoint" and explains the
difference (`frontend/src/lib/viewmodel.ts:reportCheckpoint`), though the derived snapshot
is the intended source.

**Authoritative totals (from `state.json`, B1):** 7 generations (G00–G06), 256 model calls
(45 ledgered errors), 62 attack candidates, 139 episodes, 28 Red versions, 3 Blue versions,
2 patch records (1 promoted), 23 Red boundary decisions (11 promoted / 12 rejected).

**What the UI shows:**

| Field | Value |
|---|---|
| Generations | 7 (G00–G06) |
| Model calls | 256 (`red_attacker` 81, `red_mutator` 29, `blue_executor` 142, `blue_harness_engineer` 4) |
| ASR by generation | 0.667, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 |
| Utility by generation | 0.667 every generation |
| Red champion | `R-…-G06-538bf492` (decision-time fitness 0.0862) |
| Blue champion | `B-…-G01-C1` (ELITE; block rate 1.0) |
| Red hall of fame | `A-…-G00-83848bcf` (fit 1.0), `A-…-G00-e9ae9662` (fit 0.7826) |
| Red evolutions | 23 decisions: 11 promoted, 12 rejected |

**Demo click path (in order):**

1. Open the RUN REPORT window: 7 generations, 256 calls, champions above.
2. Go to G00: two breaches (direct_override, scenario DOC-001) vs the baseline B0 —
   `B-…-G00-B0` blocked 0 of them.
3. Blue lineage: patch `PATCH-…-G01-1` authored by Ling —
   PROPOSED → VALIDATED (3 ops) → COMPILED (9 nodes) → EVALUATED (fitness 0.702 over 10
   battles) → PROMOTED. `PATCH-…-G01-2` lost on fitness (0.698 vs 0.702). C1 then held
   every attack in G01–G06 (ASR 0.0 each).
4. Follow the mutation stream G01–G06: 11 promotions and 12 rejections, each with a
   measured parent-vs-child fitness and a mutation note naming the defense it worked
   around. Red keeps attacking; C1 keeps holding.
5. Optional caveat to mention honestly: `R-…-G08-cc4699b5` (parent `G06-538bf492`) was
   created by the in-flight generation when the volume unmounted; it is ACTIVE with no
   evaluation and no episode. A future resume evaluates it before selection.

**Known export checkpoint on disk (do not edit):**
`backend/experiments/OVERNIGHT-COEV-20260926-022643/exports/run_report_OVERNIGHT-COEV-20260926-022643.json`
= 3 generations / 102 calls. The journal, `generation_table.csv`, `evidence.json`,
`red_lineage.txt`, `blue_lineage.txt`, `model_calls.json` in that directory were rebuilt
read-only from the snapshot after recovery; the final derived copies live in
`backend/exports/derived/OVERNIGHT-COEV-20260926-022643/`.

## Target 2 — Two-sided: held → Red breaks through → Blue adapts → holds

**Launch:** `scripts/demo-two-sided.sh` (Ctrl-C tears down both). The script serves a
disposable copy; `backend/.dev-state-coevo-20260926-011123.json` is never modified
(sha256 `f7d01684…6073` before and after the demo run).

**Story beats (from the run's own records):**

| Generation | ASR | What happened |
|---|---:|---|
| G00 | 0.0 | Baseline B0 holds |
| G01 | 0.333 | Red adapts and breaches |
| G02 | 0.667 | Red widens the breach; Blue proposes two patches at the G01 boundary — both rejected on the utility floor (0.40 < 0.50) |
| G03 | 0.0 | Blue promotes `PATCH-…-G03-1` (2 ops, fitness 0.683 over 11 battles) as C1; `G03-2` loses by 0.681 vs 0.683; C1 holds |

**What the UI shows:** 4 generations, 132 model calls, ASR `[0.0, 0.333, 0.667, 0.0]`,
Red champion `R-…-G02-6992fd0c`, Blue champion `B-…-G03-C1`, 20 attacks (3 successful),
4 patch records (1 promoted), Red decisions 3 promoted / 7 rejected. The run includes a
real resume (see `docs/OVERNIGHT_COEV_VERDICT_2026-09-26.md` §H).

**Click path:** show G00 held, then step G01 and G02 to watch ASR climb; open the patch
records to show the two utility-floor rejections and then the G03 promotion; step G03 to
show ASR back to 0.0 under C1. This is the "both sides evolve" story — do not narrate it
with target 1's numbers or champions.

## Target 3 — Live (only if asked; real model spend)

**Launch:** `scripts/demo-live.sh` boots a writable stack and prints the exact one-generation
command; `scripts/demo-live.sh --run` also executes it (real calls). Persistence is a fresh
disposable state under `$TMPDIR/darwinguard-demo/live-<timestamp>/`; no experiment directory
or `.dev-state*.json` is touched. The observer API is read-only even here; the CLI writes
the state directly, and the script relaunches the API afterwards so it reloads the run
(the API holds an in-memory copy).

**Preflight before `--run`:**

```bash
cd backend
grep -E 'RED_BASE_URL|RED_MODEL|BLUE_MODEL|BLUE_ENGINEER_MODEL' .env   # AI rig + OpenRouter, do not print keys
curl -s -m 3 "$(grep '^RED_BASE_URL' .env | cut -d= -f2-)/models" | head -c 300
curl -s http://127.0.0.1:8000/health
```

Expected from the current config: Red `qwen3.8-flash-next-heretic2` on the ai-rig,
Blue executor `inclusionai/ling-3.0-flash-fin:free` via OpenRouter, engineer primary
`nvidia/nemotron-3-super-120b-a12b:free` with Ling as fallback. One generation is ~15–20
calls and 3–6 minutes with a warm rig; 38–53 minutes is possible when the rig returns
empty completions (that is what happened late in the long-horizon run). Do not soak.

The latest complete live run in Atlas is `CRUCIBLE-LIVE-20260926-162014`: ASR `[1.0, 0.0]`,
a Nemotron patch (`recipient_validation` + `input_classifier`) promoted at fitness 0.676, and
5 Atlas memory recalls with outcomes `PROMOTED ×3 / REJECTED ×1`.

**Note:** the UI's Start button runs the legacy arena loop (`/arena/start`), not the
co-evolution engine. On a historical server it is refused with `409 READ_ONLY_SNAPSHOT`. For a
live co-evolution demo use the printed CLI command, then reload the page when it exits. The
script relaunches the API so the finished run is loaded.

---

## Evidence hygiene (checked in this session)

Hashes before and after the derived rebuild, the finalize rerun, both demo API boots, and the
demo-script safety tests (2026-09-26, port-collision + run-id verification):

| File | sha256 |
|---|---|
| `experiments/OVERNIGHT-COEV-20260926-022643/state.json` | `10373cb94c34b16da36ef5cf6d970e51104fe8651eae565774730a979dcc0c35` |
| `experiments/OVERNIGHT-COEV-20260926-022643/exports/run_report_…json` (phase-A checkpoint) | `39a5ef64e212c1dc4208410f9da95999ad5bc71377207557f1dc850d8b9b83d1` |
| `experiments/OVERNIGHT-COEV-20260926-022643/OVERNIGHT_COEV_JOURNAL.md` | `93e176005609ebe92acad3216c587e0a07d0e5b50fc3a8c6258edc6cfd2c3910` |
| `.dev-state-coevo-20260926-011123.json` | `f7d016846bf61968df09e68d3048e9366506b72920a74ef0af5b1c2cbb906073` |

Derived artifacts (regenerable at any time):

| File | sha256 |
|---|---|
| `exports/derived/OVERNIGHT-COEV-20260926-022643/state.final.json` | `10cfa81f212a372d372ad6d3054dc71f67216c60c0bcaa663601c56505ef035e` |
| `exports/derived/OVERNIGHT-COEV-20260926-022643/run_report_…-FINAL.json` | `1571f2a7be29e8efd45e1e4cd1a2c112bd5da488fe601f893f14ed2b0b177c7b` |

Rebuild command (idempotent, read-only on the source):

```bash
cd backend
.venv/bin/python scripts/rebuild_run_report.py \
  --state experiments/OVERNIGHT-COEV-20260926-022643/state.json \
  --run-id OVERNIGHT-COEV-20260926-022643 \
  --out-dir exports/derived/OVERNIGHT-COEV-20260926-022643
```

The rebuild is validated against the completed `COEV-SEL2-20260926-013728` run: applying
`scripts/rebuild_run_report.py` to its snapshot reproduces the original exported report
exactly in every content field (only `created_at` and two intra-generation ordering swaps
differ; 12/12 comparisons identical as a multiset).

## Read-only guard status

The observer read-only guard is in the working tree: a snapshot-backed repository is
read-only by default, `/system/status` reports `read_only` straight from the repository
capability (`backend/app/api/generations.py`), and `POST /arena/start` / `POST /arena/reset`
return `409 READ_ONLY_SNAPSHOT`. Verified 2026-09-26 after the demo-script changes: both
historical scripts boot with `read_only=true`, both refused mutations with 409, and the
source hashes did not change (table above). If the guard ever regresses, the scripts still
serve disposable copies, but the startup check (`/system/status` read_only + 409 probe) would
fail and READY would not print.

## Caveats to state if asked

- Persistence is DEV / Atlas NOT CONNECTED; every run is labelled that way in the UI.
- The long-horizon run was recovered after an APFS/FileVault unmount; no model calls were
  made after the incident, and G07 was in flight with one unevaluated Red candidate.
- The phase-A export on disk remains the mid-run checkpoint; the derived final report is
  the demo's source of truth and is labelled as derived in `REBUILD_NOTES.md`.
- Historical run reports and snapshots must never be edited; all demo artifacts are copies
  or derived files under `backend/exports/derived/`.
