"""Headless co-evolution runner: ``python -m app.coevolution --generations 3`` (§34).

Runs real Red attacks and real Blue patches, prints the per-generation transcript and
the run report, and exports the report plus optional training JSONL (§48, §49).
Fails loudly with a non-zero exit code when a model endpoint is unavailable (§33).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.coevolution.exports import write_all
from app.coevolution.providers import ProviderConfig, ProviderError, probe
from app.coevolution.runtime import assert_real_run, build_stack
from app.config import Settings


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.coevolution", description="DarwinGuard real co-evolution")
    parser.add_argument("--generations", type=int, default=3, help="number of generations to run")
    parser.add_argument("--red-versions", type=int, default=4, help="Red agent versions seeded at generation 0")
    parser.add_argument("--attacks-per-version", type=int, default=2, help="attack candidates per Red agent version")
    parser.add_argument(
        "--blue-candidates",
        type=int,
        default=3,
        help="harness candidate versions Blue proposes per generation (§25 asks for 3)",
    )
    parser.add_argument("--run-id", default=None, help="explicit run id (default: COEV-<timestamp>)")
    parser.add_argument(
        "--red-eval-attacks",
        type=int,
        default=1,
        help="attacks each Red mutation must play against the current champion before selection (§5)",
    )
    parser.add_argument(
        "--baseline",
        choices=("standard", "naked"),
        default="standard",
        help="starting Blue champion: 'standard' segmentation+risk gate, or 'naked' unguarded control",
    )
    parser.add_argument("--test-mode", action="store_true", help="allow deterministic stand-ins (never a real run)")
    parser.add_argument("--mode", choices=("real", "dev", "test"), default="real", help="label and enforce the run mode")
    parser.add_argument("--skip-probe", action="store_true", help="skip the pre-flight endpoint probe")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed for historical-champion sampling (§42); defaults to a value derived from the run id",
    )
    return parser.parse_args(argv)


def _banner(
    describe: dict[str, str], mode: str, is_mock: bool, red_team_mode: str = "BLACK_BOX"
) -> None:
    print(f"SPACE BUNNY — {mode} CO-EVOLUTION")
    print(f"RED MODEL   {describe['red']}")
    print(f"RED VISIBILITY  {red_team_mode}")
    print(f"BLUE MODEL  {describe['blue']}")
    print(f"BLUE ENGINEER  {describe.get('blue_engineer', 'same as blue')}")
    print(f"MONGODB     {describe['mongodb']}")
    print(f"VECTOR      {describe['vector_search']}")
    if is_mock:
        print("!! TEST/MOCK MODE — results are NOT a genuine co-evolution experiment (§33)")
    print("")


def _printer(event_type: str, payload: dict[str, Any]) -> None:
    if event_type == "attack_candidates_generated":
        print(f"  Red {payload.get('red_agent_version_id')} generated {payload.get('count')} candidate(s)")
    elif event_type == "red_agent_evolved":
        print(f"  Red evolved {payload.get('parent_id')} -> {payload.get('child_id')} prior={payload.get('tactic_prior')}")
    elif event_type == "red_candidate_promoted":
        print(
            f"  RED PROMOTED {payload.get('child_id')} over {payload.get('parent_id')} "
            f"fitness={payload.get('child_fitness')} (parent {payload.get('parent_fitness')}) :: {payload.get('reason')}"
        )
    elif event_type == "red_candidate_rejected":
        print(
            f"  RED REJECTED {payload.get('child_id')}; {payload.get('parent_id')} survives "
            f"fitness={payload.get('child_fitness')} (parent {payload.get('parent_fitness')}) :: {payload.get('reason')}"
        )
    elif event_type == "failure_analysis":
        print(f"FAILURE CLUSTER  {payload.get('memory_id')} episode={payload.get('episode_id')}")
    elif event_type == "harness_patch_proposed":
        operations = payload.get("patch", {}).get("operations", [])
        for operation in operations:
            print(f"  BLUE PROPOSED {operation.get('op')} {operation.get('target')}={operation.get('value')} :: {operation.get('reason')}")
    elif event_type == "harness_patch_unusable":
        print(f"  BLUE UNUSABLE no schema-valid patch in {payload.get('attempts')} attempt(s); candidates rejected")
    elif event_type == "candidate_compiled":
        print(f"  COMPILED {payload.get('harness_id')}")
    elif event_type == "harness_promoted":
        print(f"  PROMOTED {payload.get('harness_id')} fitness={payload.get('fitness'):.3f}")
    elif event_type == "harness_rejected":
        print(f"  REJECTED {payload.get('harness_id')} fitness={payload.get('fitness'):.3f} pareto_reject={payload.get('pareto_reject')}")
    elif event_type == "regression_completed":
        print(f"  REGRESSION benign_pass={payload.get('benign_pass')} ({payload.get('benign_total')} tasks)")
    elif event_type == "champion_comparison":
        historical = ", ".join(payload.get("historical_champions") or []) or "none"
        print(
            f"  CHAMPION SAMPLE historical=[{historical}] "
            f"candidates={payload.get('candidates')} generalizing={payload.get('generalizing')}"
        )
    elif event_type == "generation_finished":
        print(
            f"  GENERATION {payload.get('champion')}: ASR={payload.get('asr')} utility={payload.get('utility')} "
            f"red_fitness={payload.get('red_fitness'):.3f} blue_fitness={payload.get('blue_fitness'):.3f} "
            f"red_champion={payload.get('red_agent_champion')}"
        )
    print("")


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings().model_copy(update={"run_mode": args.mode.upper(), "test_mode": args.test_mode or args.mode == "test"})
    if settings.effective_run_mode == "REAL" and args.skip_probe:
        print("REALITY_ASSERTION_FAILED: --skip-probe is unavailable in REAL mode", file=sys.stderr)
        return 2
    if settings.effective_run_mode == "DEV":
        red_ready, blue_ready = True, True
        if not args.skip_probe:
            try:
                red_result, blue_result = await asyncio.gather(
                    probe(ProviderConfig.red(settings)),
                    probe(ProviderConfig.blue(settings)),
                )
            except ProviderError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            red_ready, blue_ready = red_result.reachable, blue_result.reachable
            if not red_ready:
                print(f"RED_PROVIDER_UNAVAILABLE: {red_result.detail}", file=sys.stderr)
            if not blue_ready:
                print(f"BLUE_PROVIDER_UNAVAILABLE: {blue_result.detail}", file=sys.stderr)
            if not (red_ready and blue_ready):
                print("Refusing to substitute a fake attacker/defender. Configure endpoints or pass --test-mode.", file=sys.stderr)
                return 2
    stack = None
    try:
        stack = await build_stack(settings, progress=_printer)
        if settings.effective_run_mode == "REAL":
            await assert_real_run(stack)
    except ProviderError as exc:
        if stack is not None:
            await stack.close()
        print(str(exc), file=sys.stderr)
        return 2
    _banner(stack.describe(), settings.effective_run_mode, stack.is_mock, settings.red_team_mode)
    from datetime import UTC, datetime

    run_id = args.run_id or f"COEV-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    try:
        report = await stack.engine.run(
            run_id=run_id,
            generations=args.generations,
            red_versions=args.red_versions,
            attacks_per_version=args.attacks_per_version,
            blue_candidates=args.blue_candidates,
            baseline=args.baseline,
            seed=args.seed,
            red_eval_attacks=args.red_eval_attacks,
        )
    except ProviderError as exc:
        print(f"{exc}", file=sys.stderr)
        await stack.close()
        return 2
    print("RUN REPORT")
    print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    report_path = export_dir / f"run_report_{run_id}.json"
    report_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2, default=str), encoding="utf-8")
    for name, rows in (await write_all(stack.repository, report, export_dir)).items():
        print(f"  {name}: {rows} row(s)")
    print(f"\nReport written to {report_path}")
    await stack.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
