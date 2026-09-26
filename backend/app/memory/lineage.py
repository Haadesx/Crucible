from collections import deque
from collections.abc import Sequence

from app.models.attack import AttackGenome, AttackRecord
from app.models.defense import DefenseGenome, DefenseRecord
from app.memory.repository import MemoryRepository


async def lineage_for_run(
    repository: MemoryRepository,
    run_id: str,
) -> tuple[list[AttackRecord], list[DefenseRecord]]:
    """Return the complete Red and Blue ancestry for a run, ordered by generation."""

    attacks = await repository.list_attacks(run_id)
    defenses = await repository.list_defenses(run_id)
    return (
        sorted(attacks, key=lambda record: (record.genome.generation, record.genome.id)),
        sorted(defenses, key=lambda record: (record.genome.generation, record.genome.id)),
    )


def ancestor_ids(
    genome_id: str,
    records: Sequence[AttackRecord] | Sequence[DefenseRecord],
) -> list[str]:
    """Walk parent links breadth-first and return ancestors without duplicates."""

    genomes: dict[str, AttackGenome | DefenseGenome] = {
        record.genome.id: record.genome for record in records
    }
    start = genomes.get(genome_id)
    queue = deque(start.parent_ids if start else [])
    ancestors: list[str] = []
    seen = {genome_id}
    while queue:
        parent_id = queue.popleft()
        if parent_id in seen:
            continue
        seen.add(parent_id)
        ancestors.append(parent_id)
        parent = genomes.get(parent_id)
        if parent is not None:
            queue.extend(parent.parent_ids)
    return ancestors
