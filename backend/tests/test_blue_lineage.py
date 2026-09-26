"""Blue inheritance and selection, proven from persisted records (network-free).

One scripted run: the first candidate denies every tool and is rejected on utility, the
second binds tools to the goal and is promoted. Every assertion reads what the
repository stored, not engine internals.

Numbering gotcha: a search that runs while generation g is being played stamps its
patches generation g + 1 (engine.py passes next_generation), while GenerationRecord g
stores the champion *after* that search. So the champion a generation-G patch had to
inherit from is the champion stored in GenerationRecord G - 2, or the baseline for the
first search.
"""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any

import pytest

# tests/ has no __init__.py; pytest puts it on sys.path, so sibling test modules import bare.
from test_coevolution import PATCH_JSON, BlueScript, RedScript, _completion, _engine, _provider

from app.coevolution.suite import baseline_harness
from app.memory.repository import InMemoryRepository
from app.models.blue import HarnessPatchRecord

RUN = "T-LINEAGE"

LOCKDOWN = {
    "analysis": "Block every tool unconditionally.",
    "operations": [
        {"op": "SET_TOOL_PERMISSION", "target": tool, "value": "DENY", "reason": "lockdown"}
        for tool in ("send_email", "transfer_money", "delete_document")
    ],
    "expected_effect": "Nothing can be exfiltrated.",
}


class LockdownThenBind(BlueScript):
    """First engineer call is over-defensive (rejected); every later call is a real fix."""

    def __init__(self) -> None:
        super().__init__()
        self.proposals = 0

    def __call__(self, kwargs: Any) -> Any:
        prompt = "\n".join(str(message.get("content", "")) for message in kwargs["messages"])
        if "harness engineer" in prompt:
            self.proposals += 1
            return _completion(json.dumps(LOCKDOWN if self.proposals == 1 else PATCH_JSON))
        return super().__call__(kwargs)


async def _run() -> tuple[InMemoryRepository, list[HarnessPatchRecord], list[Any], str]:
    engine, repository = await _engine(
        _provider("RED", "test-red-model", RedScript()),
        _provider("BLUE", "test-blue-model", LockdownThenBind()),
    )
    await engine.run(run_id=RUN, generations=4, red_versions=1, attacks_per_version=1, blue_candidates=1)
    patches = sorted(
        (r for r in await repository.list_patch_records(RUN) if not r.id.endswith("-RESULT")),
        key=lambda r: r.generation,
    )
    generations = sorted(await repository.list_generations(RUN), key=lambda g: g.id)
    champion = await engine.registry.champion(RUN)
    assert champion is not None
    return repository, patches, generations, champion.id


def _champion_before(patch: HarnessPatchRecord, generations: list[Any]) -> str:
    """The champion in force when this patch was proposed, from generation records alone."""
    return generations[patch.generation - 2].blue_champion if patch.generation >= 2 else baseline_harness(RUN, 0).id


@pytest.mark.anyio
async def test_every_patch_inherits_from_the_champion_current_when_it_was_proposed() -> None:
    _, patches, generations, _ = await _run()

    assert len(patches) >= 2, "the script should have produced a rejection and a promotion"
    for patch in patches:
        assert patch.parent_harness_id == _champion_before(patch, generations), patch.id


@pytest.mark.anyio
async def test_a_rejected_candidate_never_becomes_the_champion() -> None:
    repository, patches, generations, final_champion = await _run()

    rejected = [p for p in patches if p.status == "REJECTED" and p.child_harness_id]
    assert rejected, "no candidate was compiled and then rejected"
    for patch in rejected:
        child = patch.child_harness_id
        record = await repository.get_harness(child)
        assert record is not None and record.deployment.status == "REJECTED"
        assert record.deployment.promoted_at is None
        # Unchanged champion: the generation record written right after the search still
        # names the parent, and so does the one after it unless something later won.
        assert generations[patch.generation - 1].blue_champion == patch.parent_harness_id
        assert child not in {g.blue_champion for g in generations}
        assert child not in {g.active_harness_id for g in generations}
        assert child != final_champion
        active = await repository.get_active_harness(RUN)
        assert active is not None and active.version.id != child


@pytest.mark.anyio
async def test_a_promoted_candidate_is_the_champion_in_the_next_record_and_the_registry() -> None:
    repository, patches, generations, final_champion = await _run()

    promoted = [p for p in patches if p.status == "PROMOTED"]
    assert promoted, "no candidate was promoted"
    for patch in promoted:
        child = patch.child_harness_id
        assert child is not None
        # Right after its search, and in the generation that then attacks it.
        assert generations[patch.generation - 1].blue_champion == child
        assert generations[patch.generation - 1].active_harness_id == child
        record = await repository.get_harness(child)
        assert record is not None and record.deployment.status == "PROMOTED"
        # The next generation's benign runs (always played by that generation's champion)
        # prove it was really the champion that generation ran with.
        nxt = patch.generation
        if nxt < len(generations) and generations[nxt].blue_champion == child:
            played = {
                e.harness_id
                for e in repository.episodes.values()
                if e.run_id == RUN and e.generation == nxt and e.attack_id.startswith("BENIGN-")
            }
            assert played == {child}
    assert final_champion == promoted[-1].child_harness_id
    active = await repository.get_active_harness(RUN)
    assert active is not None and active.version.id == final_champion


@pytest.mark.anyio
async def test_lineage_reconstructs_from_persisted_records() -> None:
    repository, patches, _, final_champion = await _run()

    patch_by_child = {p.child_harness_id: p for p in patches if p.child_harness_id}
    chain = [final_champion]
    while chain[-1] in patch_by_child:  # child harness -> the patch that made it -> its parent
        patch = patch_by_child[chain[-1]]
        assert patch.status == "PROMOTED", f"{patch.id} is on the champion chain but is {patch.status}"
        chain.append(patch.parent_harness_id)

    assert chain[-1] == baseline_harness(RUN, 0).id, "the chain must end at the opening baseline"
    assert len(chain) >= 2
    # The harness records agree with the patch records about who the parent is.
    for child, parent in pairwise(chain):
        record = await repository.get_harness(child)
        assert record is not None and record.version.parent_id == parent
