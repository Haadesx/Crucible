import random
from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar


class HasId(Protocol):
    id: str


T = TypeVar("T", bound=HasId)


def select_elites(population: Sequence[T], scores: Mapping[str, float], count: int = 2) -> list[T]:
    """Keep the highest measured scores; ties resolve by original population order."""

    ranked = sorted(enumerate(population), key=lambda item: (-scores.get(str(item[1].id), 0.0), item[0]))
    return [population[index] for index, _ in ranked[:count]]


def choose_parents(
    population: Sequence[T],
    scores: Mapping[str, float],
    count: int,
    seed: int,
) -> list[T]:
    """Use elites most of the time and one deterministic exploration sample per child."""

    if not population:
        return []
    ranked = sorted(enumerate(population), key=lambda item: (-scores.get(str(item[1].id), 0.0), item[0]))
    elites = [population[index] for index, _ in ranked[: min(2, len(population))]]
    non_elites = [population[index] for index, _ in ranked[2:]]
    rng = random.Random(seed)
    parents: list[T] = []
    for index in range(count):
        if non_elites and (index == 0 or rng.random() < 0.30):
            parents.append(rng.choice(non_elites))
        else:
            parents.append(rng.choice(elites))
    return parents
