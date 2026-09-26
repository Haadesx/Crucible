# Historical-Champion A/B Sampling — Verdict (t-ef575bb0)

Status: VERDICT RECORDED 2026-09-25 by Atlas. Follow-up t-c81c815c CLOSED 2026-09-25 by
Helios (deterministic end-to-end test delivered; see Residual gap below).
Scope: decide whether the §20/§42 historical-champion arm is unimplemented, mis-wired, or
failed by the proof script. Read-only analysis; no engine code changed; MongoDB not touched.

## Verdict

The historical-champion sampling path is **implemented and correctly wired**. It is not an
engine defect. DEF-ACCEPT-1's empty historical arm is **by design** given that run's state.
The `backend/ab_causality_proof.py` attempts are **wrong in expectation and broken in code**,
so they are not evidence about the engine either way.

## Evidence (file:line)

- `backend/app/coevolution/champions.py:63-77` — `sample_champions`: sorts by `ref_id`,
  draws deterministically from `sample_key`, and excludes the current champion
  (`exclude_id`, line 72).
- `champions.py:116-118` — `blue_hall_of_fame` reads Blue HoF entries for **this run**.
- `champions.py:145-150` — `measure` calls `sample_champions(..., exclude_id=champion.id)`.
- `champions.py:152-158` — each sampled champion is replayed through `registry.rehearse`,
  which leaves deployment state and stored metrics untouched; `judgement.sampled` records it.
- `champions.py:164-193` — one `current` comparison per candidate plus one `historical`
  comparison per sampled champion.
- `champions.py:194-207` — `generalizes` requires evidence: `bool(sampled) and beat_current
  and not survived`, else no generalisation is claimed.
- `backend/app/coevolution/engine.py:167-173` — `ChampionJudge` is wired to a real battle
  callback (`engine._execute` with the genome's carrier scenario).
- `engine.py:331-346` — `measure` runs every generation with the run's own HoF, before Blue
  adapts, so the compared champion is the one the candidates were just measured against; the
  sampled ids reach the report (`engine.py:127`) and the event stream (`engine.py:613`).

## Why DEF-ACCEPT-1's historical arm is empty (expected)

DEF promoted exactly one champion (B-DEF-ACCEPT-1-G01-C1); generations 0-2 never promoted a
second. `sample_champions` excludes the current champion, and in generations 1 and 2 C1 was
both the only HoF entry and the current champion, so the pool was empty. Generation 0 had no
HoF yet. Persisted report: 24 `champion_comparisons`, all `champion_kind=current` (8 per
generation), `sampled_champion_ids=[]`, and `generalizes=False` everywhere — consistent with
the code and with the honest-claim gate, not with a hardcoded outcome.

## Why the ab_causality_proof.py attempts fail (script, not engine)

- `/tmp/ab.log` (15:01) and `/tmp/ab2.log` (15:07) drove the production engine end-to-end and
  expected generation-2 `champion_comparisons` to include historical rows. After a single
  promotion the pool is empty by the exclusion rule above, so the expectation is arithmetically
  unachievable without a second promotion (or a cross-run pool, which the design does not have).
- The script is also broken before reaching the subject: the 15:11 revision crashed with
  `NameError: ArenaEventBus` (used at line 50, not imported at the time); the 15:12 revision
  crashed with `AttributeError: 'HarnessVersion' object has no attribute 'tactic_prior'` from
  calling `engine._scenario_for` with a Blue harness — that method expects a `RedAgentVersion`
  (`backend/app/models/red.py:30`; correct use at `engine.py:284`). The file was still being
  rewritten at 15:13.
- `/tmp/ab3.log` (15:13) is the surviving last revision and the most informative: it exercised
  the production path with `ChampionJudge.measure` against live `darwinguard_final` and PASSED
  the historical arm — 1 historical comparison row, sampled champions are the real records
  (`B-AB-CAUSAL2-G00-B0`). It then failed on two script-only bugs, not engine behaviour: it
  expected the isolated `rehearse` replay to persist an episode (only the current-arm battle
  does), then crashed with `TypeError: 'async_generator' object is not iterable` at line 155.
- WARNING unchanged: the 15:01/15:07 runs wiped `darwinguard_final` (`delete_many`); the
  on-disk 15:13 copy no longer contains it. Do not re-run any version without a backup.

## Reproducer that exercises the historical arm safely (no MongoDB)

Run from `backend/` with `uv run python -` and the snippet below. It uses the deterministic
test fixtures (`tests/test_coevolution.py`), an `InMemoryRepository`, seeds one non-current
champion into the HoF, and calls the production `ChampionJudge.measure`. Observed output:

```
champion: B-AB-DIRECT-G01-C1 | run hof: [('B-AB-DIRECT-G01-C1', 0.6749988888888889, 1)]
candidates: ['A-AB-DIRECT-G01-7abbda08']
  comparison current    candidate=A-...-7abbda08 vs B-AB-DIRECT-G01-C1 -> survived (hof_fitness=0.67499...)
  comparison historical candidate=A-...-7abbda08 vs B-AB-DIRECT-G00-BH -> survived (hof_fitness=0.4)
  signal sampled=['B-AB-DIRECT-G00-BH'] beat_current=False broken=[] survived=['B-AB-DIRECT-G00-BH'] generalizes=False
HISTORICAL ARM EXERCISED: True
```

Key steps: one generation via `engine.run(...)` to get a real promoted champion; register a
second harness (`champion.version.model_copy(update={"id": "B-<run>-G00-BH"})`) so `rehearse`
has a real persisted record; build a `HallOfFameEntry` for it; generate one real candidate with
the fixture Red provider; run `engine._execute` for the current-arm episode; then call
`engine.champions.measure(..., blue_hof=[*hof, hist_entry], ...)` and inspect the comparisons.

## Residual gap and recommendation

The arm is implemented, wired, and now directly exercised; the remaining gap was that **no run
had promoted at least two champions in one run**, so the historical arm had never fired in a
live end-to-end run.

RESOLVED (t-c81c815c, 2026-09-25): the new test
`backend/tests/test_coevolution.py::test_two_same_run_promotions_produce_a_historical_comparison_end_to_end`
now drives the production flow through two same-run promotions (gen-1 champion fitness
0.6229, gen-2 0.6528) and asserts that the generation-2 run report carries a
`champion_kind=historical` `ChampionComparison` against the first champion plus an
`AntiOverfittingSignal` with a non-empty `sampled_champion_ids`. Deterministic, in-memory, no
MongoDB. Evidence: full backend suite 165 passed, ruff clean on `app/ tests/`. The
`ab_causality_proof.py` script is still unowned and must not be re-run without a backup — that
caveat is unchanged.
