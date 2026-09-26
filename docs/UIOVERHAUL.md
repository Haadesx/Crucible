Build/rework the **DarwinGuard frontend** into a polished spatial runtime interface inspired by the interaction model of October.dev.

Do NOT create a pixel-for-pixel clone of October.

Instead, study October's current visual approach and reproduce the concepts that make it useful:

- dark spatial canvas
- floating runtime cards/windows
- visible system topology
- connections showing work/data moving between components
- live status
- inspectable execution
- one place to understand the whole operation
- detail panels instead of forcing users into separate pages
- clear distinction between idle / running / waiting / failed / successful states
- evidence attached directly to the thing that produced it

The frontend should feel like an **operations cockpit for a living DarwinGuard evolution run**, not a traditional SaaS dashboard.

---

# 1. FIRST — RESEARCH OCTOBER'S UI

Before coding, inspect the current public October website/docs/screenshots and identify its reusable UI principles.

Focus on:

- spatial canvas layout
- dark desktop-like visual treatment
- floating cards/windows
- agent/process cards
- connections between components
- status indicators
- selected-object inspector behavior
- runtime/task progress
- compact controls
- hierarchy of primary canvas vs secondary details
- how dense technical information remains readable

Do not blindly copy logos, branding, proprietary artwork, or exact visual assets.

We want:

**"DarwinGuard with an October-like spatial operations UX."**

Not:

**"a counterfeit October screen."**

---

# 2. INSPECT THE EXISTING DARWINGUARD FRONTEND FIRST

Do not immediately rewrite everything.

Inspect:

- frontend framework
- routes
- components
- styles
- current API clients
- WebSocket/SSE support
- existing evolution/workbench UI
- existing state management
- backend schemas exposed to frontend
- existing run/generation APIs
- model-call APIs
- harness APIs
- attack/episode APIs
- persistence APIs

Preserve useful existing components and backend contracts.

Do not break the working DarwinGuard backend to accommodate the UI.

The backend is now substantially functional and should remain the source of truth.

---

# 3. PRIMARY EXPERIENCE

The default DarwinGuard screen should be a **large interactive spatial canvas**.

Think:

```text
┌───────────────────────────────────────────────────────────────┐
│ DarwinGuard                 REAL • Running       Gen 03       │
├────────────┬──────────────────────────────────────────────────┤
│            │                                                  │
│ RUNS       │       [ RED ]                                    │
│            │          │                                       │
│ Gen 0      │          ▼                                       │
│ Gen 1      │      [ ATTACK ]                                  │
│ Gen 2      │          │                                       │
│ Gen 3 ●    │          ▼                                       │
│            │     [ SANDBOX ]                                  │
│ HISTORY    │          │                                       │
│            │          ▼                                       │
│ ...        │    [ EVALUATOR ]                                 │
│            │      │       │                                   │
│            │   breach    held                                 │
│            │      │                                           │
│            │      ▼                                           │
│            │    [ BLUE ]                                      │
│            │      │                                           │
│            │      ▼                                           │
│            │ [ HARNESS PATCH ]                                │
│            │      │                                           │
│            │      ▼                                           │
│            │ [ CANDIDATE C1 ] ──→ [ REPLAY ]                  │
│            │      │                    │                      │
│            │      └───────┬────────────┘                      │
│            │              ▼                                   │
│            │      [ PROMOTE / REJECT ]                         │
│            │              │                                   │
│            │              ▼                                   │
│            │        [ CHAMPION ]                               │
│            │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

This is conceptual, not a required exact layout.

The important thing is that a user can visually understand:

**what happened, what is happening now, and why.**

---

# 4. THE CANVAS SHOULD SHOW REAL DARWINGUARD OBJECTS

Represent major runtime entities as cards/nodes.

## Red node

Show:

- model
- provider
- status
- generation
- attack attempts
- latency
- attack count
- mutation count

For current expected real setup, this may show the local AI-rig Red model when applicable.

Do not hard-code model names if the backend provides them.

## Attack node/card

Show:

- attack ID
- tactic/type
- generation
- originating Red call
- parse status
- execution status
- whether it caused a breach

Use a compact card on the canvas.

Detailed prompt/model response belongs in the inspector.

## Sandbox node

Show:

- executing / complete / timeout / error
- duration
- executed tool/call count
- result
- environment

A user should immediately see whether the attack actually executed.

## Evaluator node

Show:

- ASR
- utility / fitness metrics
- deterministic outcome
- failure reason
- pass/breach state

This should visually distinguish:

`BREACH`

from:

`HELD`

very clearly.

## Blue node

Show:

- provider/model
- status
- patch attempt count
- repair count
- output validity

Current intended model:

`inclusionai/ling-3.0-flash-fin:free`

Do not hard-code it as a decorative label if runtime metadata says otherwise.

Show actual runtime data.

## HarnessPatch card

This is particularly important.

Show a concise mutation summary:

- stages added
- stages removed
- stages modified
- validation status
- patch ID
- originating failure

Allow selecting the patch to inspect the structured patch.

## Candidate harness

Show:

- candidate ID
- parent champion
- compiled state
- current lifecycle state
- fitness
- utility
- block rate
- replay count

## Champion

The currently deployed/promoted harness should be visually prominent.

Show:

- harness ID
- generation
- fitness
- promoted timestamp
- parent
- defenses/stages active

A user should be able to instantly answer:

**"What harness is currently winning?"**

---

# 5. CONNECTIONS ARE FIRST-CLASS UI

Do not just put cards beside each other.

Connect them.

Examples:

```text
Red
  │ generated
  ▼
Attack
  │ executed by
  ▼
Sandbox
  │ measured by
  ▼
Evaluator
```

On breach:

```text
Evaluator
   │ breach evidence
   ▼
Blue
   │ proposed
   ▼
HarnessPatch
   │ compiled into
   ▼
Candidate
```

Then:

```text
Candidate
   │ replay
   ▼
Judge
   │
   ├── PROMOTED → Champion
   │
   └── REJECTED
```

Edges should communicate actual relationships.

Where useful, show:

- labels
- direction
- animated activity while executing
- completed state after execution
- failure state when a transition fails

Do not make excessive animations that distract from inspection.

---

# 6. OCTOBER-LIKE FLOATING CARD FEEL

Use a dark, refined visual language.

Target feel:

- deep charcoal/navy background
- subtle grid/dot spatial canvas
- restrained borders
- slightly elevated floating cards
- compact typography
- monospaced text where technical
- minimal but clear status colors
- subtle glows only for active/selected objects
- rounded but not toy-like
- very little wasted space
- professional developer-tool aesthetic

Cards should feel like miniature runtime windows.

A card header might have:

```text
● BLUE EXECUTOR                  ⋯
Ling 3.0 Flash
──────────────────────────────────
Generating HarnessPatch...
2 repair attempts
14.2s
```

Avoid generic giant dashboard tiles.

---

# 7. SIDE PANEL / INSPECTOR

Selecting anything on the canvas should open an inspector panel rather than navigate away.

For example, selecting an attack might show:

```text
Attack A-0192

STATUS
BREACH

GENERATION
G03

RED MODEL
qwen...

TACTIC
context confusion

MODEL CALL
7.1s

EXECUTION
Sandbox #EP-493

RESULT
Invariant violated

[ Prompt ]
[ Raw output ]
[ Parsed attack ]
[ Sandbox trace ]
[ Evaluation ]
```

Selecting a HarnessPatch could show:

```text
HarnessPatch P-0031

STATUS
VALID

PARENT
B-G02-C1

CHANGES
+ approval_gate
~ argument_validator
~ risk_gate threshold

SOURCE FAILURE
A-0192

[ Structured patch ]
[ Validation ]
[ Graph diff ]
[ Replay results ]
```

This is one of the most important UX ideas.

The canvas explains **structure**.

The inspector explains **evidence**.

---

# 8. RUN / GENERATION SIDEBAR

Add a compact left sidebar inspired by October's project/run navigation.

Show:

- current run
- generations
- historical runs
- current status
- promoted generations
- failed/interrupted runs

Example:

```text
DARWINGUARD

REAL-ACCEPT-2
● REAL

GENERATIONS

✓ G00
  breach → C1 promoted

✓ G01
  held

● G02
  running

HISTORY

DEF-ACCEPT-1
FINAL-01
...
```

Clicking a generation should rehydrate the canvas with that generation's persisted evidence.

This must use real backend data.

---

# 9. TOP STATUS BAR

Have a compact persistent system status bar.

Useful information:

```text
DarwinGuard

RUN: REAL-ACCEPT-2

MODE
REAL

GENERATION
03

RED
CONNECTED

BLUE
CONNECTED

AI RIG
ONLINE

DATABASE
ATLAS / DEV

CHAMPION
B-G01-C1
```

Use small status pills rather than giant panels.

Users should immediately know whether they are looking at:

- REAL vs DEV
- live vs historical data
- Atlas vs local persistence

This distinction is especially important for the hackathon.

---

# 10. LIVE EXECUTION

The UI should visibly update during execution.

If the backend already exposes WebSocket/SSE/event streaming, use it.

If not, inspect the cleanest existing mechanism.

Do NOT fake live activity with timers.

As events occur:

```text
Red thinking
→ attack appears
→ attack execution starts
→ evaluator result appears
→ breach route activates
→ Blue activates
→ patch appears
→ candidate compiles
→ replay occurs
→ decision appears
→ champion changes
```

The canvas should make this sequence comprehensible.

A user watching the demo should not require narration to understand what DarwinGuard is doing.

---

# 11. TIMELINE / EVENT LOG

Include a compact event timeline, optionally collapsible.

Example:

```text
18:42:01  Generation 03 started
18:42:04  Red generated A-0192
18:42:05  Attack parsed successfully
18:42:07  Sandbox execution complete
18:42:07  BREACH detected
18:42:08  Blue invoked
18:42:19  HarnessPatch P-0031 generated
18:42:20  Candidate C2 compiled
18:42:22  Replay battery started
18:42:29  Candidate promoted
18:42:29  Champion changed B1 → C2
```

Selecting an event should select the corresponding object on the canvas.

---

# 12. GENERATION / LINEAGE VIEW

DarwinGuard has something October does not: **evolutionary lineage**.

Make this a signature visual feature.

Add a toggle:

`LIVE CANVAS | LINEAGE`

Lineage view could show:

```text
G00
B0
│
├─ P1 → C1 ✓ PROMOTED
│        │
│        └─────────────── G01 champion
│
└─ P2 → C2 ✕ REJECTED


G01
C1
│
├─ P3 → C3 ✕ REJECTED
│
└─ P4 → C4 ✓ PROMOTED
         │
         └─────────────── G02 champion
```

Nodes should expose:

- fitness
- utility
- ASR
- parent
- mutation
- outcome

Clicking any historical harness opens it in the inspector.

---

# 13. RED VS BLUE VISUAL IDENTITY

Red and Blue should be visually recognizable without turning the UI into a game.

Use restrained semantic visual identities:

Red:
- adversarial generation
- attack cards
- breach route

Blue:
- defense analysis
- mutation
- candidate creation

Champion/promotion:
- distinct neutral/success identity

Rejected candidate:
- muted and clearly terminal

Do not overwhelm the entire UI with saturated red and blue backgrounds.

Use the colors as signals, not wallpaper.

---

# 14. HUMAN-READABLE DEMO MODE

This is a hackathon project.

Add a presentation-friendly mode if practical.

Potential toggle:

`DEVELOPER | DEMO`

Developer mode exposes:

- IDs
- latency
- JSON
- provider
- call traces
- detailed metrics

Demo mode emphasizes:

- "Red found a weakness"
- "Blue proposed a defense"
- "Candidate blocked the attack"
- "Candidate promoted"
- "Generation 2 now attacks the stronger harness"

The underlying data must be identical.

Demo mode changes presentation only.

It must NOT generate fake summaries/outcomes.

---

# 15. MODEL CALL INSPECTION

Users should be able to inspect real model activity.

For Red/Blue nodes expose:

- provider
- model
- latency
- timestamp
- role
- success/error
- parse status
- repair count

Raw prompts/responses may be shown behind an expandable technical tab.

Never expose API keys, auth headers or secrets.

---

# 16. FAILURE STATES NEED FIRST-CLASS DESIGN

October's model is useful because runtime state is inspectable.

DarwinGuard should behave similarly.

Design visible states for:

- provider unavailable
- timeout
- malformed Red output
- sandbox failure
- evaluator failure
- Blue invalid patch
- candidate compile failure
- replay failure
- rejected candidate
- persistence failure
- interrupted run

Do not just print failures in the browser console.

The relevant node should visibly indicate the failure, and the inspector should explain it.

---

# 17. PERFORMANCE

The canvas may accumulate many nodes.

Avoid rendering every historical event simultaneously.

Use:

- generation scoping
- collapsed groups
- virtualized lists where appropriate
- lazy inspector payloads
- efficient canvas rendering

The live generation should remain smooth.

---

# 18. RESPONSIVE TARGET

Primary target is desktop/laptop presentation.

Optimize for approximately:

- 1440p desktop
- 1080p projector/demo screen
- MacBook-class laptop displays

Do not spend excessive time on mobile.

At narrow widths, graceful degradation is enough.

---

# 19. IMPLEMENTATION CHOICE

Use the existing frontend stack where reasonable.

If the project already includes a good node/canvas library, keep it.

If no suitable canvas exists, evaluate a mature graph/canvas solution rather than writing pan/zoom/edges completely from scratch.

Requirements include:

- draggable/selectable nodes
- pan
- zoom
- fit-to-view
- directed edges
- custom nodes
- live updates
- reliable layout

Choose the smallest dependency that cleanly satisfies those requirements.

Do not migrate the entire frontend framework simply to build this UI.

---

# 20. DATA MUST BE REAL

This is critical.

Do not create fake placeholder runs and then leave them wired into the production UI.

The interface should consume the actual DarwinGuard backend entities.

Map actual backend data into view models where needed.

The final demo should visually represent the same REAL run evidence the CLI/runtime uses.

If a backend endpoint is missing, add the smallest clean read-only endpoint necessary.

Do not invent a second frontend-only source of truth.

---

# 21. PRESERVE THE WORKING ENGINE

The verifier has already confirmed the real backend evolution loop works.

Do not refactor engine behavior while implementing the frontend unless absolutely required.

Frontend work must not break:

- Red execution
- sandbox
- evaluator
- Ling Blue execution
- HarnessPatch
- candidate compiler
- replay
- promotion
- generation continuity
- persistence
- REAL-mode guards

Treat engine changes as high-risk.

---

# 22. ACCEPTANCE CRITERIA

The task is done when I can open DarwinGuard and immediately understand a live or persisted evolution run visually.

At minimum:

1. There is an October-inspired dark spatial canvas.
2. Major DarwinGuard runtime components appear as connected nodes/cards.
3. Current execution status is visible.
4. Selecting a node opens meaningful real evidence.
5. Generation navigation works.
6. Current champion is obvious.
7. Promotion/rejection is visually obvious.
8. Real Red/Blue model metadata is visible.
9. REAL vs DEV is clearly labeled.
10. Persisted historical runs can be inspected.
11. A lineage/evolution view exists.
12. The UI consumes real backend data.
13. Failure states are visible.
14. Existing backend tests remain green.
15. Frontend build passes.

Most importantly:

A judge unfamiliar with the code should be able to watch the screen and understand:

**Red attacked → something failed → Blue adapted the harness → the candidate was tested → it either won or lost → the next generation continued from the result.**

---

# 23. VERIFY VISUALLY

Do not declare the frontend finished based only on successful compilation.

Actually launch it.

Inspect it in a browser.

Verify:

- spacing
- canvas layout
- edge routing
- text clipping
- scroll behavior
- inspector
- generation navigation
- empty states
- loading states
- error states
- live updates
- 1440p presentation
- 1080p presentation

Take screenshots if your environment supports it and inspect them yourself.

Fix obvious visual problems before reporting completion.

---

# 24. FINAL REPORT

When finished, report:

### IMPLEMENTATION
- components added/changed
- canvas/graph technology used
- APIs/events consumed
- any backend read endpoints added

### VISUAL FEATURES
- spatial topology
- run sidebar
- inspector
- timeline
- lineage view
- status bar
- developer/demo mode if implemented

### LIVE DATA
- which UI elements are backed by actual runtime data
- whether live updates work
- which persisted run was tested

### VERIFICATION
- frontend build result
- backend regression result
- screenshots/browser verification
- known UI limitations

### CODE
- files changed
- commit hash

Do not start unrelated backend work afterward.

This task owns the **DarwinGuard visual runtime experience**.