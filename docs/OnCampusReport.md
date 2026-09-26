# DarwinGuard — Multi-Agent Spawn Test + Full Current-State Audit

We currently have ONE OpenCode terminal open.

Your job is to prove that this session can use October Bus MCP to spawn and coordinate multiple additional OpenCode agents, with ALL spawned workers using DeepSeek Flash through the DeepSeek provider.

This is primarily an AUDIT.

Do NOT implement fixes yet.
Do NOT refactor DarwinGuard.
Do NOT modify historical experiment evidence.
Do NOT use Claude.
Do NOT use Codex.
Do NOT use Kiro for this task.

Kiro is reserved for later high-level review if needed.

---

# PHASE 0 — VERIFY THE CURRENT ORCHESTRATOR

Before spawning anything, report:

- current terminal/session ID
- current agent identity
- current provider
- current model
- workspace path
- git HEAD
- working-tree state
- October Bus MCP connected: YES/NO

This current terminal is the ORCHESTRATOR.

Do not turn it into a worker.

---

# PHASE 1 — TEST MULTI-AGENT SPAWNING

Use the existing October Bus MCP child-terminal functionality.

The previous audit showed tools such as:

- `add_terminal`
- `list_peers`
- `list_canvas`
- `message_peer`
- `add_task`
- `claim_task`
- `complete_task`
- `get_node_status`
- `wait_for_nodes`

Use the REAL registered tool names available in this session.

Do not invent APIs if names differ.

## Spawn exactly 4 OpenCode worker terminals

Name/role them approximately:

1. `repo-auditor`
2. `runtime-auditor`
3. `demo-ui-auditor`
4. `independent-verifier`

Every worker must use:

Provider:
`deepseek`

Model:
the configured DeepSeek Flash model currently available through OpenCode.

Do NOT allow automatic fallback to:
- Claude
- Codex
- GPT
- Kiro
- Gemini

If model selection is inherited from the parent, verify the inherited provider/model.

If OpenCode exposes explicit provider/model arguments when spawning, set them.

---

# PHASE 2 — PROVE THEY ARE ACTUALLY ALIVE

Before assigning real work, test communication with every worker.

For each child:

1. verify the node/terminal appears on October Bus
2. verify status is alive/ready
3. send a correlated request:

`Reply with your terminal ID, provider, model, cwd, and the word BUS_READY.`

4. wait for the correlated response
5. verify the response came from the intended child

Do NOT accept a worker as healthy just because a terminal exists.

Build:

| Worker | Terminal ID | Provider | Model | Bus request/reply | Status |
|---|---|---|---|---|---|

All four should report DeepSeek Flash.

If any worker launches under another provider/model:

STOP that worker and respawn correctly.

Do not proceed with an incorrectly routed model.

---

# PHASE 3 — TEST THE OCTOBER BUS TASK BOARD

Create four independent tasks on the shared task board.

Each task should have:

- clear owner role
- narrow scope
- no overlapping write ownership
- acceptance criteria
- report destination = orchestrator

Have each child claim its own task.

This is intentionally testing:

OpenCode orchestrator
→ October Bus
→ child claims work
→ child performs work
→ child sends evidence
→ child completes task
→ orchestrator receives result

Use correlated Bus request/response for the final report too.

---

# WORKER 1 — REPOSITORY / CODEBASE AUDIT

Role:
`repo-auditor`

READ-ONLY.

Determine the CURRENT repository state.

Inspect:

- current HEAD
- recent commits since `a4a2b87`
- branches/worktrees
- uncommitted changes
- staged changes
- untracked source files
- configuration changes
- TODO/FIXME markers relevant to demo readiness
- latest current-state Markdown
- whether historical reports still exist
- whether experiment evidence is intact

Run:

- full pytest
- mypy
- Ruff

If frontend has its own checks, leave those to worker 3.

Report:

### REPO
HEAD:
clean/dirty:
recent important commits:

### TESTS
pytest:
mypy:
ruff:

### IMPLEMENTED
What major DarwinGuard systems are currently present and working.

### KNOWN CODE ISSUES
Only issues supported by current code/tests.

Do NOT fix anything.

---

# WORKER 2 — RUNTIME / MODEL / CO-EVOLUTION AUDIT

Role:
`runtime-auditor`

READ-ONLY except harmless network/model probes.

Verify the actual current runtime configuration.

Check:

## Red

Expected:

`qwen3.8-flash-next-heretic2`

through the AI rig.

Verify:
- Tailscale reachability
- endpoint
- model present
- REAL origin guard
- one harmless readiness completion
- reasoning-token fix still active

Do NOT run another soak.

## Blue

Verify actual configuration:

Executor:
`inclusionai/ling-3.0-flash-fin:free`

Engineer primary:
`nvidia/nemotron-3-super-120b-a12b:free`

Engineer fallback:
`inclusionai/ling-3.0-flash-fin:free`

Verify provider reachability only.

## Core loop

Trace current code for:

Red
→ attack
→ sandbox
→ evaluator
→ Red selection
→ Blue patch
→ candidate
→ replay
→ promotion/rejection
→ next generation

Confirm whether each path is still wired.

Check persisted REAL runs:

- `OVERNIGHT-COEV-20260926-022643`
- `COEV-SEL2-20260926-013728`
- `COEV-SEL-20260926-011123`

Do not modify them.

Report:

| Component | WORKING / PARTIAL / BROKEN / NOT TESTED | Evidence |

Also report current:
- Red model
- Blue executor
- Blue engineer primary/fallback
- persistence backend
- Atlas status

Do NOT implement anything.

---

# WORKER 3 — DEMO / FRONTEND / PERSISTENCE AUDIT

Role:
`demo-ui-auditor`

READ-ONLY.

Inspect the frontend and demo workflow.

Run:

- TypeScript check
- frontend build

Determine:

## Historical evidence

Can the UI load:

`OVERNIGHT-COEV-20260926-022643`

and:

`COEV-SEL-20260926-011123`

without corrupting them?

## Observer write hazard

The previous audit said historical snapshots could still be modified if Start was clicked.

Determine CURRENT truth:

- FIXED
- STILL PRESENT
- PARTIAL
- UNVERIFIED

Trace code; do not guess.

## Live-state isolation

Determine whether:

historical state
and
fresh live state

are now safely separated.

## UI truthfulness

Verify the UI obtains from backend/persistence rather than fabricating:

- Red champion
- Blue champion
- ASR
- mutation decisions
- patch decisions
- model attribution
- lineage

## Persistence

Report current persistence mode:

- DEV snapshot
- local Mongo
- Atlas
- other

Do not pretend Atlas exists if it does not.

Report:

### FRONTEND
build:
typecheck:

### HISTORICAL RUNS
overnight:
two-sided:

### OBSERVER SAFETY
status:

### LIVE/HISTORICAL ISOLATION
status:

### DEMO BLOCKERS
evidence-backed only.

Do NOT fix anything.

---

# WORKER 4 — INDEPENDENT VERIFIER

Role:
`independent-verifier`

This worker is not allowed to simply repeat previous Markdown claims.

Its job is to independently establish the current state from code, tests, configuration, and persisted evidence.

READ-ONLY.

Focus on inconsistencies between:

- repository code
- current configuration
- recent reports
- persisted runs
- other workers' likely conclusions

Independently answer:

1. Does Red genuinely evolve under empirical selection?
2. Does Blue genuinely evolve under empirical selection?
3. Do both champions feed the next generation?
4. Are historical runs authentic and internally consistent?
5. Is the current model stack what we think it is?
6. Are there stranded/incomplete candidates?
7. Can a resumed run duplicate generation-boundary work?
8. Is the demo safe to operate?
9. What are the 3 most important things still incomplete?

Do NOT modify anything.

After the other workers report, the orchestrator may send this verifier their summaries and ask it to challenge any unsupported claims.

---

# PHASE 4 — ORCHESTRATOR INTEGRATION

The main OpenCode terminal must remain the integrator.

Do not blindly concatenate worker reports.

Compare them.

For any contradiction:

1. identify the exact disputed claim
2. ask the relevant workers for evidence over October Bus
3. if necessary, ask the independent verifier to resolve it
4. use tests/code/persisted state as authority

Do not resolve disagreements by majority vote.

Evidence wins.

---

# PHASE 5 — MULTI-AGENT CAPABILITY REPORT

Before discussing DarwinGuard itself, report whether the agent spawning test succeeded.

Return:

## MULTI-AGENT TEST

October Bus connected:
YES / NO

Spawn requested:
4

Spawn succeeded:
N / 4

DeepSeek provider correct:
N / 4

DeepSeek Flash model correct:
N / 4

Bus correlated request/reply:
N / 4

Task claiming:
N / 4

Task completion:
N / 4

Average spawn-to-ready time:

### Agent table

| Agent | Terminal | Provider | Model | Bus | Task | Result |
|---|---|---|---|---|---|---|

If this fails, tell me exactly where:
- terminal creation
- model routing
- Bus delivery
- task claim
- response correlation
- workspace access

---

# PHASE 6 — CURRENT DARWINGUARD STATE

Produce one authoritative status table:

| System | Status | Evidence | Remaining work |
|---|---|---|---|

Include at minimum:

- repository
- tests
- Red provider
- reasoning-token handling
- Red empirical evolution
- sandbox
- evaluator
- Blue executor
- Blue engineer
- HarnessPatch
- candidate compilation
- replay/regression
- Blue promotion
- next-generation inheritance
- persistence
- historical run loading
- resume/recovery
- observer read-only safety
- frontend
- October Bus
- AI rig
- demo launch path

Use:

`WORKING`
`PARTIAL`
`BROKEN`
`NOT TESTED`

Do not use vague language.

---

# PHASE 7 — WHAT IS ACTUALLY DONE

Give a concise list titled:

## DONE

Only include features independently supported by evidence.

Do not list planned features.

---

# PHASE 8 — WHAT ACTUALLY REMAINS

Give:

## REMAINING

Rank remaining items:

`P0`
`P1`
`P2`

Maximum 10 items total.

P0 means:
could materially break or embarrass the demo.

P1 means:
important but demo can survive.

P2 means:
post-demo improvement.

Do not invent work merely to keep agents busy.

---

# PHASE 9 — RECOMMEND THE NEXT MOVE

Give exactly:

## NEXT 3 ACTIONS

1.
2.
3.

These should be the highest-value next steps based on the current system.

Do NOT implement them yet.

I will decide what we do next.

---

# IMPORTANT OPERATING RULES

- No Claude.
- No Codex.
- No Kiro during this test.
- All spawned workers = OpenCode + DeepSeek Flash.
- Use October Bus for assignment and reporting.
- No code changes.
- No commits.
- No cleanup.
- No historical evidence mutation.
- No long-running co-evolution experiment.
- Harmless provider/readiness probes are allowed.
- Tests/builds are allowed.
- Every significant claim needs concrete evidence.

The purpose of this run is:

1. prove that we can dynamically create and coordinate a DeepSeek/OpenCode swarm through October Bus;
2. establish the authoritative CURRENT state of DarwinGuard;
3. tell me what remains before we touch anything else.