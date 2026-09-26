import asyncio

from app.config import Settings
from app.dependencies import build_container
from app.models.generation import ArenaStartRequest


async def _print_battles(container: object) -> None:
    # The container is intentionally duck-typed here to keep the demo output
    # independent of the FastAPI application lifecycle.
    async for event in container.event_bus.subscribe():  # type: ignore[attr-defined]
        if event.type != "battle_finished":
            continue
        episode = event.payload.get("episode")
        if not isinstance(episode, dict):
            continue
        winner = episode.get("winner")
        # Episode serializes its fields; winner is a property and is added for logs.
        if winner is None:
            if episode.get("attack_success") and episode.get("legitimate_task_success"):
                winner = "RED"
            elif not episode.get("attack_success") and episode.get("legitimate_task_success"):
                winner = "BLUE"
            else:
                winner = "BLUE (utility failure)"
        print(
            f"[G{int(episode.get('generation', 0)):02d}] "
            f"{episode.get('attack_id')} × {episode.get('defense_id')} "
            f"[{episode.get('scenario_id')}] → {winner} "
            f"ASR={'BREACH' if episode.get('attack_success') else 'BLOCKED'} "
            f"UTILITY={'PASS' if episode.get('legitimate_task_success') else 'FAIL'}"
        )


async def run_demo() -> None:
    settings = Settings(
        agent_provider="fake",
        mutation_provider="deterministic",
        use_change_streams=False,
        use_vector_search=False,
        demo_mode=True,
    )
    container = await build_container(settings)
    printer = asyncio.create_task(_print_battles(container))
    try:
        print("DARWINGUARD")
        print("Offline deterministic co-evolution demo — all tools are sandboxed.\n")
        run_id = await container.evolution.start(
            ArenaStartRequest(
                generations=3,
                red_population=4,
                blue_population=4,
                matchups_per_genome=2,
            )
        )
        await container.evolution.wait()
        print("\nGeneration fitness")
        for generation in await container.repository.list_generations(run_id):
            print(
                f"G{generation.id:02d}  "
                f"ASR={generation.attack_success_rate:.2f}  "
                f"UTILITY={generation.utility_rate:.2f}  "
                f"RED={generation.red_mean_fitness:.2f}  "
                f"BLUE={generation.blue_mean_fitness:.2f}"
            )
        attacks = await container.repository.list_attacks(run_id)
        defenses = await container.repository.list_defenses(run_id)
        print(f"\nStored {len(await container.repository.list_generations(run_id))} generations, "
              f"{len(attacks)} Red genomes, {len(defenses)} Blue genomes, and "
              f"{len(await container.repository.list_attacks(run_id))} lineage records.")
        print("Evolution complete.")
    finally:
        printer.cancel()
        await asyncio.gather(printer, return_exceptions=True)
        await container.close()


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
