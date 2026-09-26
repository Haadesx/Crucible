# DarwinGuard — ADD LIVE CO-EVOLUTION DEMO MODE
## Real AI-rig Red Team → Real Blue Response → Real Selection → Live Browser Feed

Add one final capability to the existing final-demo mission:

I want to SEE DarwinGuard genuinely operating live.

Not a replay.
Not FakeAgent.
Not frontend animation.
Not a deterministic demo loop.
Not hard-coded events.

I want:

```text
REAL Red model on my AI rig
        ↓
real attacks
        ↓
real sandbox execution
        ↓
real deterministic evaluation
        ↓
real Red empirical selection
        ↓
real Blue engineer
        ↓
real HarnessPatch
        ↓
real candidate harness
        ↓
real replay/regression
        ↓
real PROMOTE / REJECT
        ↓
next generation
```

while the browser at:

```text
http://localhost:5175
```

updates as that run progresses.

This becomes the fourth demo mode:

```text
1. Overnight historical evidence
2. Two-sided historical evidence
3. Existing Atlas event evidence
4. REAL LIVE CO-EVOLUTION
```

Do not compromise the first three while adding the fourth.

---

# IMPORTANT SEMANTICS

Do NOT tell the UI or judges that model weights themselves are being trained.

The truthful description is:

```text
RED:
foundation model weights frozen
strategy/genome/tactic distribution evolves empirically

BLUE:
foundation model weights frozen
security harness evolves through executable HarnessPatch candidates

BOTH:
candidate descendants compete against their current parent/champion
promotion is based on measured outcomes
```

The judge-facing phrase remains:

```text
MODEL WEIGHTS FROZEN · HARNESS + ADVERSARIAL STRATEGY EVOLVE
```

---

# REAL RED MODEL

The Red attacker MUST come from the actual local AI rig.

Expected endpoint:

```text
http://ai-rig.tail6d5242.ts.net:11500/v1
```

Expected model:

```text
qwen3.8-flash-next-heretic2
```

Before starting the run, verify:

```bash
tailscale ping ai-rig
```

and verify the model endpoint responds.

Do NOT silently substitute another Red model.

If the AI rig is unavailable:

```text
LIVE REAL RUN: BLOCKED
```

Do not fall back to FakeAgent.

---

# REAL BLUE STACK

Keep the shipping stack:

```text
Blue executor:
inclusionai/ling-3.0-flash-fin:free

Blue engineer primary:
nvidia/nemotron-3-super-120b-a12b:free

Blue engineer fallback:
inclusionai/ling-3.0-flash-fin:free
```

Fallback must remain truthful and visible in evidence.

If Ling fallback authors a patch, display Ling.

If Nemotron authors it, display Nemotron.

---

# PERSISTENCE

The live run MUST use:

```text
MongoDB Atlas
```

Use a fresh unique run ID such as:

```text
DARWINGUARD-LIVE-<timestamp>
```

Do NOT write into:

```text
OVERNIGHT-COEV-20260926-022643
COEV-SEL-20260926-011123
DARWINGUARD-EVENT-20260926
```

Historical evidence remains immutable.

The live run must persist at minimum the existing architecture's:

```text
run state
generations
Red versions
Blue versions
attacks
attack candidates
episodes
sandbox/evaluator results
model calls
HarnessPatch records
candidate harnesses
replay results
promotion/rejection decisions
champion pointers
arena events
run report/state
```

No silent JSON fallback.

If Atlas becomes unavailable:

```text
FAIL CLOSED
```

---

# DO NOT USE /arena/start

The old:

```text
POST /arena/start
```

FakeAgent/EvolutionLoop path remains disabled.

The real co-evolution engine remains the authoritative execution path:

```text
python -m app.coevolution
```

Do not resurrect the fake Start button.

If we expose a UI action at all, it may only invoke/control the REAL engine through a clearly separated real-runtime path.

But that is OPTIONAL.

For today's demo, starting the real runtime from a terminal is perfectly acceptable.

The browser's job is to OBSERVE it live.

---

# FIRST — INSPECT THE REAL ENGINE

Before changing anything, inspect:

```text
app.coevolution
current CLI args
event persistence
generation lifecycle
Atlas repository
frontend polling/data loading
arena_events
run status representation
```

Determine exactly how the real engine currently emits state.

Do not invent new architecture if the necessary information already exists.

---

# LIVE FEED REQUIREMENT

I want the frontend to visibly change WHILE the real process is running.

For example, as events occur I should see:

```text
LIVE · ATLAS CONNECTED
RUNNING

Generation 0

Red generating attack…
Attack candidate created…
Executing in sandbox…
Evaluator: BREACH
Red candidate fitness updated…

Blue engineer analyzing breach…
HarnessPatch generated…
Candidate compiled…
Replay 1/9…
Replay 2/9…
...
Candidate PROMOTED

Generation 1

New Red parent…
New Blue champion…
...
```

These messages must derive from ACTUAL persisted/runtime events.

No fake timers.

No synthetic transitions.

No frontend-generated outcomes.

---

# IMPLEMENT LIVE OBSERVATION USING THE SMALLEST SAFE METHOD

First look for an existing mechanism:

```text
arena_events
event API
change stream
SSE
websocket
pollable run state
generation endpoints
model_call endpoints
```

Prefer existing infrastructure.

## Preferred order

Use, in order of preference:

```text
1. existing event stream
2. existing Mongo/change-stream plumbing
3. lightweight API polling of persisted event/state records
```

Do NOT build a complicated realtime framework today.

If simple polling every approximately:

```text
1–2 seconds
```

is sufficient, that is acceptable.

Correctness matters more than fancy realtime transport.

---

# LIVE CANVAS BEHAVIOR

The existing October.dev-like spatial canvas should stay.

As real records arrive:

```text
Red window
Attack window
Sandbox window
Evaluator window
Blue Engineer window
HarnessPatch window
Candidate window
Replay/Judge window
Champion window
```

should populate/update from actual backend records.

New windows/edges should appear only when corresponding evidence exists.

Do not pre-create fake future steps.

---

# LIVE EVENT FEED

If the existing UI has a suitable log/event region, use it.

Otherwise add the smallest possible inspectable live event feed.

Example:

```text
14:31:04  RED       attack candidate R…A2 generated
14:31:07  SANDBOX   6 proposed / 1 executed
14:31:07  EVALUATOR BREACH
14:31:10  RED EVO   candidate fitness 0.421 > parent 0.337
14:31:10  RED EVO   PROMOTED
14:31:18  BLUE      Nemotron analyzing breach
14:31:33  PATCH     PATCH-G00-1 validated
14:31:34  REPLAY    battle 1/9 BLOCKED
...
14:31:42  JUDGE     PROMOTED
```

Every row must map to a real stored event/result.

Clicking an event should ideally focus the corresponding canvas object if this already fits the architecture cheaply.

Do not build that interaction if it adds risk.

---

# LIVE STATUS

The top bar should distinguish:

```text
LIVE · ATLAS CONNECTED · RUNNING
```

from:

```text
LIVE · ATLAS CONNECTED · COMPLETE
```

and:

```text
HISTORICAL · READ ONLY
```

If run status is not currently explicit, derive it from authoritative runtime state, not UI timers.

---

# SHOW BOTH SIDES ACTUALLY EVOLVING

This part matters.

The live run should provide enough workload for us to observe real selection behavior.

I want to be able to see:

## Red

```text
current parent
candidate mutation
strategy/tactic changes
candidate fitness
parent fitness
PROMOTED / REJECTED
new Red champion if promoted
```

## Blue

When a breach exists:

```text
current harness champion
breach evidence
engineer call
HarnessPatch
candidate harness
replay battery
candidate fitness
parent fitness
PROMOTED / REJECTED
new Blue champion if promoted
```

If one side does not promote in a particular run, DO NOT fake it.

A rejection is valid evolution evidence.

Explain:

```text
evolution means selection, not guaranteed improvement every generation
```

---

# IMPORTANT: "IMPROVEMENT" MUST REMAIN EMPIRICAL

Do not label every new child:

```text
improved
```

until it actually beats its parent under the relevant evaluation.

Use:

```text
candidate
```

until selection.

Then:

```text
PROMOTED
```

or:

```text
REJECTED
```

A promoted descendant is the empirical improvement.

A rejected descendant remains evidence.

---

# LIVE RUN SIZE

Do NOT start another multi-hour soak.

We need a bounded judge-friendly REAL run.

Inspect current CLI capabilities and choose the smallest configuration that gives a genuine chance to exercise:

```text
Red mutation/selection
attack execution
Blue patching if breach occurs
replay
promotion/rejection
generation inheritance
```

Target approximately:

```text
2–3 generations
```

and a runtime suitable for a demo.

Prefer roughly:

```text
3–8 minutes
```

rather than a long benchmark.

Do not hard-code unsupported CLI arguments.

Use only arguments actually implemented by `app.coevolution`.

Before executing, print the exact command and explain why the selected workload is real but bounded.

---

# START WITH A DRY CONNECTIVITY CHECK

Before consuming model/API resources:

Verify:

```text
AI rig reachable
Red model exists
Atlas reachable
Blue executor configured
Blue engineer configured
frontend reachable :5175
backend observer/API reachable
real coevolution module imports
```

Then start the real run.

---

# LIVE OBSERVER ARCHITECTURE

The preferred topology is:

```text
Terminal A:
REAL app.coevolution process
    │
    ├── Red → AI rig
    ├── Blue → configured providers
    └── writes → Atlas

Terminal B:
observer/backend API
    │
    └── reads → Atlas

Browser:
frontend :5175
    │
    └── reads observer API repeatedly / stream
```

This separation is desirable because:

```text
writer can run
observer can reconnect
browser can refresh
state survives process boundaries
```

Do not merge everything into a fake in-process demo loop.

---

# CRITICAL ACCEPTANCE TEST — TRUE LIVE STATE

During the run perform this proof:

```text
T0:
browser shows generation/event count N

T1:
REAL model call completes

T2:
new record appears in Atlas

T3:
observer sees the new record

T4:
browser displays it without manually fabricating state
```

Capture timestamps or IDs proving this chain.

Repeat for at least:

```text
one Red attack event
one sandbox/evaluator outcome
one evolutionary selection decision
```

And, if a breach occurs:

```text
one Blue HarnessPatch lifecycle
```

---

# MID-RUN PAGE REFRESH TEST

While the REAL run is still active:

refresh the browser.

Expected:

```text
same live run reconstructs from Atlas
existing events return
new events continue appearing
```

This proves the UI is not relying on ephemeral frontend state.

---

# OBSERVER RESTART TEST — ONLY IF CHEAP

If safe and quick:

while the writer continues:

```text
restart observer/API
```

Then verify it reconstructs the current run from Atlas and continues following it.

Do NOT risk the live run if this test looks unsafe.

Fresh-process Atlas readback has already been proven, so this is optional.

---

# UI MUST SHOW PROVIDER TRUTH

During the live run visibly expose actual model attribution.

Example:

```text
RED
qwen3.8-flash-next-heretic2
LOCAL AI RIG

BLUE EXECUTOR
inclusionai/ling-3.0-flash-fin:free

BLUE ENGINEER
nvidia/nemotron-3-super-120b-a12b:free
```

If fallback occurs:

show it.

Do not conceal provider failures.

---

# LIVE MODEL-CALL TELEMETRY

If already available from `model_calls`, expose useful non-sensitive telemetry where easy:

```text
role
model
latency
success/failure
generation
candidate
```

Do not expose:

```text
API keys
credentials
full hidden reasoning / CoT
```

The Red reasoning-output protection remains in force.

Never persist or render hidden chain-of-thought.

---

# UI PRODUCT STORY

When live mode is running, the user should be able to visually understand:

```text
WHO is acting
WHAT was generated
WHAT actually executed
WHY it was scored as held/breach
WHAT changed
HOW candidate and champion compared
WHY candidate won/lost
WHO becomes the next parent
```

This is more important than additional visual polish.

---

# OCTOBER.DEV FEEL

Preserve the spatial runtime presentation.

For live execution, a useful experience is:

```text
current active stage subtly highlighted
real windows appear/populate as evidence arrives
causal edges remain visible
current generation obvious
event feed scrolls
lineage updates only after real promotion/rejection
```

Do NOT create flashy fake animations.

---

# AWS / HARNESS OPTIMIZER STORY

The live mode should strengthen this accurate statement:

> DarwinGuard is adversarial empirical harness optimization. The harness isn't updated because an LLM thinks a patch sounds better; candidate changes have to survive measured replay against security and utility objectives while the attack distribution itself evolves.

Do not claim Strands integration.

---

# KEEP HISTORICAL DEMOS

Do NOT replace the persisted demos with the live run.

The historical runs remain our reliable evidence.

The presentation strategy is:

```text
Persisted run
= proof that the system works repeatedly

Live run
= proof that this is actually happening now
```

That combination is stronger than relying exclusively on either.

---

# LIVE DEMO FAILURE POLICY

Real models can fail.

Handle that honestly.

If a provider call fails:

show:

```text
MODEL CALL FAILED
```

with sanitized error/evidence.

If candidate generation fails:

show failure.

If Red produces no breach:

that is a valid outcome.

Do NOT force a breach.

Do NOT mutate scores.

Do NOT manually promote a candidate.

Do NOT swap in historical data and call it live.

The UI may let us switch to historical evidence afterward.

---

# HUMAN OPERATOR CONTROL

Before starting the real run, show me:

```text
Run ID:
CLI command:
Red endpoint:
Red model:
Blue executor:
Blue engineer:
Persistence:
Expected approximate runtime:
```

Then execute it.

Once running, provide the browser URL:

```text
http://localhost:5175
```

and tell me exactly where I should look for:

```text
current generation
live event stream
Red candidate
Blue patch
replay result
lineage
```

---

# KIRO REVIEW

Do NOT block live testing on October auto-launching Kiro.

The working manual Kiro session is sufficient.

After the live path works, send Kiro only:

```text
REAL live co-evolution is now observable from the browser.

Please spend at most 10 minutes checking:

1. no simulated frontend state
2. Red model actually comes from ai-rig
3. Atlas records correspond to visible events
4. promotion/rejection is empirical
5. model attribution is truthful
6. model weights are not described as evolving
7. historical and live runs are unmistakably different

Return only BLOCKER/HIGH issues or APPROVE FOR DEMO.
```

---

# INDEPENDENT VERIFIER

Have a fresh OpenCode + DeepSeek Flash verifier independently prove:

```text
REAL RUN: YES

Red endpoint:
ai-rig

Red model:
qwen3.8-flash-next-heretic2

FakeAgent involved:
NO

Atlas:
YES

Frontend receives new runtime state:
YES

Frontend refresh reconstructs state:
YES

Red selection:
REAL / observed result

Blue candidate lifecycle:
REAL / NOT TRIGGERED BECAUSE NO BREACH

Promotion/rejection:
REAL

Historical evidence modified:
NO

Secrets exposed:
NO
```

Do not call it PASS if it only inspected source code.

Use actual runtime evidence.

---

# DO NOT RUN THE KIRO AUTO-LAUNCH FIX FIRST

The Kiro 2.26 / October >=3.0 version-gate mismatch is lower priority.

Keep manual Kiro working.

Order of operations now is:

```text
1. frontend stability
2. live observation path
3. REAL bounded co-evolution
4. visually inspect it
5. independent verifier
6. Kiro regression
7. optional tiny Kiro launcher fix only if time remains
8. FREEZE
```

---

# FINAL DEMO MODES

At completion we should have FOUR trustworthy modes.

## A — Historical overnight

```text
HISTORICAL · READ ONLY
```

Reliable long-run evidence.

## B — Historical two-sided

```text
HISTORICAL · READ ONLY
```

Best adaptive-arms-race evidence.

## C — Persisted Atlas event run

```text
LIVE · ATLAS CONNECTED
```

Known Nemotron/rejection story.

## D — REAL LIVE CO-EVOLUTION

```text
LIVE · ATLAS CONNECTED · RUNNING
```

Actual AI-rig Red agent and actual Blue stack operating NOW.

This is the hero mode.

---

# FINAL REPORT

Return:

## LIVE INFRASTRUCTURE

```text
AI rig: PASS / FAIL
Red model: <actual>
Blue executor: <actual>
Blue engineer: <actual>
Atlas: PASS / FAIL
Observer: PASS / FAIL
Frontend :5175: PASS / FAIL
```

## REAL RUN

```text
Run ID:
Started:
Completed:
Duration:
Generations:
Red versions:
Blue candidates:
Attacks:
Breaches:
Model calls:
```

## RED EVOLUTION

```text
Parent:
Candidate(s):
Fitness comparisons:
Promoted:
Rejected:
Final champion:
```

## BLUE EVOLUTION

```text
Starting champion:
Breaches triggering engineer:
Patch(es):
Replay results:
Promoted:
Rejected:
Final champion:
```

If no Blue patch was triggered, state truthfully:

```text
NOT TRIGGERED — NO BREACH
```

Do NOT fabricate one.

## LIVE FEED

```text
Real event feed: PASS / FAIL
Browser updates during execution: PASS / FAIL
Refresh reconstruction: PASS / FAIL
No synthetic events: PASS / FAIL
```

## UI

```text
LIVE · ATLAS CONNECTED · RUNNING: PASS / FAIL
Red visible: PASS / FAIL
Attack visible: PASS / FAIL
Sandbox visible: PASS / FAIL
Evaluator visible: PASS / FAIL
Blue visible: PASS / FAIL
HarnessPatch visible: PASS / FAIL / NOT TRIGGERED
Replay visible: PASS / FAIL / NOT TRIGGERED
Selection visible: PASS / FAIL
Lineage updated: PASS / FAIL
```

## INTEGRITY

```text
FakeAgent used: NO
Historical evidence changed: NO
Silent persistence fallback: NO
Model weights described as evolving: NO
Secrets exposed: NO
```

## REVIEWS

```text
Independent verifier:
Kiro:
```

## FINAL VERDICT

Choose:

```text
REAL LIVE CO-EVOLUTION READY
```

or:

```text
LIVE MODE BLOCKED
```

If ready, leave the system in the safest judge-demo state and STOP ENGINEERING.