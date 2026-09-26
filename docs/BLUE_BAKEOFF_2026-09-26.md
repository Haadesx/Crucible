# DarwinGuard Blue Model Bake-Off — 2026-09-26

Isolated comparison of free OpenRouter models as Blue HarnessPatch engineers, using the
same real breach evidence from the verified runs, the production engineer prompt, the
production validator (`make_patch_validator` → dry-run `apply_patch`), the production
patcher and the production replay runner. No candidate was promoted: every candidate went
through `registry.rehearse` (isolated runtime, deployment state untouched) inside a scratch
in-memory repository. The episode executor was fixed to the currently configured Ling model
for every model, so only the engineer varied.

## Method

- **Cases:** five real Red-candidate breaches frozen from the verified snapshots —
  `OVERNIGHT-COEV-20260926-022643` G00 (2), `COEV-SEL2-20260926-013728` G00 (2),
  `COEV-SEL-20260926-011123` G01 (1). Each case carries its defending champion, the exact
  production breach summaries, utility failures, failure memory, prior patches, tool
  definitions, scenario brief and benign regression evidence (`cases.json`).
- **Attempts:** two proposals per case (production asks for multiple candidates per
  generation); the first valid candidate per case was compiled and replayed.
- **Replay battery:** every Red-candidate breach of that case's generation plus the benign
  suite, scored with the production `score_blue_spec`; “block” is the mean security score.
- **JSON-mode probe:** a minimal request with the exact feature production sends
  (`response_format={"type": "json_object"}`).

## Results

| Model | First-pass valid | Final valid | Compiles | Replay | Fitness | Utility | Avg latency | API problems |
|---|---|---|---|---|---|---|---|---|
| Ling 3.0 Flash Fin (control) | 4/5 | 5/5 | 5/5 | 5/5 | 0.6975 | 0.6667 | 2131 ms | JSON mode rejected (400); production fallback used; 5 ledgered call errors |
| Ling 3.0 Flash Sante | 1/5 | 5/5 | 5/5 | 5/5 | 0.6986 | 0.6667 | 7997 ms | JSON mode rejected (400); production fallback used; 9 ledgered call errors |
| **Nemotron 3 Super** | **5/5** | 5/5 | 5/5 | 5/5 | 0.6979 | 0.6667 | 12686 ms | **none** |
| Inkling Small | 0/10 | 0/10 | 0/5 | 0/5 | — | — | 306 ms | **403: “only available on agentic harnesses”** — unusable via API |
| North Mini Code | 0/5 | 5/5 | 5/5 | 5/5 | 0.6982 | 0.6667 | 57328 ms | 18 ledgered call errors; 3–7.5 min per patch |

“First-pass valid” counts accepted proposals that needed no real repair round; the single
extra ledger row that Ling models produce is the JSON-mode rejection being retried in place
by the production fallback, not a repair.

Baselines (unpatched champions on the same batteries): fitness 0.593 / 0.682 / 0.619,
block 0.80 / 0.90 / 0.89, benign 0.6667. Every valid candidate lifted block to **1.00** on
its battery with benign unchanged.

Per-case detail is in `experiments/blue-bakeoff/aggregates.json`; patches converged on the
same minimal fix (`recipient_validation=true`, often with `send_email=GOAL_BOUND`), and all
compiled to 7–10 graph nodes.

## Findings

1. **Structured-output support is the sharpest difference.** Only **Nemotron 3 Super** and
   **North Mini Code** accept `response_format=json_object` natively. Both Ling models are
   rejected with HTTP 400 (`does not support feature: structured-outputs`) and rely on the
   production in-place degradation; that fallback works, but it adds a failed transport row
   to every patch and is the source of all of the Lings' ledger errors. **Inkling Small is
   not usable at all** through a plain API key: OpenRouter returns 403 until it is plugged
   into an “agentic harness”.
2. **Patch quality converged; latency and stability decided the ranking.** All four usable
   models eventually produced valid, compiling, replay-blocking patches (5/5 final), and
   their fitness spread (0.680–0.705) is within battery noise. Only Nemotron produced valid
   patches on every first attempt with zero errors; Ling Fin was nearly as clean but needed
   one repair on case 5 and carries the JSON-fallback rows; Ling Sante needed 1–2 real
   repairs on four of five cases and took 33 s per patch; North Mini Code needed 3–5 retries
   per patch and took **2.8–7.5 minutes per case** (1488.8 s total) — unusable for anything
   interactive.
3. **No model regressed the benign suite** (0.6667 everywhere, same as the unpatched
   baseline). The battery's benign task that already failed is unrelated to these patches.
4. **No promotion, no production change.** Every candidate was rehearsed; the canonical
   harness and production configuration are untouched.

## Recommendation

- **PRIMARY BLUE: `nvidia/nemotron-3-super-120b-a12b:free`** — the only model that is
  natively JSON-mode compatible, 5/5 first-pass, zero errors, competitive patch quality, and
  a stable ~6–19 s per patch. Slower than Ling Fin per patch, but engineer calls are a small
  fraction of a generation (executor episodes dominate), and it removes the 400/fallback
  noise entirely.
- **FALLBACK BLUE: `inclusionai/ling-3.0-flash-fin:free`** (the current control) — proven in
  the real runs, 5/5 final valid, by far the fastest engineer (2.1 s average, 98 s total),
  provided the production JSON-mode fallback stays in place.
- Not recommended: **Ling Sante** (same fallback burden, 4× slower, repair-heavy),
  **North Mini Code** (minutes per patch, retry-heavy), **Inkling Small** (API-gated, unusable).

Production configuration was deliberately left unchanged, per the brief; switching
`BLUE_MODEL` to Nemotron is a one-line config change when the team decides.

## Artifacts

`backend/experiments/blue-bakeoff/`: `cases.json` (frozen evidence), `results.json` /
`results.csv` (per-attempt machine-readable), `table.md` / `aggregates.json` (rendered
summary), `run.log` (timeline), `build_cases.py` / `bakeoff.py` / `report.py` (tooling).
