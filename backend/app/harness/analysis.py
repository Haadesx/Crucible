from __future__ import annotations

from app.models.episode import Episode
from app.models.harness import FailureAnalysis, HarnessVersion


class FailureAnalyzer:
    def analyze(
        self,
        episode: Episode,
        harness: HarnessVersion,
        *,
        historical_match_ids: list[str] | None = None,
        historical_similarity: float = 0.0,
        historical_adaptations: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> FailureAnalysis:
        executed = [call for call in episode.executed_tool_calls if call.result.success]
        tool = executed[-1].name if executed else "unknown"
        source = executed[-1].instruction_source if executed else "unknown"
        failed_stages = [step.stage for step in episode.runtime_trace if step.status == "FAIL"]
        if failed_stages:
            root_stage = failed_stages[-1]
        elif not harness.tool_policy.goal_binding_enabled and source != "user":
            root_stage = "Goal binder"
        elif not harness.validation_policy.recipient_validation and tool == "send_email":
            root_stage = "Argument validator"
        elif not harness.trust_policy.enabled and source != "user":
            root_stage = "Provenance boundary"
        else:
            root_stage = "Tool authorization gate"
        candidate_changes = self._candidate_changes(harness, tool, source)
        weakness = self._weakness(harness, tool, source, root_stage)
        return FailureAnalysis(
            episode_id=episode.id,
            harness_id=harness.id,
            root_stage=root_stage,
            weakness=weakness,
            observed_effect=f"{tool} executed from {source} despite the trusted user goal.",
            candidate_changes=candidate_changes,
            historical_match_ids=historical_match_ids or [],
            historical_similarity=historical_similarity,
            historical_adaptations=historical_adaptations or [],
            evidence=evidence or [],
        )

    @staticmethod
    def _candidate_changes(harness: HarnessVersion, tool: str, source: str) -> list[str]:
        changes: list[str] = []
        if not harness.tool_policy.goal_binding_enabled:
            changes.append("+ GoalBinderStage")
        if source != "user" and not harness.trust_policy.enabled:
            changes.append("+ ProvenanceBoundary")
        if tool == "send_email" and not harness.validation_policy.recipient_validation:
            changes.append("+ RecipientValidator")
        if tool == "transfer_money" and not harness.validation_policy.amount_validation:
            changes.append("+ AmountValidator")
        if tool == "delete_document" and not harness.validation_policy.resource_validation:
            changes.append("+ ResourceValidator")
        if not changes:
            changes.append("+ Provenance-aware risk multiplier")
        return changes

    @staticmethod
    def _weakness(harness: HarnessVersion, tool: str, source: str, root_stage: str) -> str:
        if root_stage == "Goal binder":
            return "External tool authority was not bound to the trusted user goal."
        if root_stage == "Provenance boundary":
            return "External content was treated as a trusted instruction source."
        if tool == "send_email":
            return "Recipient substitution was not rejected before tool execution."
        if tool == "transfer_money":
            return "Transfer amount or destination was not authorized against the goal."
        if tool == "delete_document":
            return "Resource identity was not authorized against the goal."
        return f"Runtime stage {root_stage} allowed an unsafe {tool} proposal."
