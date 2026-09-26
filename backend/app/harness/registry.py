from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.arena.fitness import score_blue
from app.harness.compiler import CompiledHarness, HarnessCompiler
from app.harness.runtime import RuntimeHarness
from app.models.episode import Episode
from app.models.harness import (
    HarnessDeployment,
    HarnessDeploymentStatus,
    HarnessDiff,
    HarnessDiffChange,
    HarnessGraph,
    HarnessMetrics,
    HarnessRecord,
    HarnessVersion,
)
from app.memory.repository import MemoryRepository


# A harness is "deployed" while it is live: the baseline a run starts from and every
# promoted champion. A candidate being scored is not deployed, and neither is a
# candidate that lost — which is the whole reason a rejected harness can never be
# read back as the champion.
DEPLOYED_STATUSES: frozenset[HarnessDeploymentStatus] = frozenset({"ACTIVE", "PROMOTED"})


@dataclass(frozen=True)
class DeployedHarness:
    """A compiled runtime activated for execution under a persisted deployment."""

    version: HarnessVersion
    runtime: RuntimeHarness
    graph: HarnessGraph
    deployment: HarnessDeployment

    @property
    def id(self) -> str:
        return self.version.id


class HarnessRegistry:
    """Git-like registry for executable runtime harness versions."""

    def __init__(self, repository: MemoryRepository, compiler: HarnessCompiler | None = None) -> None:
        self.repository = repository
        self.compiler = compiler or HarnessCompiler()
        self._deployed: dict[str, DeployedHarness] = {}

    def reset(self) -> None:
        self._deployed.clear()

    async def register(self, version: HarnessVersion, *, run_id: str | None = None) -> CompiledHarness:
        compiled = self.compiler.compile(version)
        self._deployed.pop(version.id, None)
        existing = await self.repository.get_harness(version.id)
        parent_record = await self.repository.get_harness(version.parent_id) if version.parent_id else None
        deployment = HarnessDeployment(
            id=f"DEP-{version.id}",
            version_id=version.id,
            status="COMPILED",
            compiled_at=compiled.version.compiled_at,
            reason="Compiled executable runtime graph before evaluation.",
        )
        record = HarnessRecord(
            version=compiled.version.model_copy(update={"run_id": run_id}),
            deployment=deployment,
            metrics=HarnessMetrics(candidate_status="COMPILED"),
            created_at=version.created_at,
        )
        await self.repository.save_harness(record)
        if parent_record is not None:
            diff = self.diff(parent_record.version, compiled.version)
            await self.repository.save_harness_diff(diff)
        if existing is not None and existing.lifecycle in DEPLOYED_STATUSES:
            record.set_status(existing.lifecycle, reason=existing.deployment.reason)
            record.deployment.activated_at = existing.deployment.activated_at
            record.deployment.promoted_at = existing.deployment.promoted_at
            await self.repository.save_harness(record)
        return compiled

    def rehearse(self, version: HarnessVersion) -> DeployedHarness:
        """Compile an isolated runtime for replay without changing deployment state."""

        compiled = self.compiler.compile(version)
        active_version = compiled.runtime.activate()
        now = active_version.activated_at
        deployment = HarnessDeployment(
            id=f"REPLAY-{version.id}",
            version_id=version.id,
            status="ACTIVE",
            compiled_at=compiled.version.compiled_at,
            activated_at=now,
            reason="Ephemeral replay runtime; persisted lifecycle is unchanged.",
        )
        return DeployedHarness(
            version=active_version,
            runtime=compiled.runtime,
            graph=compiled.graph,
            deployment=deployment,
        )

    async def activate(self, compiled: CompiledHarness) -> DeployedHarness:
        """Make this harness the live one: the champion, by an explicit decision.

        This, :meth:`promote` and :meth:`sync_pointer` are the only things that move
        the active-harness pointer, and all three are writes. Everything that merely
        needs a runtime uses :meth:`stage` instead, so scoring a candidate can never
        quietly steal the champion slot.
        """

        deployed = await self.stage(compiled)
        await self._point_at(deployed.version)
        return deployed

    async def stage(self, compiled: CompiledHarness) -> DeployedHarness:
        """Make a harness runnable for evaluation without claiming the champion slot.

        Rejection is final: a harness the repository has marked REJECTED is refused
        rather than flipped back to ACTIVE, which is what stops :meth:`activate` (and
        any other caller) from resurrecting a candidate the search already lost.
        """

        active_version = compiled.runtime.activate()
        existing = await self.repository.get_harness(active_version.id)
        if existing is None:
            raise KeyError(f"harness {active_version.id} is not registered")
        if existing.lifecycle == "REJECTED":
            raise RuntimeError(f"harness {active_version.id} is rejected and cannot be staged or activated")
        # The freshly compiled version knows nothing about which run owns the record.
        # Carrying the stored ownership across keeps the champion answer run-scoped
        # instead of silently widening to "whatever harness was activated last".
        active_version = active_version.model_copy(update={"run_id": existing.version.run_id})
        existing.version = active_version
        existing.set_status("ACTIVE")
        existing.deployment.activated_at = active_version.activated_at
        await self.repository.save_harness(existing)
        deployed = DeployedHarness(
            version=active_version,
            runtime=compiled.runtime,
            graph=compiled.graph,
            deployment=existing.deployment.model_copy(deep=True),
        )
        self._deployed[active_version.id] = deployed
        return deployed

    async def champion(self, run_id: str | None = None) -> DeployedHarness | None:
        """The one answer to "which harness is the champion for this run".

        The registry owns the whole lifecycle, so it - not the engine, not a local
        variable, not a status field read in isolation - is what decides.

        This is a pure read. It looks only at the persisted deployment records of the
        run it is asked about, writes nothing, and is ordered so the answer is a
        function of those records alone: a promotion outranks the run's opening
        baseline, the newest promotion wins, and the id breaks any remaining tie so
        two repository adapters cannot disagree. Nothing outside the run is consulted,
        so one run cannot change another run's answer, and reading twice - including
        from a registry with an empty cache - changes no field.
        """

        best = self._champion_record(await self.repository.list_harnesses(run_id), run_id)
        return None if best is None else self._restored(best)

    async def sync_pointer(self, run_id: str) -> str | None:
        """Point this run's active-harness slot at its champion, and return the id.

        The pointer is published state, not an input: resolution never reads it. It is
        written here, on the operations that genuinely change who is live, so a
        pointer left naming a rejected or foreign harness is healed by the next write
        rather than by somebody asking a question.
        """

        best = self._champion_record(await self.repository.list_harnesses(run_id), run_id)
        if best is None:
            return None
        await self._point_at(best.version)
        return best.version.id

    def _champion_record(self, records: list[HarnessRecord], run_id: str | None) -> HarnessRecord | None:
        """Rank a run's records: the newest promotion, else the opening baseline."""

        eligible = [record for record in records if _is_champion(record, run_id)]
        if not eligible:
            return None
        return max(eligible, key=_champion_rank)

    async def _point_at(self, version: HarnessVersion) -> None:
        if version.run_id is not None:
            await self.repository.set_active_harness(version.run_id, version.id)

    async def get_deployed(self, harness_id: str) -> DeployedHarness:
        """An executable handle for a harness the repository currently deploys.

        The cache is a convenience, not the authority: a candidate can be rejected
        after it was staged, and a cache hit must not keep a rejected runtime
        deployable. So the persisted lifecycle is read first and the cached handle is
        reused only while it still describes that lifecycle.
        """

        record = await self.repository.get_harness(harness_id)
        if record is None:
            self._deployed.pop(harness_id, None)
            raise KeyError(f"harness {harness_id} is not registered")
        if record.lifecycle not in DEPLOYED_STATUSES:
            self._deployed.pop(harness_id, None)
            raise RuntimeError(f"harness {harness_id} is not deployed")
        cached = self._deployed.get(harness_id)
        if cached is not None and cached.deployment.status == record.lifecycle:
            return cached
        return self._restored(record)

    def _restored(self, record: HarnessRecord) -> DeployedHarness:
        """An executable handle for a persisted record, rebuilt without writing.

        Reading a harness must not change it. This used to re-activate the record on
        the way through, which re-stamped activated_at - the very field its own
        ordering depends on.
        """

        compiled = self.compiler.compile(record.version)
        compiled.runtime.activate()
        deployed = DeployedHarness(
            version=record.version,
            runtime=compiled.runtime,
            graph=compiled.graph,
            deployment=record.deployment.model_copy(deep=True),
        )
        self._deployed[record.version.id] = deployed
        return deployed

    async def evaluate(
        self,
        version_id: str,
        episodes: list[Episode],
        *,
        champion_fitness: float | None = None,
    ) -> HarnessRecord:
        record = await self.repository.get_harness(version_id)
        if record is None:
            raise KeyError(f"harness {version_id} is not registered")
        if any(episode.harness_id != version_id for episode in episodes):
            raise ValueError(f"evaluation episodes do not belong to harness {version_id}")
        # Scoring needs only the episodes; it never touches a runtime, so a candidate is
        # not staged to be scored. Re-opening a rejected record here is the arena
        # tournament's per-generation semantics and stays out of stage()/activate(),
        # which must never make a rejected harness deployable again.
        score = score_blue(episodes)
        record.metrics = HarnessMetrics(
            fitness=score["fitness"],
            block_rate=score["block_rate"],
            utility_rate=score["utility_rate"],
            attack_coverage=score["block_rate"],
            battles=len(episodes),
        )
        record.version.fitness = score["fitness"]
        record.version.attack_coverage = score["block_rate"]
        record.version.utility_score = score["utility_rate"]
        record.set_status("ACTIVE", reason="Scored against the champion's battery.")
        await self.repository.save_harness(record)
        if champion_fitness is not None and score["fitness"] > champion_fitness:
            await self.promote(version_id)
        else:
            record = await self.repository.get_harness(version_id) or record
            record.set_status("REJECTED", reason="Did not beat the champion.")
            await self.repository.save_harness(record)
        return record

    async def promote(self, version_id: str) -> HarnessRecord:
        record = await self.repository.get_harness(version_id)
        if record is None:
            raise KeyError(f"harness {version_id} is not registered")
        now = datetime.now(UTC)
        record.set_status("PROMOTED", reason="Promoted over the current champion.")
        record.version.promoted_at = now
        record.deployment.promoted_at = now
        await self.repository.save_harness(record)
        await self._point_at(record.version)
        return record

    def diff(self, before: HarnessVersion, after: HarnessVersion) -> HarnessDiff:
        paths = [
            "context_policy.isolation_mode",
            "context_policy.segment_external",
            "trust_policy.enabled",
            "trust_policy.external_content_trusted",
            "trust_policy.tool_outputs_trusted",
            "trust_policy.untrusted_risk_multiplier",
            "trust_policy.provenance_required",
            "memory_policy.filter_mode",
            "memory_policy.trust_threshold",
            "tool_policy.gateway_enabled",
            "tool_policy.goal_binding_enabled",
            "tool_policy.risk_threshold",
            "tool_policy.permissions.send_email",
            "tool_policy.permissions.transfer_money",
            "tool_policy.permissions.delete_document",
            "validation_policy.input_classifier_enabled",
            "validation_policy.input_classifier_threshold",
            "validation_policy.recipient_validation",
            "validation_policy.amount_validation",
            "validation_policy.resource_validation",
            "approval_policy.email",
            "approval_policy.transfer",
            "approval_policy.delete",
            "verifier_policy.enabled",
            "verifier_policy.verifier_model",
            "verifier_policy.trigger_threshold",
            "system_instruction_policy.variant",
        ]
        changes: list[HarnessDiffChange] = []
        for path in paths:
            old = _read_path(before, path)
            new = _read_path(after, path)
            if old != new:
                changes.append(HarnessDiffChange(path=path, before=old, after=new, kind="changed"))
        old_nodes = {node.id for node in before.runtime_graph.nodes if node.enabled}
        new_nodes = {node.id for node in after.runtime_graph.nodes if node.enabled}
        return HarnessDiff(
            from_version=before.id,
            to_version=after.id,
            changes=changes,
            added_nodes=sorted(new_nodes - old_nodes),
            removed_nodes=sorted(old_nodes - new_nodes),
            summary=f"{len(changes)} policy changes · {len(new_nodes - old_nodes)} runtime modules added",
        )


def _is_champion(record: HarnessRecord | None, run_id: str | None) -> bool:
    """Could this record be the champion? Deployed, ours, and actually decided.

    A generation above 0 that is merely ACTIVE was staged for scoring and never
    reached a verdict; a process that died mid-evaluation leaves exactly that behind,
    and it is not something Red should be measured against.
    """

    if record is None or record.lifecycle not in DEPLOYED_STATUSES:
        return False
    if run_id is not None and record.version.run_id != run_id:
        return False
    return record.lifecycle == "PROMOTED" or record.version.generation == 0


def _champion_rank(record: HarnessRecord) -> tuple[bool, datetime, str]:
    """Newest promotion wins; the opening baseline is the only other candidate."""

    promoted = record.lifecycle == "PROMOTED"
    when = record.deployment.promoted_at or record.deployment.activated_at or record.created_at
    return (promoted, when, record.version.id)


def _read_path(value: HarnessVersion, path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        current = current.get(part) if isinstance(current, dict) else getattr(current, part)
    return current
