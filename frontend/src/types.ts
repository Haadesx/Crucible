export type Json = string | number | boolean | null | Json[] | { [key: string]: Json }

export type ToolName = 'send_email' | 'transfer_money' | 'delete_document'
export type Decision = 'allow' | 'deny' | 'require_approval'
export type Winner = 'red' | 'blue' | 'catastrophic_blue' | 'over_defensive_blue'
export type HarnessStatus = 'CANDIDATE' | 'COMPILED' | 'EVALUATING' | 'ACTIVE' | 'ELITE' | 'REJECTED' | 'ANCESTOR'
export type GraphNodeKind = 'input' | 'context' | 'agent' | 'policy' | 'tool' | 'memory' | 'verifier'
export type TraceStatus = 'PASS' | 'FAIL' | 'BLOCKED' | 'SKIPPED' | 'EXECUTED' | 'PENDING'

export interface AttackGenome {
  id: string
  generation: number
  parent_ids: string[]
  carrier: string
  strategy: string
  target_tool: ToolName
  placement: string
  indirection_level: number
  obfuscation_level: number
  social_authority: number
  persistence: boolean
  mutation_reason: string
  payload: string | null
}

export interface DefenseGenome {
  id: string
  generation: number
  parent_ids: string[]
  trust_external_content: boolean
  trust_tool_outputs: boolean
  goal_binding_enabled: boolean
  input_classifier_enabled: boolean
  input_classifier_threshold: number
  tool_firewall_enabled: boolean
  tool_risk_threshold: number
  recipient_validation: boolean
  amount_validation: boolean
  resource_validation: boolean
  require_approval_email: boolean
  require_approval_transfer: boolean
  require_approval_delete: boolean
  secondary_verifier_enabled: boolean
  memory_filter_enabled: boolean
  system_policy_variant: string
  mutation_reason: string
}

export interface AttackRecord {
  genome: AttackGenome
  stats: { fitness: number; success_rate: number; novelty: number; battles: number }
  embedding: number[]
  created_at: string
}

export interface DefenseRecord {
  genome: DefenseGenome
  stats: { fitness: number; block_rate: number; utility_rate: number; battles: number }
  created_at: string
}

export interface ContextPolicy {
  isolation_mode: 'FLAT' | 'SEGMENTED' | 'STRICT'
  segment_external: boolean
  system_instruction_variant: string
}

export interface TrustPolicy {
  enabled: boolean
  external_content_trusted: boolean
  tool_outputs_trusted: boolean
  untrusted_risk_multiplier: number
  provenance_required: boolean
}

export interface MemoryPolicy {
  filter_mode: 'OFF' | 'TRUSTED_ONLY' | 'SIMILARITY_TRUSTED'
  trust_threshold: number
  retrieve_failure_memories: boolean
  retrieve_successful_defenses: boolean
}

export interface ToolPolicy {
  gateway_enabled: boolean
  goal_binding_enabled: boolean
  risk_threshold: number
  permissions: Record<string, 'AUTO' | 'GOAL_BOUND' | 'REQUIRE_APPROVAL' | 'DENY'>
}

export interface ValidationPolicy {
  input_classifier_enabled: boolean
  input_classifier_threshold: number
  recipient_validation: boolean
  amount_validation: boolean
  resource_validation: boolean
}

export interface ApprovalPolicy {
  email: boolean
  transfer: boolean
  delete: boolean
}

export interface VerifierPolicy {
  enabled: boolean
  verifier_model: string
  trigger_threshold: number
}

export interface HarnessVersion {
  id: string
  generation: number
  parent_id: string | null
  parent_ids: string[]
  context_policy: ContextPolicy
  trust_policy: TrustPolicy
  memory_policy: MemoryPolicy
  tool_policy: ToolPolicy
  validation_policy: ValidationPolicy
  approval_policy: ApprovalPolicy
  verifier_policy: VerifierPolicy
  system_instruction_policy: { variant: string; max_policy_chars: number }
  mutation_reason: string
  mutation_set: Array<Record<string, string | number | boolean>>
  mutation_evidence: string[]
  expected_effect: string
  historical_matches: string[]
  fitness: number | null
  attack_coverage: number
  utility_score: number
  status: HarnessStatus
  runtime_graph: HarnessGraph
  run_id: string | null
  created_at: string
  compiled_at: string | null
  activated_at: string | null
  promoted_at: string | null
  metrics: Record<string, number>
}

export interface HarnessGraphNode {
  id: string
  label: string
  kind: GraphNodeKind
  enabled: boolean
  config: Record<string, Json>
}

export interface HarnessGraphEdge {
  source: string
  target: string
  condition: string | null
}

export interface HarnessGraph {
  nodes: HarnessGraphNode[]
  edges: HarnessGraphEdge[]
}

export interface HarnessDeployment {
  id: string
  version_id: string
  status: 'REGISTERED' | 'COMPILED' | 'ACTIVE' | 'REJECTED' | 'PROMOTED'
  compiled_at: string | null
  activated_at: string | null
  promoted_at: string | null
  reason: string
}

export interface HarnessMetrics {
  fitness: number
  block_rate: number
  utility_rate: number
  attack_coverage: number
  battles: number
  candidate_status: HarnessStatus
}

export interface HarnessRecord {
  version: HarnessVersion
  deployment: HarnessDeployment
  metrics: HarnessMetrics
  created_at: string
}

export interface HarnessDiffChange {
  path: string
  before: Json
  after: Json
  kind: 'added' | 'removed' | 'changed'
}

export interface HarnessDiff {
  from_version: string
  to_version: string
  changes: HarnessDiffChange[]
  added_nodes: string[]
  removed_nodes: string[]
  summary: string
  created_at: string
}

export interface ProposedToolCall {
  call_id: string
  name: ToolName
  arguments: Record<string, Json>
  instruction_source: string
}

export interface GatewayDecision {
  decision: Decision
  risk_score: number
  reason_codes: string[]
}

export interface ExecutedToolCall extends ProposedToolCall {
  result: { success: boolean; output: Record<string, Json>; error: string | null }
}

export interface RuntimeTraceStep {
  stage: string
  status: TraceStatus
  details: Record<string, Json>
}

export interface Episode {
  id: string
  run_id: string
  generation: number
  attack_id: string
  defense_id: string
  harness_id: string | null
  scenario_id: string
  user_prompt: string
  attack_payload: string
  proposed_tool_calls: ProposedToolCall[]
  gateway_decisions: GatewayDecision[]
  executed_tool_calls: ExecutedToolCall[]
  runtime_trace: RuntimeTraceStep[]
  harness_graph: HarnessGraph
  final_response: string
  sandbox_snapshot: Record<string, Json>
  attack_success: boolean
  legitimate_task_success: boolean
  security_score: number
  utility_score: number
  latency_ms: number
  model_calls: number
  created_at: string
}

export interface Generation {
  id: number
  run_id: string
  red_population: AttackGenome[]
  blue_population: DefenseGenome[]
  red_champion: string
  red_agent_champion: string
  red_fitness_by_version: Record<string, number>
  blue_champion: string
  active_harness_id: string | null
  harness_status: string
  attack_success_rate: number
  utility_rate: number
  red_mean_fitness: number
  blue_mean_fitness: number
  total_battles: number
  created_at: string
}

export interface LineageResponse {
  run_id: string | null
  red: AttackRecord[]
  blue: DefenseRecord[]
}

export interface RunStatus {
  run_id: string | null
  status: string
  generation: number
  total_generations: number
  red_population: number
  blue_population: number
  completed_battles: number
  latest_event: string | null
  error: string | null
}

export interface FailureAnalysis {
  episode_id: string
  harness_id: string
  root_stage: string
  weakness: string
  observed_effect: string
  candidate_changes: string[]
  historical_match_ids: string[]
  historical_similarity: number
  historical_adaptations: string[]
  evidence: string[]
  created_at: string
}

export interface FailureMemory {
  id: string
  run_id: string
  episode_id: string
  type: 'breach' | 'utility_failure'
  summary: string
  attack_id: string
  defense_id: string
  analysis: FailureAnalysis | null
  historical_match_ids: string[]
  similarity: number
  created_at: string
}

export type ArenaEventType =
  | 'generation_started'
  | 'battle_started'
  | 'tool_proposed'
  | 'tool_blocked'
  | 'tool_allowed'
  | 'battle_finished'
  | 'mutation_created'
  | 'generation_finished'
  | 'run_finished'
  | 'harness_compiled'
  | 'harness_activated'
  | 'harness_deployed'
  | 'harness_evaluated'
  | 'harness_promoted'
  | 'harness_rejected'
  | 'failure_analysis'
  | 'harness_diff'
  | 'memory_retrieved'
  | 'attack_candidates_generated'
  | 'red_agent_evolved'
  | 'red_candidate_promoted'
  | 'red_candidate_rejected'
  | 'harness_patch_proposed'
  | 'harness_patch_unusable'
  | 'candidate_compiled'
  | 'candidate_rejected'
  | 'regression_completed'
  | 'champion_comparison'
  | 'run_report'

export interface ArenaEvent {
  type: ArenaEventType
  run_id: string
  generation: number
  payload: Record<string, Json>
  created_at: string
}

// Frozen contract for the `memory_retrieved` event: Atlas Vector Search recall that fed
// the Blue engineer. Every field is optional in storage; the UI renders only what is present.
export interface RetrievedMemory {
  memory_id: string
  similarity: number
  run_id: string
  generation: number
  attack_family: string
  patch_id: string
  outcome: string
}

export interface MemoryRetrievedPayload {
  count: number
  backend: string
  memories: RetrievedMemory[]
}

export interface HarnessComparisonSide {
  harness: HarnessVersion
  episode: Episode
}

export interface HarnessComparisonResponse {
  run_id: string
  same_attack: boolean
  different_outcome: boolean
  harness_a: HarnessComparisonSide
  harness_b: HarnessComparisonSide
}

export type ReplayResponse = Episode

export interface SystemStatus {
  run_mode: 'REAL' | 'DEV' | 'TEST'
  read_only: boolean
  persistence: {
    backend: string
    mongodb_connected: boolean
    atlas_connected: boolean
    database: string
    label: string
  }
  vector_search: {
    configured: string
    observed: string
  }
  latest_run_id: string | null
}

export interface RunSummary {
  run_id: string
  generations: number
  episodes: number
  model_calls: number
  patches: number
  has_report: boolean
  last_activity: string | null
}

/* ---------------------------------------------------------- version matrix */
/* Frozen contract of GET /runs/{run_id}/matrix (Worker A's endpoint). */

export type MatrixCellOutcome = 'BREACH' | 'BLOCKED' | 'BENIGN_PASS' | 'FALSE_POSITIVE' | 'TASK_FAILED'

export interface MatrixVersion {
  label: string
  harness_id: string
  parent_id: string | null
  generation: number
  patch_id: string | null
  status: 'BASELINE' | 'PROMOTED'
  fitness: number | null
  block_rate: number | null
  utility_rate: number | null
  engineer_model: string | null
}

export interface MatrixRejected {
  harness_id: string
  patch_id: string
  generation: number
  reason: string
  fitness: number | null
  block_rate: number | null
  utility_rate: number | null
}

export interface MatrixTest {
  key: string
  kind: 'adversarial' | 'benign'
  scenario_id: string
  attack_id: string
  label: string
  family: string | null
  slice: 'regression' | 'holdout' | 'benign' | 'current'
}

export interface MatrixCell {
  version: string
  test_key: string
  outcome: MatrixCellOutcome
  episode_id: string
  reason: string
}

export interface MatrixTrendPoint {
  version: string
  asr: number
  benign_success: number
  block_rate: number
  event: 'BASELINE' | 'PROMOTED'
}

export interface RunMatrix {
  run_id: string
  versions: MatrixVersion[]
  rejected: MatrixRejected[]
  tests: MatrixTest[]
  cells: MatrixCell[]
  trend: MatrixTrendPoint[]
  // Persisted memory_retrieved events for this run (Atlas recall provenance).
  memory_events?: ArenaEvent[]
}

export interface ModelCallRecord {
  id: string
  run_id: string
  generation: number
  provider: string
  base_url: string | null
  model: string
  role: 'red_attacker' | 'red_mutator' | 'blue_executor' | 'blue_harness_engineer'
  agent_version_id: string
  artifact_id: string
  artifact_type: string
  input_hash: string
  prompt_chars: number
  output_text: string
  latency_ms: number
  usage: Record<string, number | string>
  retrieval_query: string
  retrieved_ids: string[]
  retrieval_scores: Record<string, number>
  error: string | null
  created_at: string
}

export type CandidateStatus = 'PROPOSED' | 'VALIDATED' | 'COMPILED' | 'DEPLOYED_FOR_EVAL' | 'EVALUATED' | 'PROMOTED' | 'REJECTED'

export type HarnessPatchOp = 'ADD_STAGE' | 'REMOVE_STAGE' | 'MOVE_STAGE' | 'SET_PARAMETER' | 'SET_TOOL_PERMISSION' | 'SET_CONTEXT_POLICY' | 'SET_MEMORY_POLICY' | 'SET_SYSTEM_POLICY'

export interface HarnessOperation {
  op: HarnessPatchOp
  target: string
  value: Json
  reason: string
}

export interface HarnessPatch {
  analysis: string
  operations: HarnessOperation[]
  retrieved_memory_ids: string[]
  expected_effect: string
}

export interface CandidateTransition {
  status: CandidateStatus
  at: string
  detail: string
}

export interface SliceMetrics {
  episodes: number
  security: number
  utility: number
}

export interface PatchMetrics {
  fitness: number
  block_rate: number
  utility_rate: number
  latency_penalty: number
  cost_penalty: number
  battles: number
  slices: Record<string, SliceMetrics>
}

export interface HarnessPatchRecord {
  id: string
  run_id: string
  generation: number
  parent_harness_id: string
  child_harness_id: string | null
  patch: HarnessPatch
  model_call_id: string
  raw_response: string
  repair_call_ids: string[]
  status: CandidateStatus
  transitions: CandidateTransition[]
  valid: boolean
  rejection_reason: string
  metrics: PatchMetrics | null
  created_at: string
}

export interface RedAgentVersion {
  id: string
  run_id: string
  generation: number
  parent_ids: string[]
  base_model: string
  system_strategy: string
  tactic_prior: Record<string, number>
  carrier_prior: Record<string, number>
  mutation_policy: string
  memory_query_policy: string
  exploration_level: number
  created_from_failure_ids: string[]
  fitness: number | null
  model_call_id: string
  status: string
  mutation_note: string
  decision_reason: string
  evaluation_episode_ids: string[]
  created_at: string
}

export interface BlueAgentVersion {
  id: string
  run_id: string
  generation: number
  parent_ids: string[]
  base_model: string
  executor_system_policy: string
  harness_engineer_policy: string
  harness_version_id: string
  memory_policy_id: string
  fitness: number | null
  status: string
  created_at: string
}

export interface AttackCandidate {
  id: string
  run_id: string
  red_agent_version_id: string
  scenario_id: string
  parent_attack_ids: string[]
  attack_family: string
  carrier: string
  target_capability: string
  attack_plan: string
  payload: string
  generated_by_model: string
  generation: number
  model_call_id: string
  novelty_score: number | null
  fitness: number | null
  created_at: string
}

export interface ChampionComparison {
  candidate_id: string
  generation: number
  champion_id: string
  champion_kind: 'current' | 'historical'
  champion_generation: number
  broken: boolean
  hof_fitness: number
}

export interface AntiOverfittingSignal {
  candidate_id: string
  generation: number
  current_champion_id: string
  beat_current_champion: boolean
  sampled_champion_ids: string[]
  broken_champion_ids: string[]
  survived_champion_ids: string[]
  generalizes: boolean
}

export interface RunReport {
  run_id: string
  red_model: string
  blue_model: string
  red_provider: string
  blue_provider: string
  generations: number
  red_versions_created: number
  blue_versions_created: number
  attacks_generated: number
  attacks_successful: number
  harness_patches_generated: number
  candidates_compiled: number
  candidates_promoted: number
  asr_by_generation: number[]
  utility_by_generation: number[]
  red_hall_of_fame: string[]
  blue_hall_of_fame: string[]
  final_red_champion: string
  final_blue_champion: string
  total_model_calls: number
  red_team_mode: string
  run_seed: number
  historical_champions_sampled: string[]
  champion_comparisons: ChampionComparison[]
  anti_overfitting: AntiOverfittingSignal[]
  created_at: string
}

export function isEpisode(value: unknown): value is Episode {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return typeof record.id === 'string' && typeof record.attack_id === 'string' && Array.isArray(record.proposed_tool_calls)
}
