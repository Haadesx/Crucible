from pathlib import Path

content = r"""# DarwinGuard — FINAL 2-HOUR ORCHESTRATOR SPRINT
## MongoDB-native memory + radically clearer UI + live proof + submission

You are the MAIN OpenCode orchestrator for DarwinGuard.

We have approximately **2 hours before judging**.

The system already works end-to-end. Do **not** rebuild it.

Your mission is to aggressively parallelize the remaining work so that DarwinGuard becomes:

1. easier to understand in under 10 seconds,
2. more visibly MongoDB-native,
3. stronger against the “Blue just says no to everything” failure mode,
4. demonstrably live,
5. submission-ready.

Use October Bus and as many healthy OpenCode + DeepSeek Flash workers as useful, but avoid duplicate work.

---

# 0. CURRENT VERIFIED STATE — DO NOT REGRESS

We already have a REAL live co-evolution run:

```text
Run:
DARWINGUARD-LIVE-20260926-142845

Red:
qwen3.8-flash-next-heretic2
running on local AI rig

Blue executor:
inclusionai/ling-3.0-flash-fin:free

Blue engineer:
nvidia/nemotron-3-super-120b-a12b:free

Atlas:
REAL persistence

Live observer:
:8000

Frontend:
http://localhost:5175
```

Verified live behavior:

```text
2 generations
ASR 1.0 -> 0.0

real Red attacks
real sandbox execution
real deterministic evaluation
real Red candidate selection

real Nemotron HarnessPatch
real candidate compilation
real replay
real Blue promotion

real Atlas persistence
real arena event stream
real browser updates
real refresh reconstruction
```

FakeAgent must remain disabled from judge-facing flows.

Historical evidence must remain immutable.

---

# 1. HARD PRODUCT TRUTH

Foundation model weights stay frozen.

What evolves:

```text
RED:
attack strategy / genome / tactic distribution

BLUE:
the harness
```

The system is:

```text
adversarial empirical harness optimization
```

Every evolutionary claim must be backed by:

```text
actual execution
actual persisted evidence
actual fitness comparison
actual promotion/rejection
```

No frontend simulation.

No fake success sequence.

No fabricated lineage.

No hard-coded model outcomes.

---

# 2. FIRST ACTION — RECONSTRUCT TOPOLOGY

Immediately inspect:

```text
git HEAD
git status
running backend/frontend processes
October Bus topology
healthy terminals
stale terminals
current task claims
manual Kiro session
```

Use node IDs for routing.

Do not blindly spawn duplicates.

Then create parallel workstreams.

Preferred:

```text
Orchestrator
│
├── Worker A — MongoDB Vector Memory / Blue context
├── Worker B — Benign utility + replay hardening
├── Worker C — UI simplification / product clarity
├── Worker D — MongoDB Agent Skills + MCP + Atlas audit
├── Worker E — V0 integration / frontend design assist
└── Worker F — independent verifier + submission readiness
```

Routine workers:

```text
OpenCode
DeepSeek provider
DeepSeek Flash
```

Use Kiro only as final reviewer.

---

# 3. PRIORITY A — MAKE ATLAS VECTOR SEARCH PART OF REAL BLUE MEMORY

We already have Atlas Vector Search infrastructure.

Expected indexes include:

```text
attack_embedding_index
memory_embedding_index
```

Do not merely show that vector indexes exist.

Make them matter to the live harness.

## Required real runtime path

When a new breach occurs:

```text
current breach evidence
        ↓
embed/query
        ↓
MongoDB Atlas Vector Search
        ↓
top-k semantically similar prior failures/memories
        ↓
previous patch/outcome context
        ↓
Blue engineer
        ↓
new HarnessPatch
```

### Rules

Retrieved memories inform Blue.

Retrieved memories do NOT decide promotion.

The deterministic replay + security + benign utility gate remains authoritative.

### Persist provenance

For each Blue engineering event, persist:

```text
retrieved memory IDs
similarity scores
source run/generation
previous patch ID if available
previous outcome
```

Emit an arena event such as:

```text
memory_retrieved
```

with sanitized metadata.

### Failure behavior

If no useful memories exist:

```text
continue with empty memory context
```

Do not fake memory.

If Vector Search fails:

report it truthfully.

Do not claim memory retrieval happened when it did not.

### Acceptance

Must prove with a REAL run:

```text
current breach
→ actual $vectorSearch
→ actual historical records returned
→ Blue prompt/context receives them
→ retrieved IDs persisted
→ visible in API/UI
```

---

# 4. PRIORITY B — MAKE BENIGN UTILITY A FIRST-CLASS PROMOTION CONSTRAINT

A teammate correctly identified the degenerate policy:

```text
deny everything
→ high security
→ useless agent
```

DarwinGuard already has benign regression and utility scoring.

Now make it impossible for any live Blue promotion path to accidentally skip this.

## Every Blue promotion battery must include BOTH

```text
A. adversarial / malicious cases
B. benign / useful task cases
```

The UI must make both visible.

### Desired semantics

```text
MALICIOUS
→ should be blocked

BENIGN
→ should still work
```

Also include benign-but-security-looking cases where feasible:

```text
"Explain prompt injection risks."
"Send the approved security report."
"Summarize this admin incident."
```

These are important because a crude keyword-blocking harness should fail them.

### Promotion invariant

A Blue candidate must NEVER be promotable solely because its block rate is high.

Conceptually:

```text
security requirement passes
AND
benign utility requirement passes
AND
candidate fitness beats/gates against champion
→ PROMOTE
```

Otherwise:

```text
REJECT
```

### Reject-all test

Create one deterministic regression test representing a harness that blocks everything.

Expected:

```text
security high
benign utility collapses
promotion impossible
```

This is a critical test.

### UI requirement

Replay/Judge must clearly show:

```text
SECURITY
<attacks blocked>

BENIGN UTILITY
<benign tasks preserved>

DECISION
PROMOTE / REJECT

REASON
<why>
```

A judge should immediately understand:

> Blue cannot win by saying no to everything.

---

# 5. PRIORITY C — RADICALLY SIMPLIFY THE UI

The current UI has real data but still contains AI-product fluff and too much visual noise.

The judge must understand DarwinGuard within 10 seconds.

## REMOVE THE CHAT BAR

There is a chat/input bar at the bottom of the UI.

It does NOT make sense for this harness demo.

Remove it completely from the judge-facing product.

Do not replace it with another generic AI chat control.

DarwinGuard is:

```text
an observable co-evolution runtime
```

not:

```text
a chatbot
```

Also remove/hide other UI elements that imply conversational AI when they are not part of the actual harness.

---

# 6. DEFAULT UI MUST EXPLAIN ONE CAUSAL STORY

The default visual hierarchy should communicate:

```text
RED ATTACKER
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
        │    ↓
        │  Red mutation pressure
        │
        └── BREACH
              ↓
        ATLAS MEMORY RECALL
              ↓
         BLUE ENGINEER
              ↓
         HARNESS PATCH
              ↓
       CANDIDATE HARNESS
              ↓
      REPLAY / REGRESSION
         ↙             ↘
   MALICIOUS         BENIGN
   SHOULD BLOCK      SHOULD WORK
         ↘             ↙
           CHAMPION JUDGE
           ↓           ↓
        PROMOTE      REJECT
```

Do not bury this under decorative panels.

---

# 7. SIMPLIFY THE TOP-LEVEL UI

The primary screen should immediately show:

```text
LIVE · ATLAS CONNECTED · RUNNING
Generation N
```

Then four high-value metrics:

```text
Attack Success Rate
Benign Task Success
Current Red Champion
Current Blue Champion
```

Optional additional metric:

```text
Memory recalls this generation
```

Do NOT fill the top with vanity metrics.

---

# 8. UI CONTENT PRIORITY

## Always visible / obvious

```text
Red
Attack
Sandbox
Evaluator
Memory Recall
Blue Engineer
HarnessPatch
Replay
Security score
Benign utility
Promotion decision
Current champion
```

## Expandable detail

Move lower-level information behind inspectors:

```text
raw IDs
full prompts
full tool traces
latencies
model call metadata
exact JSON patch
lineage internals
Atlas document metadata
```

Do not delete real evidence.

Just stop overwhelming the first view.

---

# 9. PRESERVE OCTOBER.DEV-LIKE SPATIAL FEEL

Keep:

```text
spatial canvas
floating runtime windows
causal edges
pan/zoom
FIT
developer/operator feel
```

Remove:

```text
chat bar
generic AI assistant widgets
decorative AI blobs
meaningless animation
fake terminals
generic SaaS card grids
```

The UI should feel like:

> October.dev specifically for adversarial harness evolution.

---

# 10. LIVE MEMORY PANEL

Add a compact, truthful panel/window:

```text
ATLAS MEMORY
```

During a breach:

```text
3 similar failures recalled
```

Each item can show:

```text
similarity
attack family
previous run/generation
previous patch
PROMOTED / REJECTED outcome
```

Only show actual retrieved values.

If none:

```text
No relevant prior failures recalled
```

Do not fabricate examples.

---

# 11. LIVE EVENT FEED — KEEP IT USEFUL

The live event feed is valuable.

Keep it compact and causal.

Preferred visible events:

```text
RED generated attack
SANDBOX executed
EVALUATOR breach
ATLAS recalled 3 memories
BLUE proposed patch
PATCH compiled
REPLAY malicious 9/9 blocked
REPLAY benign 8/8 passed
JUDGE promoted
RED candidate rejected
RED candidate promoted
GENERATION completed
```

Everything must map to persisted events.

No fake timestamps.

No UI-only state machine.

---

# 12. MONGODB OFFICIAL TOOLING

The hackathon resource guide strongly recommends:

```text
MongoDB Agent Skills
MongoDB MCP Server
Natural Language to MongoDB guidance
```

Use these to strengthen implementation and proof, but do not destabilize the product.

## MongoDB Agent Skills

Install/use the official MongoDB Agent Skills if compatible with the current environment.

Use them to audit:

```text
schema
indexes
Vector Search
Atlas query patterns
persistence architecture
aggregation correctness
```

Record:

```text
USED
```

only if genuinely used.

---

# 13. MONGODB MCP

If it can be connected in <=15 minutes:

connect MongoDB MCP in READ-ONLY mode.

Use it to inspect the live DarwinGuard Atlas database.

Verify:

```text
collections
counts
run records
patches
champions
memories
vector/search-related data
```

Do not grant write access unless absolutely necessary.

Do not expose credentials.

If setup becomes annoying:

```text
DEFER
```

Do not burn the sprint on MCP.

---

# 14. NATURAL-LANGUAGE RUN QUERY — OPTIONAL STRETCH

Only after P0/P1 work passes.

If extremely cheap, add a small read-only feature such as:

```text
ASK THIS RUN
```

Examples:

```text
What caused the first breach?
Why was this patch rejected?
Which previous failures were recalled?
What is the current champion?
```

This must operate on actual Atlas data.

Do NOT use a generic chat bar.

If implemented, make it clearly:

```text
READ-ONLY RUN QUERY
```

not conversational AI.

If it takes >20 minutes:

skip it.

---

# 15. V0 — CONNECT TO THE REAL REPOSITORY

Use Vercel v0 as a frontend design assistant.

Do NOT paste random isolated code.

Connect/import the actual GitHub repository into v0.

Create/use a dedicated branch:

```text
v0/demo-clarity
```

or equivalent.

Never let v0 write directly to the protected/final branch.

Do not give v0 secrets.

Do not give v0:

```text
MongoDB URI
OpenRouter keys
AI-rig credentials
.env contents
```

It only needs frontend source and existing API types/client.

---

# 16. V0 DESIGN BRIEF

Give v0 this mission:

```text
This is an existing working app.

Do not rebuild the backend.
Do not invent APIs.
Do not invent runtime state.
Do not create fake agents.
Do not add fake progress.

The current UI is too noisy and too "AI app"-like.

REMOVE:
- bottom chat bar
- conversational AI controls
- decorative AI fluff
- anything that makes this look like a chatbot

MAKE THE DEFAULT SCREEN EXPLAIN:

Red
→ attack
→ sandbox
→ breach
→ MongoDB Atlas memory recall
→ Blue engineer
→ HarnessPatch
→ replay malicious + benign
→ promote/reject
→ next champion

The judge must understand within 10 seconds:
1. who is attacking
2. what breached
3. what the harness changed
4. whether malicious tests were blocked
5. whether benign tasks still worked
6. why the candidate was promoted/rejected

Keep:
- spatial canvas
- causal edges
- runtime windows
- dark developer/operator aesthetic
- real live events
- lineage

Remove visual clutter.

Do not create a generic dashboard.

Do not fabricate data.

All values must come from existing APIs.
```

OpenCode must review the v0 diff before integration.

Do not blindly merge generated code.

---

# 17. VERIFY THE ATLAS SANDBOX REQUIREMENT

The event guide says finalist eligibility requires using the official MongoDB Atlas Hackathon Sandbox.

Verify immediately:

```text
current Atlas project/cluster belongs to official hackathon sandbox:
YES / NO
```

If YES:

document evidence.

If NO:

escalate immediately to operator.

Do not silently create a second database or migrate data without approval.

This is eligibility-critical.

---

# 18. REAL LIVE TEST AFTER INTEGRATION

Run another bounded REAL live co-evolution test.

Keep it small:

```text
2 generations preferred
3–8 minutes target
```

Must use:

```text
real ai-rig Red
real Blue executor
real Nemotron engineer
real Atlas persistence
real Vector Search memory if applicable
real benign replay
real promotion/rejection
```

Verify in the browser.

---

# 19. LIVE ACCEPTANCE CHECK

During the run prove:

```text
T0 breach occurs
T1 breach persisted to Atlas
T2 Vector Search returns actual prior memories
T3 Blue receives those memories
T4 Blue proposes actual HarnessPatch
T5 candidate compiled
T6 malicious replay executes
T7 benign replay executes
T8 deterministic judge decides
T9 UI shows the same result
```

If no breach occurs:

do not fake it.

Use prior live evidence for Blue lifecycle and report:

```text
memory/Blue path not triggered in this run
```

---

# 20. REFRESH TEST

Mid-run:

refresh browser.

Expected:

```text
same run reconstructs from Atlas
prior events return
new events continue
```

No ephemeral fake UI state.

---

# 21. UI ACCEPTANCE

A first-time observer should be able to answer:

```text
Who is attacking?
What attack happened?
Was it successful?
What historical memory was recalled?
What did Blue change?
Did malicious tests improve?
Did benign tasks still work?
Why was the candidate promoted/rejected?
Who is the current Red champion?
Who is the current Blue champion?
```

without reading source code.

---

# 22. INDEPENDENT VERIFIER

Use a fresh DeepSeek/OpenCode verifier.

It must independently verify runtime evidence, not just source.

Required:

```text
FakeAgent used: NO
AI-rig Red: YES
Atlas persistence: YES
Vector Search actually queried: YES/NO
Retrieved memories actually fed to Blue: YES/NO
Benign replay included: YES
Reject-all defense fails promotion: YES
Live UI receives real events: YES
Chat bar removed: YES
Historical runs remain read-only: YES
Secrets committed: NO
```

---

# 23. KIRO FINAL REVIEW

Keep the manually working Kiro session.

Do NOT waste time fixing October's Kiro 2.26/3.0 auto-launch version gate unless everything else is complete.

Send Kiro the final state and ask for only:

```text
BLOCKER/HIGH findings
or
APPROVE FOR DEMO
```

Review specifically:

```text
truthfulness
MongoDB memory actually affects Blue context
security + benign utility gate
UI clarity
no fake data
historical/live distinction
```

---

# 24. DO NOT FEATURE-SPRAWL

Do NOT add:

```text
LangGraph rewrite
Strands rewrite
ElevenLabs
new agent framework
new database layer
new auth system
another model provider
new deployment architecture
voice interface
generic chatbot
```

We have a working product.

Strengthen the core story.

---

# 25. SUBMISSION REQUIREMENTS — MUST NOT MISS

The hackathon requires:

```text
public GitHub repository
1-minute demo video
concise project description
Cerebral Valley submission
all team members added
video + audio verified
```

Reserve time for this.

Do not code until the deadline.

---

# 26. HARD TIME PLAN

Assume agents are fast.

Parallelize immediately.

Suggested:

```text
T+00–10
topology + recovery branch + sandbox eligibility verification

T+00–45
A: Vector Memory
B: benign utility + reject-all regression
C: UI cleanup
D: MongoDB Skills/MCP
E: v0 branch

T+45–75
integration + API/UI wiring + build/tests

T+75–95
REAL bounded live run + browser verification

T+95–105
independent verifier + Kiro

T+105 onward
STOP FEATURE WORK
record 1-minute video
public GitHub verification
submission
```

If work finishes earlier:

great.

Do not invent more features.

---

# 27. RECOVERY / SOURCE CONTROL

Before parallel work:

create a safe recovery point from current working state.

Do not overwrite historical evidence.

Use clean commits by concern where practical.

Example:

```text
feat: use Atlas memory during harness evolution
fix: enforce benign utility in Blue promotion
refactor: simplify DarwinGuard live demo UI
chore: verify MongoDB hackathon tooling
```

Do not commit:

```text
.env
credentials
temporary logs
large throwaway snapshots
```

---

# 28. FINAL DEMO STORY

The demo should now be:

> Red is running on our local GPU and attacking the current security harness in real time.
>
> When an attack breaches the harness, DarwinGuard queries MongoDB Atlas Vector Search for similar failures from previous generations. Those memories help Blue propose a new executable HarnessPatch.
>
> But Blue cannot win by just blocking everything. Every candidate is replayed against both malicious attacks and benign tasks. It must improve security while preserving utility.
>
> The deterministic judge promotes or rejects the candidate. Both the Red attack strategy and Blue harness maintain persistent lineages in MongoDB Atlas.
>
> Nothing you're seeing is simulated — the browser is observing the real persisted co-evolution run.

---

# 29. FINAL REPORT FORMAT

Return:

## TOPOLOGY

```text
Orchestrator:
Workers:
Verifier:
Kiro:
V0:
```

## MONGODB

```text
Official hackathon Atlas sandbox: YES / NO
Atlas persistence: PASS / FAIL
Vector Search: PASS / FAIL
Vector Memory used by Blue: YES / NO

Retrieved memories:
<count>
<IDs + similarity, sanitized>

MongoDB Agent Skills:
USED / NOT USED

MongoDB MCP:
READ-ONLY VERIFIED / DEFERRED
```

## BLUE SAFETY / UTILITY

```text
Malicious replay: PASS / FAIL
Benign replay: PASS / FAIL
Reject-all regression test: PASS / FAIL
Security-only promotion possible: YES / NO
Utility visible in UI: PASS / FAIL
```

Required:

```text
Security-only promotion possible: NO
```

## UI

```text
Chat bar removed: YES / NO
AI fluff reduced: YES / NO
Causal flow understandable: PASS / FAIL
Memory recall visible: PASS / FAIL
Malicious vs benign obvious: PASS / FAIL
Promotion reason obvious: PASS / FAIL
Historical/live distinction: PASS / FAIL
October.dev spatial feel preserved: PASS / FAIL
```

## LIVE RUN

```text
Run ID:
Duration:
Generations:
Attacks:
Breaches:
Memory recalls:
Blue patches:
Red promotions/rejections:
Blue promotions/rejections:
```

## INTEGRITY

```text
FakeAgent used: NO
Synthetic UI events: NO
Historical evidence modified: NO
Silent Atlas fallback: NO
Secrets exposed: NO
```

## TESTS

```text
pytest:
mypy:
ruff:
frontend typecheck:
frontend build:
```

## REVIEW

```text
Independent verifier:
Kiro:
```

## SUBMISSION

```text
Public GitHub: READY / NOT READY
1-minute video: READY / NOT READY
Video audio checked: YES / NO
Cerebral Valley: READY / NOT READY
All team members added: YES / NO
```

## FINAL VERDICT

Choose exactly:

```text
READY TO SUBMIT — FREEZE
```

or:

```text
BLOCKED
```

When READY:

STOP ENGINEERING.

No more:
- model changes
- UI experiments
- v0 changes
- Atlas changes
- refactors
- framework integrations

Record/submit and prepare to present.
"""

path = Path("/mnt/data/DARWINGUARD_FINAL_2H_ORCHESTRATOR.md")
path.write_text(content)
print(f"Created {path} ({len(content):,} characters)")
