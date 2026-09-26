# DarwinGuard Task — Make the Red/Blue Harness Genuinely Self-Improving

The new spatial frontend is good enough. **Do not spend this task redesigning the UI.**

The priority now is making the underlying harness genuinely co-evolve.

I need **both Red and Blue to improve autonomously across generations based on empirical results from previous generations**.

Do not simulate this.  
Do not hard-code progress.  
Do not increment a generation counter and call that evolution.

---

## Current Verified Baseline

The repository has already demonstrated a real path:

```text
Red
→ real attack
→ sandbox
→ deterministic evaluator
→ breach
→ real Blue call
→ HarnessPatch
→ candidate
→ replay
→ promotion
→ next generation attacks promoted champion
```

A previous REAL run demonstrated:

- real Red from the local AI rig
- a genuine breach
- Blue using:
  `inclusionai/ling-3.0-flash-fin:free`
- real HarnessPatch generation
- candidate compilation
- deterministic promotion
- subsequent generations attacking the promoted Blue champion

So **do not rewrite that working engine**.

Instead, inspect it and make sure it constitutes genuine **two-sided co-evolution**.

---

# 1. Actual Requirement

At generation `N` we should have persistent evolutionary state for both sides:

```text
Red_N
Blue_N
```

Then:

```text
Red_N attacks Blue_N
        ↓
real executions + deterministic evidence
        ↓
both sides learn from those results
        ↓
candidate Red_N+1
candidate Blue_N+1
        ↓
both are empirically evaluated
        ↓
promotion/rejection
        ↓
next generation uses the winners
```

Conceptually:

```text
R0 ──mutate/evaluate──► R1 ──► R2 ──► R3
 │                      │
 ▼                      ▼
B0 ──patch/evaluate───► B1 ──► B2 ──► B3
```

This should become an actual adversarial evolutionary arms race.

---

# 2. Audit Red First

Determine whether Red currently **really evolves**.

Previous runs had concepts such as:

- Red attacker
- Red mutator
- Red versions
- tactic priors
- generation-to-generation changes

But do not assume this means meaningful evolution.

Trace it.

For every generation determine:

- What exactly is Red's persistent state?
- What changes between `Red_N` and `Red_N+1`?
- What evidence causes that change?
- Is the new Red evaluated?
- Can a worse Red mutation be rejected?
- Is there a Red parent/child lineage?
- Does the next generation really use the promoted Red version?
- Does Red learn specifically from attacks that failed against Blue?

If any of those are missing, implement them cleanly.

---

# 3. Red Needs an Explicit Evolutionary Genome

Do **not** make Red self-modify arbitrary application source code.

Red's evolution should happen through a constrained persisted strategy/genome.

Use existing abstractions where available.

A `RedVersion` / `RedGenome` may include things such as:

- tactic priors
- attack-family weights
- exploration temperature
- novelty preference
- successful tactic history
- failed tactic history
- target-stage preference
- mutation strategy
- prompt-strategy parameters
- attack diversity state

Exact schema should follow the existing architecture.

Do not create unnecessary complexity if some of this already exists.

The critical requirement is:

> `Red_N` must contain persisted strategy state which meaningfully affects the attacks it generates.

---

# 4. Red Must Learn From Failure Too

This is extremely important.

Right now a strong Blue champion may produce:

```text
ASR = 0
```

That must **not** mean:

> nothing happens.

If Red attacks Blue and all attacks are blocked, that is valuable evolutionary pressure.

Red should receive evidence like:

- which tactic was attempted
- what defense stopped it
- execution outcome
- evaluator result
- novelty
- previous similar failures
- coverage achieved

The Red mutator should use this evidence to propose a modified Red strategy.

Example:

```text
R1 heavily tries context injection.
Blue blocks all of it.

Red mutator sees the failure.

R2 shifts some probability toward:
- provenance attacks
- tool-boundary attacks
- authorization confusion
- multi-step attacks
- other available tactic families
```

This adaptation must come from actual run evidence.

Do **not** hard-code:

```text
generation 1 = tactic A
generation 2 = tactic B
generation 3 = tactic C
```

---

# 5. Red Promotion Must Be Evidence-Based

Do not automatically accept every Red mutation.

Create/use deterministic Red fitness.

Use existing metrics where possible.

Reasonable signals include:

- attack success rate
- number of unique failures discovered
- novelty
- coverage
- diversity
- ability to attack current champion
- performance against historical Blue champions

Exact formula should be explicit and tested.

Conceptually:

```text
red_fitness =
  breach effectiveness
  + novelty
  + coverage/diversity
  + historical generalization
```

Do **not** use an LLM saying:

> this Red looks better

as the promotion criterion.

The LLM can propose mutations.

Deterministic evidence decides whether they survive.

We should be able to say:

```text
R0
  ↓ mutation M1
R1 candidate
  ↓ empirical battery
PROMOTED
```

or:

```text
R1 candidate
  ↓ empirical battery
REJECTED
R0 remains champion
```

---

# 6. Blue Evolution

Now audit Blue.

Blue's evolutionary state is primarily the `RuntimeHarness` / Harness DNA.

A breach should produce:

```text
failure evidence
→ Ling Blue engineer
→ HarnessPatch
→ candidate harness
→ replay battery
→ benign/regression battery
→ deterministic fitness
→ PROMOTE or REJECT
```

Confirm that this is genuinely happening.

`Blue_N+1` must inherit from `Blue_N`.

It must **not** recreate a harness from the original baseline every generation.

Persist:

- parent
- patch
- candidate
- fitness
- replay evidence
- decision
- resulting champion

---

# 7. Blue Fitness Must Balance Defense and Utility

A Blue defense should **not** win merely because it blocks everything.

For example:

```text
disable every tool
```

would produce great security and useless behavior.

Use the existing deterministic utility/fitness system.

Blue promotion should account for things such as:

- attack block rate
- original breach fixed
- historical attacks blocked
- benign behavior preserved
- utility maintained
- regressions
- complexity/cost if already modeled

Keep whatever valid existing fitness formula the repository already has rather than inventing another competing metric.

---

# 8. Cross-Generation Arms Race

This is the most important part.

Generation `N+1` must use **both outcomes from N**.

Example:

```text
GENERATION 0

Red champion R0
Blue champion B0

R0 attacks B0

→ breach A7

Blue produces candidate B1
B1 fixes A7
B1 passes regressions
B1 promoted

Meanwhile:

Red sees:
- which attacks succeeded
- which failed
- why they failed

Red mutator creates candidate R1
R1 is evaluated
R1 promoted
```

Now:

```text
GENERATION 1
```

Do **not** use `R0 vs B0` again.

Use:

```text
R1 vs B1
```

Then repeat.

This is the core requirement.

---

# 9. Historical Adversaries / Anti-Overfitting

Both sides should avoid overfitting to only their immediate opponent.

Use historical champions where the existing `ChampionJudge` / fair-battery architecture allows.

For Blue candidate `B3`, test against:

- current Red attacks
- historical successful Red attacks
- benign/regression suite

For Red candidate `R3`, test against:

- current Blue champion
- selected historical Blue champions where practical

This creates evolutionary pressure toward generalization.

Do not require an enormous battery that makes the demo unusably slow.

Use bounded sampling.

---

# 10. Persist Both Lineages

I want the database to represent **two evolutionary trees**.

## Red lineage

```text
R0
└── mutation RM1
    └── R1
        ├── RM2 → R2 rejected
        └── RM3 → R3 promoted
```

## Blue lineage

```text
B0
└── patch BP1
    └── B1
        ├── BP2 → B2 rejected
        └── BP3 → B3 promoted
```

Persist enough information to reconstruct:

### Red
- version
- parent
- mutation
- strategy state
- attacks
- fitness
- promotion decision

### Blue
- harness
- parent
- HarnessPatch
- candidate
- fitness
- promotion decision

### Generation-level matchup

```text
Generation N:
Red champion = R?
Blue champion = B?
results = ...
```

---

# 11. REAL Mode Only for Final Acceptance

Unit tests may use deterministic fixtures.

But acceptance of this task requires a **REAL run**.

Use:

### Red
Local AI rig via the authorized REAL-mode path.

### Blue
OpenRouter:

```text
inclusionai/ling-3.0-flash-fin:free
```

Do not weaken REAL-mode guards.

Do not silently substitute deterministic fixtures for final acceptance.

---

# 12. Required Real Experiment

Run at least **3 generations**.

Prefer more if runtime/cost permits.

Capture for every generation:

```text
GEN
Red champion
Blue champion
Red mutation
Blue mutation if breached
attacks
ASR
Red fitness
Blue fitness
promotion/rejection decisions
```

I need observable evidence of adaptation.

An acceptable example could look like:

```text
G0
R0 vs B0
ASR .50
Blue breach → B1 promoted
Red mutation → R1 promoted

G1
R1 vs B1
ASR .10
B1 holds most attacks
Red changes strategy → R2 promoted

G2
R2 vs B1
new attack family discovers breach
Blue produces B2
B2 promoted

G3
R2/R3 vs B2
...
```

The exact numbers do not matter.

REAL behavior determines them.

Do not manufacture a nice trajectory.

It is completely acceptable for:

- a Red mutation to be rejected
- Blue not to mutate during a generation
- ASR to decrease
- a candidate to regress
- no breach to occur

Evolution does **not** mean metrics monotonically improve every generation.

It means selection responds to empirical fitness.

---

# 13. Important Case: Blue Holds Everything

Suppose:

```text
Red attacks B1
ASR = 0
```

Do not end the evolutionary process.

Blue may stay `B1` because there is no reason to patch.

But Red should continue evolving.

```text
R1
→ mutation
→ R2
→ attack B1

R2
→ R3
→ attack B1
```

subject to sensible generation/budget limits.

That is exactly where the adversarial arms race becomes interesting.

---

# 14. Important Case: Red Finds a Breach

Suppose Red discovers a real weakness.

Then Blue should autonomously:

- analyze evidence
- propose one or more candidate `HarnessPatch` objects if architecture supports it
- validate
- compile
- replay
- run regressions
- select/promote the best valid candidate

The human should not manually write the defense.

---

# 15. Autonomy Boundary

"Self improving" means:

```text
model proposes bounded evolutionary changes
+
system evaluates them
+
selection promotes or rejects them
+
the next generation inherits winners
```

It does **not** mean:

> allow models to arbitrarily rewrite the entire DarwinGuard source repository.

Keep mutations within the defined Red strategy and Blue `HarnessPatch` systems.

That gives us actual autonomous evolution without destroying reproducibility.

---

# 16. UI Integration

The new spatial UI is already good.

Do not redesign it.

Wire it to this REAL co-evolution state.

The canvas should eventually be able to show live:

```text
RED R2
    │
    │ attacks
    ▼
BLUE B1
    │
    ├── held → Red mutates
    │
    └── breach → Blue mutates
```

When Red evolves, create/update a Red evolution window.

When Blue evolves, show:

- HarnessPatch
- candidate
- replay

The UI must display backend truth.

No frontend-generated fake transitions.

---

# 17. Frontend Should Show Both Lineages

The existing Lineage mode should ultimately show both sides.

For example:

```text
RED                         BLUE

R0                          B0
│                           │
RM1                         BP1
│                           │
R1 ✓                        B1 ✓
│                           │
├─ R2 ✕                     ├─ B2 ✕
│                           │
└─ R3 ✓                     └─ B3 ✓
```

And generations should link the matchup:

```text
G2 = R3 vs B1
```

Do not spend this task doing visual polish beyond wiring real data.

---

# 18. Tests

Add tests proving:

1. Red mutation changes persisted strategy state.
2. Red candidate can be rejected.
3. Red champion survives rejection.
4. Promoted Red is actually used next generation.
5. Blue candidate inherits current Blue champion.
6. Rejected Blue is not used next generation.
7. Promoted Blue **is** used next generation.
8. No-breach generation can still evolve Red.
9. Historical opponent sampling does not corrupt champion state.
10. Resume/re-entry preserves **both** Red and Blue champions.
11. Evolution events/persistence reconstruct both lineages.

Keep existing tests green.

---

# 19. Observability

For every evolutionary change persist/log:

```text
who:
RED / BLUE

generation

parent version

candidate version

mutation

reason proposed

fitness before

fitness after

evaluation evidence

decision:
PROMOTED / REJECTED

next-generation champion
```

I want to be able to prove the evolution happened from stored evidence.

---

# 20. Do Not Claim Success From Code Inspection

This task is **not** complete because:

> the classes exist

or:

> the tests pass.

You must run the real system.

Use actual models.

Then inspect persisted evidence.

---

# 21. Final Acceptance Report

When finished give me:

## A. Co-Evolution Status

```text
Red genuinely evolves: YES / NO
Blue genuinely evolves: YES / NO
Selection is empirical: YES / NO
Both winners feed next generation: YES / NO
```

## B. Real Run

Provide a table:

```text
Generation | Red Champion | Blue Champion | ASR | Red Mutation | Red Decision | Blue Patch | Blue Decision
```

## C. Proof of Red Learning

Show exactly how at least one Red version differed from its parent and **why**.

## D. Proof of Blue Learning

Show exactly how at least one promoted Blue harness differed from its parent and which real breach caused it.

## E. Lineage

Print both persisted Red and Blue ancestry chains.

## F. Real Models

Provide:

- exact Red model/provider
- exact Blue model/provider

## G. Tests

Provide:

- pytest result
- mypy result
- Ruff result
- frontend build result if frontend wiring changed

## H. Remaining Limitation

Give only real limitations supported by evidence.

---

# Final Goal

DarwinGuard should not merely be:

> an LLM attacks and another LLM patches.

It should be:

> a persistent adversarial evolutionary system where Red learns how to find increasingly effective attacks, Blue learns how to build increasingly resilient harnesses, both are selected using real execution evidence, and every new generation inherits the strongest surviving versions.

That is the product.

**Make that real.**
