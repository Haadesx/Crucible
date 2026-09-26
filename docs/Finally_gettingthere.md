# DarwinGuard — Final UI/Product Fix Sprint
## Apply Kiro Findings → Verify → Rehearse → FREEZE

Kiro has completed the final adversarial product/safety/UI review.

Read this first:

```text
docs/KIRO_FINAL_REVIEW_2026-09-26.md
```

Expected reviewed HEAD was:

```text
2795934
```

Verify current HEAD before doing anything.

Kiro's verdict was:

```text
DO NOT DEMO YET
```

But importantly:

- backend correctness PASSED
- Atlas persistence PASSED
- historical snapshot safety PASSED
- no silent persistence fallback PASSED
- Nemotron shipping path PASSED
- historical attribution PASSED
- tests/builds PASSED

The remaining problems are small and primarily UI/demo-path issues.

We need to fix them QUICKLY, verify them independently, rehearse the UI, and then FREEZE THE SYSTEM.

---

# HARD RULES

Do NOT:

- change Red model
- change Blue models
- change fitness formulas
- change Atlas architecture
- migrate persistence again
- modify historical experiment evidence
- redesign the co-evolution engine
- add Strands as a dependency
- use Claude
- use Codex
- run another long soak
- introduce speculative features

This is a narrow frontend/demo-safety sprint.

Target completion:

```text
60–90 minutes maximum
```

---

# USE OCTOBER BUS

First inspect the current Bus/canvas topology because terminals may have been restarted.

Determine:

```text
current orchestrator node
healthy OpenCode terminals
stale/disconnected terminals
existing task claims
Kiro node/status
```

Use node IDs, not canvas display names, for routing.

Reuse healthy OpenCode + DeepSeek Flash workers where practical.

Do not create duplicates unnecessarily.

Preferred team:

```text
ORCHESTRATOR
│
├── Worker A — UI safety + product state
├── Worker B — demo scripts / runtime path
└── Worker C — independent verifier
```

Workers A/B:

```text
OpenCode
DeepSeek provider
DeepSeek Flash
```

Worker C must verify after integration, not author fixes.

Kiro should remain reviewer only.

---

# CURRENT PRODUCT TARGET

DarwinGuard should feel like:

> October.dev if October.dev were built specifically to observe an adversarial, self-improving security harness.

The visual category is:

```text
full-screen spatial canvas
floating runtime windows
visible execution topology
real causal connections
large negative space
developer/operator aesthetic
pan/zoom
inspectable evidence
lineage
```

But the UI must represent the REAL DarwinGuard system:

```text
RED CHAMPION
    ↓
ATTACK
    ↓
SANDBOX
    ↓
EVALUATOR
    ↓
HELD / BREACH
        │
        ├── HELD
        │     ↓
        │   RED MUTATION PRESSURE
        │
        └── BREACH
              ↓
          BLUE ENGINEER
              ↓
          HARNESS PATCH
              ↓
          CANDIDATE HARNESS
              ↓
          REPLAY / REGRESSION
              ↓
          CHAMPION JUDGE
              ↓
          PROMOTE / REJECT
              ↓
          NEXT BLUE CHAMPION
```

Red evolves separately:

```text
RED PARENT
→ MUTATION
→ RED CANDIDATE
→ EMPIRICAL EVALUATION
→ PROMOTE / REJECT
→ NEXT RED CHAMPION
```

The UI must never imply model fine-tuning.

The actual concept is:

```text
MODEL WEIGHTS FROZEN
HARNESS EVOLVES
RED STRATEGY EVOLVES
```

---

# REQUIRED FIX 1 — REMOVE FAKE START CONTROLS

Kiro found a BLOCKER.

There are currently three UI controls that call:

```text
/api.start
→ POST /arena/start
→ old EvolutionLoop
→ FakeAgent
```

These are reportedly:

1. top-bar `▶ START`
2. command-bar `▶`
3. run-list `+ Start new run`

This is NOT the real co-evolution engine.

It can create fake/deterministic runs and, on a writable Atlas observer, write them beside real evidence.

This must be fixed.

## Frontend

Hide or disable ALL controls that invoke the old FakeAgent `/arena/start` path.

For the demo, the UI must NOT imply that clicking Start launches real co-evolution.

Replace action/tooltip with something truthful such as:

```text
LIVE RUNS START FROM THE CO-EVOLUTION RUNTIME
```

or a disabled state.

Do not add a fake replacement.

## Backend defense-in-depth

Also inspect `/arena/start`.

If safe and small, add a backend guard preventing the FakeAgent/old EvolutionLoop from being started in non-TEST/demo production-like modes.

Conceptually:

```text
FakeAgent start
+
not TEST
→ refuse
```

Use existing architecture/status checks.

Do not break deterministic test fixtures.

Add a focused regression test.

The real live engine remains:

```text
python -m app.coevolution
```

---

# REQUIRED FIX 2 — MAKE HISTORICAL VS LIVE UNMISSABLE

Kiro found that:

```text
Historical vs live distinction: FAIL
Atlas live-state visibility: PARTIAL
```

Fix this.

## Backend

Extend:

```text
/system/status
```

with explicit truthful state such as:

```text
read_only: true/false
persistence_backend: snapshot/mongodb
atlas_connected: true/false
```

Use existing state where available.

Do NOT infer historical status solely from filenames if the repository already knows whether it is read-only.

## Frontend top bar

Show a prominent state chip.

Historical example:

```text
HISTORICAL · READ ONLY
```

Atlas live example:

```text
LIVE · ATLAS CONNECTED
```

Snapshot live/dev example if needed:

```text
LIVE · DEV SNAPSHOT
```

Do not display generic `DEV` as the primary persistence/run-state indicator when that hides the important distinction.

## Product footer

Replace the tiny/unclear:

```text
TARGET MODEL UNCHANGED
```

with:

```text
MODEL WEIGHTS FROZEN · HARNESS EVOLVES
```

If there is room, Red's nature may be clarified elsewhere as:

```text
RED STRATEGY EVOLVES
```

Do not imply that model weights are trained.

---

# REQUIRED FIX 3 — FIX DEMO SCRIPTS AND PORT COLLISIONS

Kiro found the historical scripts can silently show the WRONG RUN.

Current issue:

- Atlas observer may already own `:8000`
- historical script tries `:8000`
- uvicorn fails in background
- health check accidentally talks to existing Atlas observer
- presenter thinks Overnight loaded but actually sees Atlas

This is unacceptable.

## Historical scripts

Update:

```text
scripts/demo-overnight.sh
scripts/demo-two-sided.sh
```

and related launch helpers.

They must:

1. detect if `:8000` is already occupied
2. FAIL LOUDLY rather than silently continuing
3. identify which service/process is using the port where practical
4. never claim a historical run started unless its own backend is healthy
5. use the correct snapshot
6. use historical/read-only mode

## Frontend

Use explicitly:

```bash
npm run dev -- --port 5175 --strictPort
```

because `:5173` belongs to another project.

Do not allow Vite to silently select a random port while the script prints something else.

## Success output

A script should clearly print something like:

```text
DARWINGUARD HISTORICAL DEMO READY

Run:
OVERNIGHT-COEV-20260926-022643

Backend:
http://127.0.0.1:8000

Frontend:
http://127.0.0.1:5175

Mode:
HISTORICAL · READ ONLY
```

Only print READY after checking the correct backend identity/run.

---

# REQUIRED FIX 4 — BLUE ENGINEER MODEL ATTRIBUTION

Kiro found the Blue Engineer subtitle can show Ling even when Nemotron actually authored the patch.

Current problematic logic is around:

```text
frontend/src/lib/viewmodel.ts
```

The subtitle reportedly prefers:

```text
blueVersions[0].base_model
```

which represents the executor model.

That is wrong for the Blue Engineer window.

The Blue Engineer panel must derive its model from the actual successful:

```text
blue_harness_engineer
```

model call for that patch/generation.

Expected current live model:

```text
nvidia/nemotron-3-super-120b-a12b:free
```

Historical patches must remain attributed to:

```text
inclusionai/ling-3.0-flash-fin:free
```

Do NOT rewrite historical metadata.

Add a focused frontend/unit test if the current testing structure supports it cheaply.

---

# PRODUCT/UI REVIEW WHILE TOUCHING THESE FILES

Do NOT redesign the interface.

But while implementing the four fixes, inspect the main canvas in the browser.

We need to ensure the UI communicates the actual harness, not merely looks impressive.

The current Kiro assessment says these already PASS:

```text
October.dev spatial feel
Harness stages represented
Red evolution visible
Blue evolution visible
Attack → sandbox → evaluator causality
Breach → patch → replay → promotion causality
```

Preserve those.

---

# HARNESS OPTIMIZER / AWS JUDGE CONTEXT

One of today's AWS judges specifically highlighted:

- Strands Harness Optimizer
- Strands Agents
- Strands MCP
- context engineering

Do NOT rewrite DarwinGuard on Strands.

The useful conceptual comparison is:

```text
Strands Formula
≈ DarwinGuard harness stages/parameters

Rollouts
≈ DarwinGuard sandbox episodes

RewardFunction
≈ deterministic evaluator

Optimizer step
≈ Blue engineer reading failure traces

Update
≈ HarnessPatch

DarwinGuard difference:
updates are challenged by an adaptive Red population
and can be rejected by deterministic promotion gates
```

Terminology we may safely use in UI/demo language:

```text
harness
rollout
reward
optimizer step
trace-driven
tunable harness components
empirical promotion
```

Do NOT claim DarwinGuard uses Strands internally.

Do NOT add Strands SDK/MCP today.

---

# OPTIONAL V0 USE

We have Vercel v0 credits available.

Do NOT let v0 redesign the application from scratch.

If, after the required fixes, the existing UI still needs a very small visual adjustment:

v0 MAY be used as a design assistant for:

- chip placement
- hierarchy
- top-bar state presentation
- spacing
- labels
- October.dev-like canvas polish

v0 must NOT:

- invent fake backend data
- build a new app
- replace real data bindings
- add fake transitions
- create generic dashboard cards
- change state architecture

Any v0-generated frontend code must be reviewed and wired by OpenCode/DeepSeek.

Do not block the sprint on v0.

---

# WORKER A — UI SAFETY + PRODUCT STATE

Assign Worker A:

```text
Fix:
1. fake START controls
2. historical/live/Atlas status chip
3. MODEL WEIGHTS FROZEN · HARNESS EVOLVES footer
4. Blue Engineer actual model attribution
5. corresponding focused tests
```

Do not touch demo scripts.

Report over October Bus:

```text
FILES
CHANGES
DATA SOURCES
TESTS
SCREEN/BROWSER CHECK
```

---

# WORKER B — DEMO SCRIPT SAFETY

Assign Worker B:

```text
Fix:
1. :8000 collision handling
2. strict :5175 frontend
3. backend identity/run verification
4. truthful READY output
5. overnight launcher
6. two-sided launcher
7. live/Atlas launcher documentation if needed
```

Do not touch frontend product components unless coordination requires it.

Report:

```text
FILES
BEFORE
AFTER
COMMANDS TESTED
PORT COLLISION TEST
RUN ID VERIFICATION
```

---

# ORCHESTRATOR — BACKEND GUARD

The orchestrator or a narrowly delegated worker should inspect whether `/arena/start` can be safely protected against FakeAgent execution outside tests.

Implement only if it is a small defense-in-depth change.

Acceptance:

```text
TEST FakeAgent path:
still usable where expected

historical:
already 409

live Atlas / production-like observer:
cannot launch FakeAgent pretending to be real co-evolution
```

Do not create a second engine entry point.

---

# INTEGRATION

When A and B finish:

1. inspect diffs
2. verify no historical evidence changed
3. verify no secrets
4. run relevant targeted tests
5. integrate carefully
6. do NOT trust worker PASS reports alone

Then run full gates.

---

# FULL TEST GATE

Backend:

```bash
cd backend
uv run pytest -q
uv run mypy app
uv run ruff check app tests
```

Frontend:

```bash
cd frontend
npx tsc -b
npm run build
```

All must pass.

---

# BROWSER VERIFICATION

Actually launch the application.

Verify Overnight:

```text
OVERNIGHT-COEV-20260926-022643
```

Expected:

```text
HISTORICAL · READ ONLY
7 generations
256 calls
Start controls absent/disabled
Ling historical attribution
MODEL WEIGHTS FROZEN · HARNESS EVOLVES
```

Click through:

```text
Red
→ Attack
→ Sandbox
→ Evaluator
→ Blue Engineer
→ HarnessPatch
→ Candidate
→ Replay/Judge
→ Champion
```

Confirm real backend data appears.

---

Verify two-sided:

```text
COEV-SEL-20260926-011123
```

Expected ASR:

```text
0.0
→ 0.333
→ 0.667
→ 0.0
```

Confirm Red and Blue lineage views.

---

Verify Atlas live:

```text
DARWINGUARD-EVENT-20260926
```

Expected:

```text
LIVE · ATLAS CONNECTED
Nemotron engineer attribution
candidate REJECTED on utility floor
```

Do not accidentally start FakeAgent.

---

# INDEPENDENT VERIFIER

After integration, spawn/reuse ONE fresh OpenCode + DeepSeek Flash verifier.

It must independently test:

```text
1. no UI Start control can launch FakeAgent
2. direct unsafe /arena/start is prevented where applicable
3. historical Start/Reset/replay remain 409
4. historical snapshot hashes unchanged
5. historical top bar says HISTORICAL · READ ONLY
6. Atlas run says LIVE · ATLAS CONNECTED
7. Overnight is 7 / 256
8. two-sided ASR is correct
9. historical engineer model is Ling
10. current Atlas/Nemotron engineer model is Nemotron
11. demo scripts fail fast on :8000 collision
12. scripts use :5175 --strictPort
13. pytest passes
14. mypy passes
15. Ruff passes
16. frontend typecheck/build pass
```

Require raw evidence.

---

# SEND RESULTS BACK TO KIRO

After DeepSeek verification passes, use October Bus to notify the connected Kiro review node.

Send a concise evidence packet:

```text
Kiro findings addressed:
1. fake START controls
2. historical/live state
3. demo scripts/ports
4. Blue Engineer attribution

Commit:
<hash>

Tests:
<results>

Browser:
<results>

Please perform a final 10-minute regression review only.
Return APPROVE FOR DEMO or remaining BLOCKER/HIGH findings.
```

Do not ask Kiro to redo the whole audit.

---

# FINAL DEMO REHEARSAL

Once Kiro approves or returns no BLOCKER/HIGH issues:

rehearse this exact flow.

## 1 — Overnight

Start Overnight historical mode.

Open frontend at:

```text
http://localhost:5175
```

Press FIT.

Show:

```text
HISTORICAL · READ ONLY
```

Select G00.

---

## 2 — Red

Show:

```text
RED AGENT
model
strategy
fitness
```

Follow generated edge.

---

## 3 — Breach

Open real attack.

Show BREACH.

Follow to Sandbox.

---

## 4 — Sandbox + evaluator

Show actual execution trace.

Then:

```text
EVALUATOR · BREACH
```

---

## 5 — Blue

Follow breach edge.

Open:

```text
BLUE ENGINEER
```

Historical run should show Ling.

Explain that current shipping primary is Nemotron, but historical attribution is preserved.

---

## 6 — Harness optimization

Open:

```text
HARNESS PATCH
```

Explain:

> The model weights stay frozen. What evolves is the harness.

Show:

- parent
- operations
- candidate

---

## 7 — Empirical selection

Open:

```text
REPLAY / JUDGE
```

Show:

- security
- utility
- fitness
- replay battery
- PROMOTED

---

## 8 — Generations

Move through G01–G06.

Show:

```text
ASR = 0
```

while Red continues mutating.

---

## 9 — Lineage

Open LINEAGE.

Show:

```text
Red ancestry
Blue ancestry
promoted/rejected branches
```

---

## 10 — Two-sided run

Switch to:

```text
COEV-SEL-20260926-011123
```

Show:

```text
0
→ 0.333
→ 0.667
→ 0
```

Explain adaptive pressure in both directions.

---

## 11 — Atlas

Switch to live Atlas evidence.

Show:

```text
LIVE · ATLAS CONNECTED
```

Open current Nemotron patch.

Show that it was rejected on utility.

Explain:

> Security alone doesn't win. A defense has to preserve useful behavior.

---

# SOURCE CONTROL

Create a clean final commit.

Suggested:

```text
fix: make DarwinGuard demo UI truthful and safe
```

or split UI/script changes if cleaner.

Before commit:

- no secrets
- no `.env`
- no historical evidence mutation
- no giant temporary state
- inspect diff

---

# FINAL REPORT

Return:

## TOPOLOGY

```text
orchestrator:
workers:
verifier:
Kiro:
October Bus:
```

## KIRO FIXES

```text
Fake START controls: FIXED / NOT FIXED
Historical/live state chip: FIXED / NOT FIXED
Demo scripts/ports: FIXED / NOT FIXED
Blue Engineer attribution: FIXED / NOT FIXED
```

## UI PRODUCT

```text
October.dev spatial feel:
Harness causality visible:
Red evolution visible:
Blue evolution visible:
Historical/live distinction:
Atlas visibility:
Backend-truth binding:
```

## TESTS

```text
pytest:
mypy:
ruff:
tsc:
build:
```

## DEMO RUNS

```text
Overnight:
Two-sided:
Atlas:
```

## KIRO FINAL REVIEW

```text
APPROVE FOR DEMO / DO NOT DEMO YET
```

## COMMIT

```text
HEAD:
working tree:
historical evidence modified:
secrets committed:
```

Required:

```text
historical evidence modified: NO
secrets committed: NO
```

## FINAL VERDICT

Choose exactly:

```text
READY FOR JUDGES — FREEZE
```

or:

```text
NOT READY
```

If READY:

STOP ALL ENGINEERING.

No more UI changes.
No model changes.
No persistence changes.
No refactoring.

Freeze and rehearse.