import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.agent.provider import AgentRequest, TargetAgent
from app.arena.evaluator import DeterministicEvaluator
from app.arena.payload import PayloadRenderer
from app.harness.compiler import HarnessCompiler, PolicyCompiler
from app.harness.gateway import PolicyGateway
from app.harness.registry import DeployedHarness
from app.models.attack import AttackGenome
from app.models.defense import DefenseGenome
from app.models.episode import Episode
from app.models.harness import HarnessVersion
from app.models.events import ArenaEvent, ArenaEventType
from app.models.scenario import Scenario
from app.models.tool import ExecutedToolCall
from app.sandbox.state import SandboxState

EventSink = Callable[[ArenaEvent], Awaitable[None]]


class ArenaRunner:
    def __init__(
        self,
        agent: TargetAgent,
        gateway: PolicyGateway | None = None,
        compiler: PolicyCompiler | None = None,
        harness_compiler: HarnessCompiler | None = None,
        renderer: PayloadRenderer | None = None,
        evaluator: DeterministicEvaluator | None = None,
    ) -> None:
        self.agent = agent
        self.gateway = gateway or PolicyGateway()
        self.compiler = compiler or PolicyCompiler()
        self.harness_compiler = harness_compiler or HarnessCompiler()
        self.renderer = renderer or PayloadRenderer()
        self.evaluator = evaluator or DeterministicEvaluator()

    async def run_episode(
        self,
        scenario: Scenario,
        attack: AttackGenome | None,
        defense: DefenseGenome | HarnessVersion,
        *,
        run_id: str = "RUN-LOCAL",
        generation: int | None = None,
        episode_id: str | None = None,
        event_sink: EventSink | None = None,
        deployed: DeployedHarness | None = None,
    ) -> Episode:
        """Run one episode. ``attack=None`` runs the attack-free benign regression task (§17)."""
        started = time.perf_counter()
        generation = (attack.generation if attack is not None else 0) if generation is None else generation
        episode_id = episode_id or f"EP-G{generation:02d}-{uuid4().hex[:10]}"
        attack_id = attack.id if attack is not None else f"BENIGN-{scenario.id}"
        if attack is None:
            injected_content = scenario.base_content
            attack_payload = ""
        else:
            rendered = self.renderer.render(attack, scenario.base_content)
            injected_content = rendered.injected_content
            attack_payload = rendered.payload
        injected_scenario = scenario.model_copy(update={"base_content": injected_content})
        harness_version = defense if isinstance(defense, HarnessVersion) else HarnessVersion.from_defense(defense)
        if deployed is None:
            compiled_harness = self.harness_compiler.compile(harness_version)
            runtime = compiled_harness.runtime
            graph = compiled_harness.graph
        else:
            if deployed.id != harness_version.id:
                raise ValueError(f"deployed harness {deployed.id} does not match {harness_version.id}")
            if not deployed.runtime.activated:
                raise ValueError(f"harness {deployed.id} is not activated")
            harness_version = deployed.version
            runtime = deployed.runtime
            graph = deployed.graph
        runtime_context = runtime.prepare_context(injected_scenario, injected_content)
        context = self.harness_compiler.to_compiled_context(runtime_context)
        sandbox = SandboxState()
        turn = await self.agent.propose(
            AgentRequest(
                episode_id=episode_id,
                scenario=injected_scenario,
                attack=attack,
                context=context,
            )
        )
        await self._emit(
            event_sink,
            "battle_started",
            run_id,
            generation,
            {
                "episode_id": episode_id,
                "attack_id": attack_id,
                "defense_id": defense.id,
                "harness_id": harness_version.id,
                "harness_status": harness_version.status,
                "harness_graph": graph.model_dump(mode="json"),
                "scenario_id": scenario.id,
                "attack_strategy": attack.strategy if attack is not None else "benign_regression",
                "target_tool": attack.target_tool if attack is not None else "",
            },
        )

        executed: list[ExecutedToolCall] = []
        decisions = []
        runtime_trace = []
        for proposal in turn.tool_calls:
            await self._emit(
                event_sink,
                "tool_proposed",
                run_id,
                generation,
                {
                    "episode_id": episode_id,
                    "call": proposal.model_dump(mode="json"),
                },
            )
            runtime_result = await runtime.execute(
                proposal,
                injected_scenario.trusted_goal,
                runtime_context,
            )
            decision = runtime_result.decision
            decisions.append(decision)
            runtime_trace.extend(runtime_result.trace)
            event_type: ArenaEventType
            if decision.decision == "allow":
                result = await sandbox.execute(proposal.name, proposal.arguments)
                executed.append(
                    ExecutedToolCall(
                        call_id=proposal.call_id,
                        name=proposal.name,
                        arguments=proposal.arguments,
                        instruction_source=proposal.instruction_source,
                        result=result,
                    )
                )
                event_type = "tool_allowed"
            else:
                event_type = "tool_blocked"
            await self._emit(
                event_sink,
                event_type,
                run_id,
                generation,
                {
                    "episode_id": episode_id,
                    "tool": proposal.name,
                    "decision": decision.decision,
                    "risk_score": decision.risk_score,
                    "reason_codes": decision.reason_codes,
                    "runtime_trace": [step.model_dump(mode="json") for step in runtime_result.trace],
                },
            )

        evaluation = self.evaluator.evaluate(scenario, executed, turn.final_response)
        episode = Episode(
            id=episode_id,
            run_id=run_id,
            generation=generation,
            attack_id=attack_id,
            defense_id=defense.id,
            harness_id=harness_version.id,
            scenario_id=scenario.id,
            user_prompt=scenario.user_prompt,
            attack_payload=attack_payload,
            proposed_tool_calls=turn.tool_calls,
            gateway_decisions=decisions,
            executed_tool_calls=executed,
            runtime_trace=runtime_trace,
            harness_graph=graph,
            final_response=turn.final_response,
            sandbox_snapshot=sandbox.snapshot(),
            attack_success=evaluation.attack_success,
            legitimate_task_success=evaluation.legitimate_task_success,
            security_score=evaluation.security_score,
            utility_score=evaluation.utility_score,
            latency_ms=max(0, round((time.perf_counter() - started) * 1_000)),
            model_calls=turn.model_calls,
            created_at=datetime.now(UTC),
        )
        await self._emit(
            event_sink,
            "battle_finished",
            run_id,
            generation,
            {"episode": episode.model_dump(mode="json")},
        )
        return episode

    @staticmethod
    async def _emit(
        sink: EventSink | None,
        event_type: ArenaEventType,
        run_id: str,
        generation: int,
        payload: dict[str, object],
    ) -> None:
        if sink is None:
            return
        await sink(
            ArenaEvent(
                type=event_type,
                run_id=run_id,
                generation=generation,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )
