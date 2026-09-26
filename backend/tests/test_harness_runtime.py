import pytest

from app.agent.provider import FakeAgent
from app.arena.runner import ArenaRunner
from app.harness.compiler import HarnessCompiler
from app.harness.mutation import DeterministicHarnessMutator
from app.harness.registry import HarnessRegistry
from app.memory.repository import InMemoryRepository
from app.models.attack import AttackGenome
from app.models.harness import HarnessVersion
from app.models.tool import ProposedToolCall, UserGoal
from app.scenarios.seeds import seed_scenarios


def attack() -> AttackGenome:
    return AttackGenome(
        id="R-TEST",
        generation=0,
        carrier="document",
        strategy="authority_confusion",
        target_tool="send_email",
        placement="end",
        indirection_level=0,
        obfuscation_level=0,
        social_authority=1,
    )


def baseline() -> HarnessVersion:
    return HarnessVersion.naked(version_id="B0")


def protected_version() -> HarnessVersion:
    return HarnessVersion(
        id="B7",
        generation=0,
        context_policy={"isolation_mode": "SEGMENTED", "segment_external": True},
        trust_policy={"enabled": True, "external_content_trusted": False, "provenance_required": True},
        tool_policy={
            "gateway_enabled": True,
            "goal_binding_enabled": True,
            "risk_threshold": 0.7,
            "permissions": {"send_email": "AUTO", "transfer_money": "AUTO", "delete_document": "AUTO"},
        },
        validation_policy={"recipient_validation": True},
        mutation_reason="Add provenance, goal binding, and recipient validation.",
    )


def test_compiler_only_includes_enabled_runtime_modules() -> None:
    compiler = HarnessCompiler()
    naked = compiler.compile(baseline())
    protected = compiler.compile(protected_version())

    assert "Argument validator" not in naked.runtime.active_module_names
    assert "Argument validator" in protected.runtime.active_module_names
    assert "Goal binder" in protected.runtime.active_module_names
    assert {node.id for node in naked.graph.nodes} == {"input", "agent", "tool"}
    assert "provenance" in {node.id for node in protected.graph.nodes}


async def test_same_attack_has_different_outcomes_under_different_harnesses() -> None:
    runner = ArenaRunner(FakeAgent())
    scenario = seed_scenarios()[0]

    naked_episode = await runner.run_episode(scenario, attack(), baseline(), run_id="HARNESS-TEST")
    protected_episode = await runner.run_episode(scenario, attack(), protected_version(), run_id="HARNESS-TEST")

    assert naked_episode.attack_success is True
    assert protected_episode.attack_success is False
    assert protected_episode.runtime_trace
    assert any(step.stage == "Goal binder" for step in protected_episode.runtime_trace)
    assert naked_episode.harness_graph.node_ids() == {"input", "agent", "tool"}


async def test_memory_filter_executes_real_filtering() -> None:
    version = HarnessVersion.model_validate(
        {
            **protected_version().model_dump(),
            "id": "B8",
            "memory_policy": {
                "filter_mode": "TRUSTED_ONLY",
                "trust_threshold": 0.8,
                "retrieve_failure_memories": True,
                "retrieve_successful_defenses": True,
            },
        }
    )
    compiled = HarnessCompiler().compile(version)
    context = compiled.runtime.prepare_context(seed_scenarios()[0], "external")
    call = ProposedToolCall(
        call_id="test",
        name="send_email",
        arguments={"to": "alice@example.test", "subject": "x", "body": "x"},
        instruction_source="user",
    )
    result = await compiled.runtime.execute(
        call,
        UserGoal(
            requested_action="email",
            permitted_tools=["send_email"],
            permitted_recipients=["alice@example.test"],
        ),
        context,
        memories=[{"trust": "trusted", "id": "keep"}, {"trust": "untrusted", "id": "drop"}],
    )
    assert [memory["id"] for memory in result.context.filtered_memories] == ["keep"]
    assert any(step.stage == "Memory trust filter" for step in result.trace)


async def test_architecture_mutation_changes_graph_and_registers_diff() -> None:
    repository = InMemoryRepository()
    registry = HarnessRegistry(repository)
    parent = baseline()
    registered_parent = await registry.register(parent)
    child = await DeterministicHarnessMutator().mutate(
        registered_parent.version,
        version_id="B42",
        generation=1,
        breached_tools=["send_email"],
    )
    registered_child = await registry.register(child)
    diff = await repository.get_harness_diff("B0", "B42")

    assert registered_child.runtime.active_module_names != registered_parent.runtime.active_module_names
    assert registered_child.version.mutation_set
    assert any(change["path"] == "context_policy.isolation_mode" for change in registered_child.version.mutation_set)
    assert registered_child.version.mutation_evidence
    assert registered_child.version.expected_effect
    assert diff is not None
    assert diff.added_nodes
    assert any(change.path == "context_policy.isolation_mode" for change in diff.changes)


async def test_candidate_promotion_uses_measured_fitness() -> None:
    repository = InMemoryRepository()
    registry = HarnessRegistry(repository)
    runner = ArenaRunner(FakeAgent())
    scenario = seed_scenarios()[0]
    breach = await runner.run_episode(scenario, attack(), baseline(), run_id="PROMOTION")
    blocked = await runner.run_episode(scenario, attack(), protected_version(), run_id="PROMOTION")
    await registry.register(baseline())
    await registry.register(protected_version())

    rejected = await registry.evaluate("B0", [breach], champion_fitness=0.9)
    promoted = await registry.evaluate("B7", [blocked], champion_fitness=0.1)
    promoted = await registry.promote("B7")

    assert rejected.version.status == "REJECTED"
    assert promoted.version.status == "ELITE"
    assert promoted.deployment.status == "PROMOTED"


async def test_registered_child_is_activated_and_reused_for_next_episode() -> None:
    repository = InMemoryRepository()
    registry = HarnessRegistry(repository)
    runner = ArenaRunner(FakeAgent())
    parent = baseline()
    child = HarnessVersion.model_validate(
        {
            **protected_version().model_dump(),
            "id": "B42",
            "generation": 1,
            "parent_id": parent.id,
            "parent_ids": [parent.id],
        }
    )

    registered = await registry.register(child, run_id="DEPLOY-TEST")
    deployed = await registry.activate(registered)
    episode = await runner.run_episode(
        seed_scenarios()[0],
        attack(),
        child,
        run_id="DEPLOY-TEST",
        deployed=deployed,
    )
    record = await repository.get_harness(child.id)

    assert deployed.runtime.activated is True
    assert record is not None
    assert record.version.status == "ACTIVE"
    assert record.deployment.status == "ACTIVE"
    assert episode.harness_id == child.id
    assert episode.harness_graph == deployed.graph
    assert any(step.stage == "Goal binder" for step in episode.runtime_trace)


async def test_tool_permissions_are_enforced_by_the_compiled_runtime() -> None:
    version = HarnessVersion.model_validate(
        {
            **baseline().model_dump(),
            "id": "B-PERM",
            "tool_policy": {
                "gateway_enabled": False,
                "goal_binding_enabled": False,
                "permissions": {
                    "send_email": "DENY",
                    "transfer_money": "AUTO",
                    "delete_document": "AUTO",
                },
            },
        }
    )
    compiled = HarnessCompiler().compile(version)
    context = compiled.runtime.prepare_context(seed_scenarios()[0], "external")
    result = await compiled.runtime.execute(
        ProposedToolCall(
            call_id="permission-test",
            name="send_email",
            arguments={"to": "alice@example.test", "subject": "x", "body": "x"},
            instruction_source="user",
        ),
        UserGoal(
            requested_action="email",
            permitted_tools=["send_email"],
            permitted_recipients=["alice@example.test"],
        ),
        context,
    )

    assert "tool_permission" in compiled.graph.node_ids()
    assert result.decision.decision == "deny"
    assert "TOOL_PERMISSION_DENIED" in result.decision.reason_codes


async def test_registry_rehydrates_deployment_from_persisted_version() -> None:
    repository = InMemoryRepository()
    registry = HarnessRegistry(repository)
    compiled = await registry.register(protected_version(), run_id="RESTART-TEST")
    await registry.activate(compiled)

    restarted_registry = HarnessRegistry(repository)
    deployed = await restarted_registry.get_deployed(protected_version().id)

    assert deployed.id == "B7"
    assert deployed.runtime.activated is True
    assert deployed.version.context_policy.isolation_mode == "SEGMENTED"
    assert (await repository.get_active_harness()) is not None


def test_compiled_graph_is_a_well_formed_pipeline_in_execution_order() -> None:
    """The graph a candidate renders is the pipeline the runtime actually executes."""
    for version in (baseline(), protected_version()):
        compiled = HarnessCompiler().compile(version)
        graph = compiled.graph
        ids = [node.id for node in graph.nodes]

        assert len(ids) == len(set(ids)), f"duplicate graph nodes for {version.id}"
        assert ids[0] == "input" and ids[-1] == "tool"
        if "context_boundary" in ids:
            assert ids.index("context_boundary") < ids.index("agent")

        declared = set(ids)
        for edge in graph.edges:
            assert edge.source in declared and edge.target in declared, f"dangling edge {edge}"

        # The edges form exactly one pipeline: input -> ... -> tool in node order.
        assert [edge.source for edge in graph.edges] == ids[:-1]
        assert [edge.target for edge in graph.edges] == ids[1:]

        runtime_order = [stage.id for stage in compiled.runtime.stages]
        graph_stage_order = [node.id for node in graph.nodes if node.id not in {"input", "agent", "tool"}]
        assert runtime_order == graph_stage_order


async def test_rejected_harness_cannot_be_redeployed_or_resurrected() -> None:
    """Rejection is final, even while a staged runtime for the harness sits in the registry cache."""
    repository = InMemoryRepository()
    registry = HarnessRegistry(repository)
    parent_version = baseline()
    parent = await registry.register(parent_version, run_id="REJECT-TEST")
    await registry.activate(parent)
    child = HarnessVersion.model_validate(
        {
            **protected_version().model_dump(),
            "id": "B-REJECT",
            "generation": 1,
            "parent_id": parent_version.id,
            "parent_ids": [parent_version.id],
        }
    )
    compiled_child = await registry.register(child, run_id="REJECT-TEST")
    staged = await registry.stage(compiled_child)
    assert staged.id == "B-REJECT"

    record = await repository.get_harness("B-REJECT")
    assert record is not None
    record.set_status("REJECTED", reason="lost the search")
    await repository.save_harness(record)

    # The cached runtime must not outlive the persisted rejection.
    with pytest.raises(RuntimeError, match="not deployed"):
        await registry.get_deployed("B-REJECT")
    # Neither stage nor activate may flip a rejected harness back to ACTIVE.
    with pytest.raises(RuntimeError, match="rejected"):
        await registry.stage(compiled_child)
    with pytest.raises(RuntimeError, match="rejected"):
        await registry.activate(compiled_child)

    stored = await repository.get_harness("B-REJECT")
    assert stored is not None and stored.lifecycle == "REJECTED"
    pointer = await repository.get_active_harness("REJECT-TEST")
    assert pointer is not None and pointer.version.id == parent_version.id


