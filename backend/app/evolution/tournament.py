from dataclasses import dataclass

from app.arena.fitness import group_episodes_by_id
from app.models.attack import AttackGenome
from app.models.defense import DefenseGenome
from app.models.episode import Episode
from app.models.scenario import Scenario
from app.scenarios.loader import ScenarioCatalog


@dataclass(frozen=True)
class Matchup:
    attack: AttackGenome
    defense: DefenseGenome
    scenario: Scenario
    episode_id: str


class TournamentScheduler:
    def __init__(self, catalog: ScenarioCatalog) -> None:
        self.catalog = catalog

    def create(
        self,
        red_population: list[AttackGenome],
        blue_population: list[DefenseGenome],
        *,
        run_id: str,
        generation: int,
        matchups_per_genome: int,
    ) -> list[Matchup]:
        if not red_population or not blue_population:
            return []
        blue_count = len(blue_population)
        matchups_per = min(matchups_per_genome, blue_count)
        stride = 2 if blue_count % 2 == 0 else 1
        matchups: list[Matchup] = []
        for red_index, attack in enumerate(red_population):
            seen: set[int] = set()
            for round_index in range(matchups_per):
                blue_index = (red_index + round_index * stride) % blue_count
                while blue_index in seen:
                    blue_index = (blue_index + 1) % blue_count
                seen.add(blue_index)
                defense = blue_population[blue_index]
                scenario = self.catalog.by_carrier(attack.carrier)
                matchups.append(
                    Matchup(
                        attack=attack,
                        defense=defense,
                        scenario=scenario,
                        episode_id=(
                            f"EP-{run_id}-G{generation:02d}-R{red_index:02d}-B{blue_index:02d}"
                        ),
                    )
                )
        return matchups


def score_by_genome(
    episodes: list[Episode],
    population: list[AttackGenome] | list[DefenseGenome],
    *,
    attack: bool,
) -> dict[str, float]:
    """Convenience wrapper used by the loop and tests."""

    grouped = group_episodes_by_id(episodes, "attack_id" if attack else "defense_id")
    return {genome.id: float(len(grouped.get(genome.id, []))) for genome in population}
