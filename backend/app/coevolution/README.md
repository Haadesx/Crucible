# DarwinGuard co-evolution — package structure

How the code is arranged, which piece owns what, and which way data flows. This is a
map for later changes: read it before adding a module, and update it when you move a
boundary.

## Data flow

```
providers ──▶ red / blue agents ──▶ engine ──▶ repository ──▶ exports ──▶ __main__
 (real LLM)     (what to attack,     (the loop)   (the only      (JSONL)    (prints)
                 what to patch)                     durable state)
```

Data moves strictly left to right. Nothing downstream is imported by anything upstream:
the engine never imports the exporters, the exporters never import the engine, and the
CLI imports both only to call them. Every artifact the run produces — episodes, patch
records, the ledger, the report, the exports — is written through the repository, so a
run can be reconstructed from persisted records alone.

## Modules

| Module | Owns | Knows nothing about |
|---|---|---|
| `providers.py` | OpenAI-compatible HTTP, JSON repair, the model-call ledger | the experiment |
| `red.py` | Red agent: attack candidates, self-evolution | Blue, the arena |
| `blue.py` | Blue executor turns and the harness engineer | Red, promotion |
| `patcher.py` | Patch operations → policy switches (compiler-facing) | the loop, scoring |
| `suite.py` | Scenarios, benign suite, holdout attacks, baseline harness | models |
| `champions.py` | §20/§42: which Blue champions a candidate is measured against, and the verdict | promotion, scoring |
| `engine.py` | The co-evolution loop and the harness lifecycle | file formats, printing |
| `exports.py` | §49: turning persisted records into JSONL | scoring, promotion, the loop |
| `runtime.py` | Assembly: build the repository, providers, engine | any specific experiment step |
| `__main__.py` | CLI: parse args, probe, print, delegate | experiment internals |

## State ownership

- **The repository owns all durable state.** `MemoryRepository` is the only thing that
  survives a run, and both adapters (in-memory, Mongo) hold the same contract.
- **`RunLedger` owns the run's counters** and is the only place a `RunReport` is built,
  so a counter cannot be added to the loop without appearing in the report.
- **`ChampionJudge` owns the Blue hall of fame read** for a generation. The engine asks
  it once and does not re-query.
- **The engine owns nothing across a call.** It holds collaborators, not results. A
  battle is run by a `RunBattle` callable that takes `(genome, harness, run_id,
  generation)` explicitly — run context travels with the call rather than being read
  from engine attributes, so a replay cannot be filed under the wrong run.
- **`HarnessRegistry` owns the champion.** `registry.champion(run_id)` is the only
  answer to "which harness is the champion for this run", and it is a pure read of
  that run's persisted deployment records — it writes nothing, and nothing outside
  the run can change it. So it survives a restart, a second engine on the same
  repository, and a run re-entered after an interruption. The engine re-reads it at
  each generation, the report reads it, and the `/harnesses/active` endpoint answers
  through it; none of them keeps a copy.
- **The active-harness pointer is published state, not an input.** It is scoped per
  run, so two runs sharing a repository cannot overwrite each other, and it is
  written only by `activate` and `promote` — the operations that genuinely change who
  is live. A pointer left naming a rejected or foreign harness therefore never
  influences an answer; `sync_pointer`, called when a run opens, heals it on the next
  write. `stage` makes a candidate runnable for scoring without claiming anything.
- **`HarnessRecord` owns the harness lifecycle.** `deployment.status` is the single
  fact; `version.status` and `metrics.candidate_status` are that same fact in the
  candidate vocabulary, rendered by `LIFECYCLE_RENDERING` and written only through
  `HarnessRecord.set_status`, which is also what re-derives them on load.

## Two rules that are now structural, not conventional

**One evaluation battery.** Champion and candidate are both scored by `_run_battery`,
which composes this generation's attacks, the Red hall of fame, the benign regression
suite, and the holdout set. "Measured on an identical battery" is therefore a property
of the code rather than a promise two call sites have to keep honouring. Scores are
written onto a harness record by `_apply_scores` for the same reason.

**Deterministic champion sampling.** `sample_champions` sorts the population by harness
id before drawing, because repository listing order differs between adapters and an
unsorted draw would silently produce a different sample per backend for one seed.

**One champion, one lifecycle.** A harness's position in its life is stored once and
projected, and the harness Red is measured against is named once. Both were previously
held in several places at once — an engine local, the active-harness pointer, a
repository guess and a three-field status triple — any of which could answer
differently after a restart, which is how Red ends up scored against a harness that
lost without anything saying so.

## Where to put new work

- A new measurement or scoring rule → its own module next to `champions.py`, taking
  the collaborators it needs explicitly.
- A new output file → `exports.py`, not the CLI.
- A new per-generation bookkeeping step → a named method on the engine, like
  `_record_generation`.
- Anything that changes a stored number → behind the repository contract, in both
  adapters.
