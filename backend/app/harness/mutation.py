from __future__ import annotations

from typing import Any

from app.models.harness import FailureAnalysis, HarnessChange, HarnessMutation, HarnessVersion


class DeterministicHarnessMutator:
    """Mutate the executable architecture, not an untyped prompt or switch bag."""

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed

    async def mutate(
        self,
        parent: HarnessVersion,
        *,
        version_id: str,
        generation: int,
        breached_tools: list[str] | None = None,
        analyses: list[FailureAnalysis] | None = None,
        historical_failures: list[dict[str, Any]] | None = None,
    ) -> HarnessVersion:
        breached_tools = breached_tools or []
        analyses = analyses or []
        historical_failures = historical_failures or []
        changes: list[HarnessChange] = []

        def add(path: str, value: str | float | bool) -> None:
            if all(change.path != path for change in changes):
                changes.append(HarnessChange(path=path, value=value))

        if parent.context_policy.isolation_mode == "FLAT":
            add("context_policy.isolation_mode", "SEGMENTED")
        if not parent.trust_policy.enabled:
            add("trust_policy.enabled", True)
            add("trust_policy.external_content_trusted", False)
        if not parent.tool_policy.goal_binding_enabled:
            add("tool_policy.goal_binding_enabled", True)
        if "send_email" in breached_tools and not parent.validation_policy.recipient_validation:
            add("validation_policy.recipient_validation", True)
        if "transfer_money" in breached_tools and not parent.validation_policy.amount_validation:
            add("validation_policy.amount_validation", True)
        if "delete_document" in breached_tools and not parent.validation_policy.resource_validation:
            add("validation_policy.resource_validation", True)
        if parent.memory_policy.filter_mode == "OFF":
            add("memory_policy.filter_mode", "TRUSTED_ONLY")
        if breached_tools and not parent.verifier_policy.enabled and len(changes) < 5:
            add("verifier_policy.enabled", True)
        if not changes:
            # A no-breach candidate still explores a bounded risk change.
            add("trust_policy.untrusted_risk_multiplier", min(2.0, round(parent.trust_policy.untrusted_risk_multiplier + 0.15, 2)))
        evidence = [
            f"{len(breached_tools)} breached tool(s): {', '.join(sorted(set(breached_tools)))}"
            if breached_tools
            else "no breach in sampled battles",
            f"{len(analyses)} deterministic failure analyses",
        ]
        if historical_failures:
            evidence.append(f"{len(historical_failures)} similar historical failure(s) retrieved")
        historical_ids = [str(item.get("id")) for item in historical_failures if item.get("id")]
        expected = self._expected_effect(parent, changes)
        mutation = HarnessMutation(
            parent_id=parent.id,
            reasoning_summary=self._reason(changes, analyses, historical_failures),
            changes=changes[:6],
            evidence=evidence,
            expected_effect=expected,
            historical_matches=historical_ids,
        )
        return mutation.apply(parent, version_id=version_id, generation=generation)

    @staticmethod
    def _reason(
        changes: list[HarnessChange],
        analyses: list[FailureAnalysis],
        historical_failures: list[dict[str, Any]],
    ) -> str:
        evidence = ", ".join(analysis.root_stage for analysis in analyses[:3]) or "baseline weakness"
        history = f" Similar memory: {historical_failures[0].get('id')}." if historical_failures else ""
        change_text = ", ".join(f"{change.path}→{change.value}" for change in changes)
        return f"Observed {evidence}.{history} Proposed executable architecture change: {change_text}."

    @staticmethod
    def _expected_effect(parent: HarnessVersion, changes: list[HarnessChange]) -> str:
        paths = {change.path for change in changes}
        effects: list[str] = []
        if "context_policy.isolation_mode" in paths or "trust_policy.enabled" in paths:
            effects.append("raise risk for external instructions")
        if "tool_policy.goal_binding_enabled" in paths or any("validation_policy" in path for path in paths):
            effects.append("bind side effects to the trusted goal")
        if "memory_policy.filter_mode" in paths:
            effects.append("exclude untrusted memory from context")
        if "verifier_policy.enabled" in paths:
            effects.append("route high-risk proposals to deterministic verification")
        return "; ".join(effects) or "explore a bounded provenance-risk change"
