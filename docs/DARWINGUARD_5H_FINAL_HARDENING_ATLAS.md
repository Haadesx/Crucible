# DarwinGuard — 5-Hour Final Hardening + MongoDB Atlas Migration Sprint
## October Bus Topology Recovery + Parallel Fixes + Atlas + Verification + Demo Freeze

We have approximately **5 hours total** before DarwinGuard must be presentation-ready.

This is the FINAL engineering sprint.

The goal is NOT to add speculative features.

The goal is:

1. reconstruct the actual OpenCode / October Bus topology after terminal restarts,
2. safely parallelize the remaining demo-critical work,
3. migrate the persistence path to **MongoDB Atlas for the event**,
4. independently verify the shipping configuration,
5. rehearse the exact demo,
6. freeze the system.

---

# HARD DEADLINE

Maximum total time:

**5 hours from task start**

Use this approximate budget:

```text
T+00–20 min   topology / terminal / Bus reconciliation
T+20–165 min  parallel hardening + Atlas migration
T+165–225     integration + full tests
T+225–260     independent verification / optional Kiro review
T+260–285     complete demo rehearsal
T+285–300     freeze + final report
```

At **T+4h30**, STOP feature/fix work unless the demo is genuinely broken.

Reserve the final 30 minutes for:

- starting the actual stack,
- validating historical evidence,
- validating Atlas-backed live state,
- AI-rig readiness,
- frontend/backend rehearsal,
- final report.

Do not spend all five hours coding.

---

# IMPORTANT CONTEXT — TERMINALS WERE REOPENED

Some OpenCode terminals were reopened with auto-approve permissions.

Therefore the previous Bus/canvas state may contain:

- disconnected terminal nodes,
- stale canvas nodes,
- restarted executions,
- old task claims,
- duplicate sessions,
- unreachable workers,
- workers whose displayed name no longer matches their actual Bus node,
- new terminal/kernel identities,
- orphaned processes.

DO NOT assume the previous four-agent swarm is still alive.

The first thing you must do is reconstruct reality.

---

# MODEL / HARNESS POLICY

For routine workers:

```text
Harness:
OpenCode

Provider:
DeepSeek

Model:
DeepSeek Flash
```

Do NOT use:

- Claude
- Codex
- GPT
- Gemini

for routine implementation.

Kiro CLI is installed and has substantial remaining credits.

Kiro MAY be used later as:

- high-level reviewer,
- orchestrator sanity-check,
- architecture reviewer,
- code-review / final verification layer.

Do NOT burn Kiro credits on mechanical implementation.

Prefer:

```text
OpenCode + DeepSeek Flash workers
        ↓
independent DeepSeek verifier
        ↓
optional ONE Kiro review
```

---

# CURRENT DARWINGUARD MODEL STACK — FREEZE IT

Do not model-shop anymore.

## Red

```text
qwen3.8-flash-next-heretic2
```

AI-rig endpoint:

```text
http://ai-rig.tail6d5242.ts.net:11500/v1
```

## Blue executor

```text
inclusionai/ling-3.0-flash-fin:free
```

## Blue engineer primary

```text
nvidia/nemotron-3-super-120b-a12b:free
```

## Blue engineer fallback

```text
inclusionai/ling-3.0-flash-fin:free
```

Do NOT change these during this sprint unless a provider is actually unavailable.

---

# KNOWN STARTING STATE

The previous authoritative audit reported:

```text
HEAD:
64732c3
```

Verify this again — do not assume it is still current.

Previously verified:

- 201 backend tests passing,
- mypy clean,
- Ruff clean on app + tests,
- frontend typecheck/build green,
- real Red empirical selection works,
- real Blue HarnessPatch evolution works,
- reasoning-token fix works,
- AI rig reachable,
- October Bus works,
- historical REAL evidence exists.

Known outstanding demo problems:

1. historical observer snapshots are writable through Start/Reset,
2. backend is not automatically serving the correct evidence snapshot,
3. overnight exported report is stale vs authoritative snapshot,
4. current Nemotron primary has config/bake-off evidence but no persisted shipping-config co-evolution run,
5. resume has some known boundary duplication / stranded candidate edge cases,
6. persistence is currently DEV snapshot only and **must now be migrated to MongoDB Atlas for the event**.

Do NOT broaden the task beyond these unless new evidence exposes a true blocker.

---

# PHASE 0 — RECONSTRUCT THE ACTUAL OPEN TERMINAL / BUS / KERNEL TOPOLOGY

DO THIS BEFORE SPAWNING ANYTHING.

Use the actual registered October Bus MCP tools.

Do not assume exact names if the runtime differs.

Previously observed capabilities included things like:

- `list_canvas`
- `list_peers`
- `find_sessions`
- `get_node_status`
- `check_inbox`
- `list_tasks`
- `add_terminal`
- `send_to_node`
- `message_peer`
- `wait_for_nodes`

Use the actual available tools.

---

## 0A. Identify this orchestrator

Report:

```text
current Bus node ID
display name
terminal ID
execution/session ID
kernel/process identity if exposed
harness
provider
model
workspace
git checkout/worktree
auto-approve state if observable
last activity
```

This terminal is the PRIMARY ORCHESTRATOR.

Keep it primarily as coordinator/integrator.

---

## 0B. Inventory the entire canvas

Inspect EVERY current canvas node/session.

Build:

| Node ID | Display Name | Terminal ID | Execution/Kernel | Harness | Provider | Model | Status | Workspace | Last Activity | Task Claim | Reachable |
|---|---|---|---|---|---|---|---|---|---|---|---|

Important:

Renamed canvas labels are NOT authoritative routing identifiers.

Use Bus/node IDs when communicating.

---

## 0C. Detect stale / duplicate sessions

Because terminals were reopened, classify every discovered node as:

```text
HEALTHY
STALE
DISCONNECTED
DUPLICATE
UNKNOWN
```

Do not delete anything yet.

For every apparently active OpenCode node, send a harmless correlated liveness request:

```text
Reply with:
BUS_READY
node ID
terminal/session ID
provider
model
workspace
current task if any
```

Wait for actual responses.

A canvas node that merely exists is NOT considered alive.

---

## 0D. Inspect shared tasks

Read the October Bus board.

Determine:

- tasks READY,
- tasks CLAIMED,
- tasks BLOCKED,
- tasks DONE,
- stale claims belonging to restarted terminals.

Do not accidentally continue an obsolete task just because its claim survived restart.

Map task claims back to the current live node IDs.

---

## 0E. Inspect local processes / kernels

Non-destructively inspect relevant processes/services.

Determine whether any of these are currently running:

```text
OpenCode sessions
Pycode sessions if any
Kiro CLI
October Bus MCP
Python workers
uvicorn/backend
frontend Vite server
co-evolution CLI
long-running experiment processes
SSH/Tailscale tunnels
```

If the environment exposes kernel/execution IDs, include them.

Do not kill unknown processes.

Flag likely orphaned duplicates.

---

# TOPOLOGY REPORT

Before proceeding internally establish:

```text
CONNECTED OPENCODE TERMINALS:
N

HEALTHY DEEPSEEK WORKERS:
N

STALE/DISCONNECTED NODES:
N

ACTIVE TASK CLAIMS:
N

ORPHANED TASK CLAIMS:
N

BACKEND PROCESSES:
N

FRONTEND PROCESSES:
N

ACTIVE COEVOLUTION RUNS:
N

KIRO AVAILABLE:
YES / NO
```

---

# PHASE 1 — BUILD THE MINIMUM WORKER TEAM

We need speed, not agent count.

Use at most:

```text
1 orchestrator
+
4 implementation workers
+
1 independent verifier
```

The extra worker is specifically for Atlas migration.

Do NOT spawn a large swarm.

---

## Reuse vs spawn

If existing workers are:

- reachable,
- correct workspace,
- OpenCode,
- DeepSeek provider,
- DeepSeek Flash,
- not busy with conflicting work,

they MAY be reused.

Otherwise spawn fresh OpenCode workers via October Bus.

Previous behavior showed that `add_terminal` may inherit:

- workspace,
- provider,
- model,

rather than accepting explicit model/cwd arguments.

Verify inheritance after spawn.

Every worker MUST prove:

```text
provider = deepseek
model = DeepSeek Flash
BUS_READY
```

before assignment.

If a spawned worker uses the wrong provider/model:

stop/recreate it.

---

# DESIRED WORKER ROLES

Create/reuse exactly these roles:

```text
Worker A — observer-safety
Worker B — demo-evidence-launch
Worker C — atlas-migration
Worker D — shipping-smoke
```

Then AFTER integration:

```text
Worker E — independent-verifier
```

Do not run Worker E concurrently with incomplete implementation.

---

# OCTOBER BUS WORKFLOW

For each worker:

1. create a shared task,
2. assign narrow acceptance criteria,
3. have the worker claim it,
4. send instructions via correlated request,
5. worker returns evidence,
6. worker completes board task,
7. orchestrator reviews diff/evidence,
8. do not trust author self-verification alone.

---

# WORKER A — OBSERVER SAFETY

## Objective

Fix the highest-risk demo bug:

Historical evidence snapshots can currently be mutated or erased through observer API actions.

Known dangerous paths include:

```text
POST /arena/start
POST /arena/reset
```

Historically:

- Start writes a run into whichever repository the server booted with,
- Reset can clear the repository,
- neither was protected,
- Start does NOT invoke the real co-evolution CLI anyway.

## Required architecture

Introduce an explicit distinction between:

```text
HISTORICAL / READ_ONLY
```

and:

```text
LIVE / WRITABLE
```

Do NOT determine this from a fragile filename pattern if avoidable.

Prefer an explicit runtime/repository/config capability.

## Historical behavior

When serving an evidence snapshot:

- GET/read APIs work,
- Start is blocked,
- Reset is blocked,
- other mutation paths are blocked where relevant,
- snapshot remains byte/state identical,
- UI should know or be able to know it is read-only.

Return a clear error such as:

```text
409 READ_ONLY_SNAPSHOT
```

or the project's established equivalent.

Do not silently create data elsewhere without telling the caller.

## Live behavior

When intentionally serving a fresh live snapshot:

- writes remain allowed,
- Start behavior may remain available if explicitly intended,
- Reset may exist only for live state,
- historical snapshots remain untouched.

## Tests

Prove:

1. historical Start blocked,
2. historical Reset blocked,
3. historical repository unchanged,
4. GET routes still work,
5. fresh live state writable,
6. current frontend does not break.

Do not modify historical experiment files.

## Worker A report

Return via Bus:

```text
FILES CHANGED
ROOT CAUSE
FIX
READ-ONLY MECHANISM
TESTS
KNOWN LIMITATIONS
```

---

# WORKER B — DEMO EVIDENCE + LAUNCH PATH

## Objective

Make the REAL persisted evidence easy and internally consistent to demo.

Do NOT modify historical run state.

## B1. Overnight authoritative source

Use:

```text
backend/experiments/OVERNIGHT-COEV-20260926-022643/state.json
```

Authoritative known totals:

```text
7 generations
256 model calls
```

Verify those from the file.

Do not trust the old exported run report.

## B2. Repair/rebuild stale report

The current exported overnight report is a mid-run checkpoint:

```text
3 generations
102 model calls
```

Use existing read-only tooling such as:

```text
finalize.py
generation_table.csv
evidence.json
journal
```

where appropriate.

Generate a NEW final report/export derived from the authoritative snapshot.

Do not hand-edit values.

Do not overwrite irreplaceable historical evidence.

The UI must stop showing contradictory 102 vs 256 totals as though both are final.

If useful, preserve the checkpoint but label it explicitly as:

```text
PHASE-A CHECKPOINT
```

## B3. Historical demo targets

Prepare exact launch support for:

### Overnight run

```text
OVERNIGHT-COEV-20260926-022643
```

Story:

```text
G00
Red breaches B0 twice
→ Blue creates defense
→ C1 promoted
→ C1 holds G01–G06
while Red continues measured mutation selection
```

### Two-sided arms-race run

```text
COEV-SEL-20260926-011123
```

Story:

```text
Blue initially holds
→ Red evolves
→ ASR 0.333
→ ASR 0.667
→ Blue evolves
→ new Blue champion holds
```

Never merge these into one fake trajectory.

## B4. Demo launcher

Prepare exact scripts/commands for:

```text
DEMO OVERNIGHT
DEMO TWO-SIDED
DEMO LIVE
```

Prefer tiny scripts over a large new snapshot-picker feature.

Possible shape:

```text
scripts/demo-overnight.sh
scripts/demo-two-sided.sh
scripts/demo-live.sh
```

Follow current repo conventions.

Each command must make clear:

- persistence source,
- read-only/writable mode,
- API port,
- frontend expectations.

Do not rely on `.dev-state.json`.

## B5. UI consistency

Verify UI displays authoritative:

- generation count,
- model call count,
- Red champion,
- Blue champion,
- ASR,
- patch attribution,
- model attribution,
- lineage,
- read-only status if added.

Do not fabricate derived values.

## Worker B report

Return:

```text
AUTHORITATIVE TOTALS
REPORT RECONCILIATION
FILES/ARTIFACTS
LAUNCH COMMANDS
UI CHECK
DISCREPANCIES
```

---

# WORKER C — MONGODB ATLAS MIGRATION

## Objective

We are now at the MongoDB event.

Atlas migration is REQUIRED for the live/demo persistence path.

The existing system already has repository abstractions and Mongo/Atlas-oriented code.

Do NOT rewrite the co-evolution engine.

Do NOT invent a second persistence architecture.

Use the existing repository interface and make Atlas the active persistence backend for NEW live/demo runs.

Historical JSON evidence remains historical and read-only.

## C1. Discover existing Atlas/Mongo implementation

Inspect:

- repository/storage interfaces,
- Mongo repository implementation,
- Atlas-specific configuration,
- pymongo/Motor usage,
- collection/index initialization,
- vector-search code if present,
- change streams if present,
- `.env.example`,
- runtime config,
- previous Atlas audit/docs.

Determine exactly:

```text
what is already implemented
what is tested
what is missing
what is only DEV fallback
```

Do not duplicate existing logic.

## C2. Credentials and configuration

Use Atlas credentials only from:

- current environment variables,
- event-provided secrets,
- existing secure local config.

Expected variable may be:

```text
MONGODB_URI
```

Use the actual repository configuration.

NEVER:

- print the URI,
- print username/password,
- commit credentials,
- paste credentials into Markdown,
- weaken Atlas network/security settings unnecessarily.

If Atlas requires event setup such as:

- database user,
- IP/network access,
- cluster/database name,

use the smallest necessary configuration.

Do not enable global `0.0.0.0/0` unless absolutely required by event instructions and explicitly unavoidable; prefer current venue IP or supported secure access.

## C3. Validate connectivity FIRST

Before code changes, perform a harmless Atlas connectivity test through the existing adapter/config.

Confirm:

```text
DNS/TLS
authentication
ping
database access
write permission
readback
```

Use a disposable smoke namespace/document if needed.

Clean up only the disposable probe data.

Do not touch historical snapshots.

## C4. Atlas collections

Use the existing schema/collection names.

The Atlas persistence path must support whatever the real engine currently persists, including at least:

- runs,
- generations,
- Red agent versions / lineages,
- Blue harnesses / lineages,
- attacks/candidates,
- episodes,
- evaluations,
- model calls,
- HarnessPatch records,
- candidate harnesses,
- promotion/rejection decisions,
- events,
- run reports,
- active champion/pointer state,
- historical champion information where used.

Do not rename collections unnecessarily.

## C5. Known Mongo defects must stay fixed

Previous work already fixed issues such as:

- Mongo `_id` leaking into strict Pydantic models,
- unsigned 64-bit seed overflow,
- ledger append-only behavior,
- async aggregate handling,
- change-stream behavior,
- false capability naming.

Verify current code still contains the fixes.

Do not regress them.

## C6. Indexes

Ensure required normal Mongo indexes exist.

If the code genuinely uses Atlas Vector Search in the demo path:

- inspect the expected search index definition,
- create/verify it using the existing intended schema,
- verify a real query.

If vector search is NOT needed for the actual judge demo path, do not burn an hour building speculative vector-search infrastructure.

Clearly report:

```text
ATLAS CRUD: VERIFIED / NOT VERIFIED
ATLAS VECTOR SEARCH: VERIFIED / NOT REQUIRED / NOT VERIFIED
```

Do not claim vector search if it was not actually exercised.

## C7. Migrate NEW live/demo persistence, not historical truth

Historical files such as:

```text
OVERNIGHT-COEV-20260926-022643
COEV-SEL-20260926-011123
```

must remain unchanged.

For Atlas, create a clean event/demo run namespace.

Something like:

```text
DARWINGUARD-EVENT-20260926
```

or follow existing run-id conventions.

Do NOT rewrite old provenance to say Atlas was used historically.

## C8. Atlas acceptance test

Run an Atlas-backed smoke path that proves:

```text
process A:
create/write run state to Atlas

process B / fresh repository instance:
read the run back from Atlas

resume/reconstruct:
Red champion
Blue champion
generation state
events
model calls
patch/candidate decisions
```

Then, if practical, execute one tiny live REAL generation backed by Atlas.

The important acceptance criterion is:

```text
REAL DarwinGuard writes to Atlas
→ process exits/restarts
→ new process reads the same state correctly
```

No silent fallback to JSON is allowed when Atlas mode is selected.

If Atlas is unavailable, fail loudly.

## C9. Runtime labels

When Atlas is active, UI/report/runtime banners must say something truthful like:

```text
ATLAS CONNECTED
```

When JSON snapshot is active:

```text
DEV SNAPSHOT
```

Never label DEV persistence as Atlas.

## C10. Tests

Add focused tests for:

- Atlas config selection,
- fail-closed behavior when Atlas selected but unavailable,
- persistence round-trip using the repository boundary where feasible,
- `_id` sanitation,
- champion pointers,
- run re-entry/readback,
- no silent DEV fallback.

Do not create an enormous integration suite if a focused set plus a real Atlas smoke proves it.

## Worker C report

Return through Bus:

```text
ATLAS URI PRESENT:
YES / NO
(do not print it)

CONNECTIVITY:
PASS / FAIL

DATABASE/COLLECTIONS:
<names without secrets>

INDEXES:
<verified>

ATLAS CRUD:
PASS / FAIL

VECTOR SEARCH:
VERIFIED / NOT REQUIRED / NOT VERIFIED

REAL LIVE RUN USING ATLAS:
YES / NO

FRESH PROCESS READBACK:
PASS / FAIL

SILENT FALLBACK POSSIBLE:
YES / NO

FILES CHANGED:
...

TESTS:
...

BLOCKER:
...
```

---

# WORKER D — SHIPPING CONFIG REAL SMOKE

## Objective

Prove the CURRENT shipping model configuration.

Historical Blue patches were authored by Ling.

Current production primary is Nemotron.

We need fresh evidence showing the current configured primary path works end-to-end.

Where possible, coordinate with Worker C so this smoke run uses the NEW Atlas-backed live repository after Atlas connectivity is ready.

Do not both edit the same persistence code.

## Fresh isolated run only

Use a clear run ID such as:

```text
VENUE-SHIPPING-SMOKE-<timestamp>
```

Do NOT mutate historical runs.

## Models

### Red

```text
qwen3.8-flash-next-heretic2
```

### Blue executor

```text
inclusionai/ling-3.0-flash-fin:free
```

### Blue engineer primary

```text
nvidia/nemotron-3-super-120b-a12b:free
```

### Blue fallback

```text
inclusionai/ling-3.0-flash-fin:free
```

## First do readiness probes

Verify:

- Tailscale,
- AI rig,
- model endpoint,
- Red model present,
- OpenRouter,
- Blue executor reachable,
- Nemotron reachable,
- Ling fallback reachable,
- Atlas ready if Worker C has completed.

Do not burn time debugging nonexistent problems.

## Smoke workload

Use a very small REAL configuration.

Approximately:

```text
generations = 1
Red versions = 2
attacks/version = 1
Red eval attacks = 1
Blue candidates = 1
```

Do not run a soak.

## If no natural breach

Do NOT wait an hour hoping for one.

Use one frozen REAL breach case through the production:

```text
Blue engineer
→ HarnessPatch validation
→ compilation
→ replay/regression
→ deterministic decision
```

This is acceptable for proving current Nemotron integration.

Do not invent breach evidence.

## Record

```text
actual Blue engineer model
fallback used?
provider latency
provider errors
patch validity
patch operations
compiled?
replay?
fitness
utility
promotion/rejection
Atlas run ID / persistence proof
```

Also verify the reasoning-token fix still works for Red.

## Worker D report

Return:

```text
RUN ID
MODE
PERSISTENCE BACKEND
RED MODEL
BLUE EXECUTOR
BLUE ENGINEER ACTUALLY USED
FALLBACK USED
PATCH VALID
COMPILED
REPLAY
DECISION
ATLAS READBACK
ERRORS
LATENCY
```

---

# ORCHESTRATOR — INTEGRATION

While workers execute:

DO NOT edit the same files casually.

Track ownership.

Pay special attention to overlap between:

- observer/runtime configuration,
- Atlas/repository configuration,
- demo launch scripts.

When workers finish:

1. inspect every diff,
2. verify evidence,
3. resolve overlap manually,
4. preserve source provenance,
5. integrate in small waves.

Do not merge a change just because a worker says PASS.

---

# FULL TEST GATE

After integration run:

## Backend

```bash
cd backend
uv run pytest -q
uv run mypy app
uv run ruff check app tests
```

Do NOT waste time fixing unrelated experiment/script lint unless it affects the demo.

## Frontend

```bash
cd frontend
npx tsc -b
npm run build
```

All must pass before moving forward.

---

# PHASE 3 — SPAWN A FRESH INDEPENDENT VERIFIER

After implementation is integrated, spawn/reuse ONE fresh OpenCode + DeepSeek Flash worker.

It must NOT be one of the four authors if avoidable.

Assign:

```text
independent-verifier
```

It must independently verify actual behavior.

---

# VERIFICATION MATRIX

## A. Historical safety

Using a COPY or protected evidence state where needed:

1. load overnight snapshot,
2. record checksum/state,
3. attempt Start,
4. confirm blocked,
5. attempt Reset,
6. confirm blocked,
7. re-check checksum/state,
8. confirm unchanged.

## B. Live-state isolation

1. create fresh live state,
2. confirm it is writable,
3. verify changes appear only there,
4. historical state remains unchanged.

## C. Overnight evidence

Confirm:

```text
7 generations
256 model calls
```

Confirm UI/report agree.

## D. Two-sided evidence

Confirm:

```text
COEV-SEL-20260926-011123
```

loads and shows the actual two-sided evolutionary sequence.

## E. Atlas

Independently confirm:

```text
Atlas selected for live/demo persistence
real write succeeds
fresh process readback succeeds
champion/run state reconstructs
no silent JSON fallback
```

If Atlas Vector Search is claimed, verify an actual search.

If it is not required, explicitly say so.

## F. Shipping Blue

Confirm current fresh evidence really contains:

```text
nvidia/nemotron-3-super-120b-a12b:free
```

as engineer if the primary succeeded.

If Ling fallback was used, report that honestly.

## G. Historical attribution

Old Ling-authored patches must still show:

```text
Ling
```

Do not relabel history as Nemotron.

## H. Core build

Independently confirm:

```text
pytest
mypy
ruff
frontend typecheck
frontend build
```

---

# OPTIONAL KIRO REVIEW

ONLY after the independent DeepSeek verifier finishes.

If Kiro CLI is immediately available and using it will not derail timing:

start ONE Kiro review session.

Give it ONLY:

- observer safety diff,
- Atlas migration diff,
- final verifier report,
- relevant tests.

Ask:

```text
Find any correctness, persistence-integrity, or demo-safety issue that both authors and verifier missed.
Do not redesign the project.
Return maximum 5 findings, severity-ranked.
```

Do not send Kiro on broad implementation.

Time-box Kiro review to approximately 20 minutes.

If Kiro setup itself takes meaningful time, skip it.

---

# PHASE 4 — SOURCE CONTROL

Integrator owns commits.

Before committing:

- inspect git diff,
- inspect untracked files,
- ensure no secrets,
- ensure no MongoDB URI,
- ensure no historical evidence accidentally changed.

Prefer compact commits such as:

```text
fix: protect historical observer snapshots

feat: enable Atlas persistence for event live runs

demo: reconcile persisted run evidence and launch flow

test: verify shipping provider and Atlas path
```

Exact structure may differ if cleaner.

Do not commit giant temporary smoke state unless intentionally required.

---

# PHASE 5 — COMPLETE DEMO REHEARSAL

At approximately T+4h15 to T+4h30, stop coding.

Now rehearse what I will actually show.

## Rehearsal 1 — overnight historical run

Start backend in HISTORICAL READ-ONLY mode using:

```text
OVERNIGHT-COEV-20260926-022643
```

Start frontend.

Verify visually:

- 7 generations,
- correct Red/Blue lineage,
- G00 breaches,
- Blue patch,
- C1 promotion,
- G01–G06 held,
- mutation promotion/rejection events,
- correct model attribution,
- correct totals,
- Start/Reset cannot corrupt evidence.

## Rehearsal 2 — two-sided historical run

Load:

```text
COEV-SEL-20260926-011123
```

Verify:

```text
held
→ Red adapts
→ ASR 0.333
→ ASR 0.667
→ Blue adapts
→ new champion holds
```

Again:

do not claim these events came from the overnight run.

## Rehearsal 3 — Atlas-backed fresh live mode

Create/use a fresh writable Atlas run.

Confirm:

- backend says Atlas connected,
- frontend sees the run,
- a write is persisted,
- fresh process can read it back,
- historical snapshots untouched,
- REAL models reachable.

Do NOT start a long run.

---

# FINAL FREEZE RULE

Once rehearsal passes:

STOP ENGINEERING.

No:

- new feature,
- model switch,
- UI redesign,
- fitness change,
- large refactor,
- dependency update,
- second persistence rewrite.

unless the running demo is literally broken.

---

# FINAL REPORT

Return ONE concise authoritative report.

## 1. TOPOLOGY

```text
Canvas nodes:
Healthy terminals:
Stale terminals:
Disconnected terminals:
OpenCode workers:
Provider/model:
Active kernels/executions:
Orphaned claims:
October Bus:
Kiro:
```

Include:

| Node | Terminal | Execution/Kernel | Model | Status | Task |
|---|---|---|---|---|---|

## 2. SWARM EXECUTION

```text
Observer worker:
Evidence worker:
Atlas worker:
Shipping worker:
Verifier:
Optional Kiro:
```

For each:

```text
spawn/reuse
Bus messaging
task claimed
task completed
result
```

## 3. OBSERVER SAFETY

```text
Historical Start blocked:
Historical Reset blocked:
Historical state unchanged:
Live state writable:
```

## 4. ATLAS

```text
Atlas connected:
Database:
Collections:
Required indexes:
Vector Search:
Live write:
Fresh-process readback:
Resume/reconstruct:
Silent fallback disabled:
```

Do NOT print secrets.

## 5. OVERNIGHT EVIDENCE

```text
Run:
Generations:
Model calls:
Report reconciled:
UI reconciled:
Historical file unchanged:
```

## 6. TWO-SIDED RUN

```text
Loads:
Lineage correct:
ASR progression:
Blue response:
Historical file unchanged:
```

## 7. SHIPPING CONFIG

```text
Red:
Blue executor:
Blue engineer configured:
Blue engineer actually exercised:
Fallback:
Patch:
Compile:
Replay:
Decision:
Persistence backend:
```

## 8. TESTS

```text
pytest:
mypy:
ruff:
frontend tsc:
frontend build:
```

## 9. SOURCE CONTROL

```text
HEAD:
commits:
working tree:
historical evidence modified:
YES / NO
secrets committed:
YES / NO
```

Required:

```text
historical evidence modified: NO
secrets committed: NO
```

## 10. EXACT DEMO COMMANDS

Give me copy-paste commands, in order, for:

### A. Start overnight historical demo

### B. Start two-sided historical demo

### C. Start fresh Atlas-backed live demo

### D. Check AI-rig readiness

### E. Optionally start ONE short REAL Atlas-backed generation

Do not use placeholders if the repo already knows the exact paths/config.

Do not echo the MongoDB URI.

## 11. JUDGE STORY

Give me a 60–90 second technical explanation of the demo:

- what Red does,
- what Blue does,
- how empirical selection works,
- why this is genuine evolution rather than two chatbots talking,
- what Atlas persists,
- what the persisted evidence proves.

Keep it factual.

## 12. FINAL VERDICT

Choose exactly:

```text
READY FOR JUDGES
```

or

```text
NOT READY
```

If NOT READY:

maximum 3 blockers.

---

# DO NOT DO THESE DURING THIS SPRINT

Do NOT:

- switch Red models,
- change fitness weights,
- redesign the UI,
- run another multi-hour soak,
- rewrite the co-evolution architecture,
- add speculative features,
- use Claude/Codex,
- fabricate missing historical evidence,
- combine separate runs into one fake story,
- rewrite old JSON history into Atlas and pretend Atlas was used historically,
- expose MongoDB credentials.

We have five hours.

Optimize for:

```text
safety
Atlas persistence
evidence integrity
runtime reliability
demo clarity
```

not additional feature count.
