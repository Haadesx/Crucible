# The harness — the thing Crucible evolves

The harness is the runtime policy wrapped around the AI agent's tool use: a small,
executable graph of stages that every proposed tool call passes through before it can run.
**Model weights stay frozen.** What Blue's engineer edits is this graph — through
`HarnessPatch` operations — and a candidate graph becomes the next champion only after it
is compiled, replayed against adversarial **and** benign tests, and judged on measured
results.

## Stage kinds

Each node is a stage; edges are the order tool calls flow through it:

```text
input → context → agent → policy stages → tool → memory/verifier
```

Policy stages include provenance boundaries, argument validation, human approval gates,
tool authorization and classifiers. Adding or changing one is what a patch does.

## A real before → after (from the recorded venue run)

Extracted from `backend/experiments/VENUE-SHIPPING-SMOKE-20260926-125109/state.json`:

| File | What it is |
|---|---|
| `b0-baseline.json` | Seed harness (generation 0): INPUT → CONTEXT ISOLATION → TARGET AGENT → PROVENANCE BOUNDARY → HUMAN APPROVAL GATE → TOOL AUTHORIZATION GATE → SANDBOX TOOL |
| `c1-current.json` | Promoted harness (generation 1): the same graph **plus ARGUMENT VALIDATOR** |
| `patch-to-c1.json` | The exact patch that produced it: `SET_PARAMETER recipient_validation = true`, author call `CALL-f241340c437341e28e10` (Nemotron engineer), valid, PROMOTED |

Replay evidence for the promotion (9 battles): block rate **1.00**, utility **0.56**,
fitness **0.720**; slices — current 2 episodes (security 1.0 / utility 0.5), holdout 2
(1.0 / 1.0), benign 5 (1.0 / 0.4). The breach that motivated the patch is blocked by C1.

The later live run shows a richer champion (recipient validation + input classifier) in
`backend/exports/run_report_CRUCIBLE-LIVE-20260926-162014.json`.

## Where the code lives

```text
backend/app/harness/compiler.py   turns a HarnessPatch into an executable graph
backend/app/harness/gateway.py    per-tool-call policy decision
backend/app/harness/registry.py   deployed versions, champions, promotion pointers
backend/app/harness/rules.py      the stage implementations (validation, gates, ...)
backend/app/harness/trust.py      provenance/trust boundaries
backend/app/harness/runtime.py    executes allowed tool calls under the compiled harness
backend/app/harness/verifier.py   final verification before a call is allowed
backend/app/harness/analysis.py   failure analysis used by the Blue engineer
backend/app/harness/mutation.py   deterministic harness mutation helpers
```

A candidate harness is never promoted because a model thinks it sounds better: the
deterministic replay battery (malicious + benign) and the promotion gate decide.
