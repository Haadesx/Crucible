import type {
  ArenaEvent,
  AttackCandidate,
  BlueAgentVersion,
  Episode,
  FailureMemory,
  Generation,
  HarnessPatchRecord,
  HarnessRecord,
  ModelCallRecord,
  RedAgentVersion,
  RunReport,
  RunSummary,
} from '../types'

/** Everything the observer knows about one run, loaded from the real API. */
export interface RunBundle {
  report: RunReport | null
  generations: Generation[]
  harnesses: HarnessRecord[]
  activeHarness: HarnessRecord | null
  redVersions: RedAgentVersion[]
  blueVersions: BlueAgentVersion[]
  candidates: AttackCandidate[]
  patches: HarnessPatchRecord[]
  episodes: Episode[]
  modelCalls: ModelCallRecord[]
  failures: FailureMemory[]
}

export function emptyBundle(): RunBundle {
  return {
    report: null,
    generations: [],
    harnesses: [],
    activeHarness: null,
    redVersions: [],
    blueVersions: [],
    candidates: [],
    patches: [],
    episodes: [],
    modelCalls: [],
    failures: [],
  }
}

export type WindowKind =
  | 'red'
  | 'red-evolution'
  | 'red-mutation'
  | 'attack'
  | 'sandbox'
  | 'evaluator'
  | 'memory'
  | 'blue'
  | 'patch'
  | 'candidate'
  | 'judge'
  | 'champion'
  | 'events'
  | 'report'
  | 'generation'
  | 'run'

export type NodeTone = 'red' | 'blue' | 'green' | 'amber' | 'cyan' | 'violet' | 'gold' | 'slate'

export type NodeState = 'idle' | 'running' | 'waiting' | 'success' | 'failed' | 'blocked'

export interface NodeRef {
  kind: WindowKind
  id: string
  generation?: number
}

/** One floating workspace window. Content is derived from the bundle by ref. */
export interface WindowSpec {
  id: string
  kind: WindowKind
  title: string
  subtitle: string
  state: NodeState
  tone: NodeTone
  generation: number
  ref: NodeRef
  x: number
  y: number
  w: number
  h: number
  badges: string[]
}

export interface EdgeSpec {
  id: string
  source: string
  target: string
  label: string
  tone: NodeTone
  state: NodeState
  sourceHandle?: string
  targetHandle?: string
}

export interface WorkspaceGraph {
  windows: WindowSpec[]
  edges: EdgeSpec[]
}

export function attackCandidateId(attackId: string): string {
  return attackId.startsWith('GN-') ? attackId.slice(3) : attackId
}

export function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

export function fixed(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

/**
 * Operational liveness of a persisted run summary. This is not an evolution claim:
 * COMPLETE means the engine's final report exists; RUNNING means no report yet but the
 * run wrote something recently; INCOMPLETE means no report and nothing recent (a run
 * that died or stalled must never read as RUNNING forever).
 */
export type RunState = 'COMPLETE' | 'RUNNING' | 'INCOMPLETE'

const RUNNING_WINDOW_MS = 120_000

// Mongo timestamps arrive without a timezone suffix; they are UTC.
function parseUtcMillis(value: string | null): number | null {
  if (!value) return null
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const parsed = Date.parse(normalized)
  return Number.isNaN(parsed) ? null : parsed
}

export function runStateOf(summary: RunSummary | null | undefined): RunState | null {
  if (!summary) return null
  if (summary.has_report) return 'COMPLETE'
  const lastActivity = parseUtcMillis(summary.last_activity)
  if (lastActivity === null) return 'INCOMPLETE'
  return Date.now() - lastActivity <= RUNNING_WINDOW_MS ? 'RUNNING' : 'INCOMPLETE'
}

export function lastActivityAge(value: string | null): string | null {
  const lastActivity = parseUtcMillis(value)
  if (lastActivity === null) return null
  const seconds = Math.max(0, Math.round((Date.now() - lastActivity) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export function championOf(bundle: RunBundle): HarnessRecord | null {
  if (bundle.activeHarness) return bundle.activeHarness
  const promoted = bundle.harnesses
    .filter((record) => record.version.promoted_at)
    .sort((a, b) => (a.version.promoted_at ?? '').localeCompare(b.version.promoted_at ?? ''))
  if (promoted.length > 0) return promoted[promoted.length - 1]
  const finalId = bundle.report?.final_blue_champion
  if (finalId) return bundle.harnesses.find((record) => record.version.id === finalId) ?? null
  return null
}

/** The harness defending during a generation (i.e. the champion promoted before it). */
export function championForGeneration(bundle: RunBundle, generation: number): HarnessRecord | null {
  const byGeneration = bundle.harnesses
    .filter((record) => record.version.generation <= generation)
    .sort((a, b) => b.version.generation - a.version.generation)
  const exact = byGeneration.find((record) => record.version.generation === generation)
  if (exact && exact.version.promoted_at) return exact
  const promoted = byGeneration.find((record) => record.version.promoted_at !== null)
  if (promoted) return promoted
  return byGeneration[byGeneration.length - 1] ?? null
}

export interface ReportCheckpoint {
  checkpoint: boolean
  exportedGenerations: number
  persistedGenerations: number
  persistedCalls: number
  persistedAttacks: number
  promotedPatches: number
}

/** A persisted RunReport may be an export checkpoint written before the run ended. */
export function reportCheckpoint(bundle: RunBundle): ReportCheckpoint {
  const exportedGenerations = bundle.report?.asr_by_generation.length ?? 0
  const persistedGenerations = bundle.generations.length
  const persistedCalls = bundle.modelCalls.length
  const persistedAttacks = bundle.candidates.length
  const promotedPatches = bundle.patches.filter((patch) => patch.status === 'PROMOTED').length
  const checkpoint =
    bundle.report !== null &&
    (exportedGenerations < persistedGenerations || bundle.report.total_model_calls < persistedCalls)
  return { checkpoint, exportedGenerations, persistedGenerations, persistedCalls, persistedAttacks, promotedPatches }
}

export function lineageSummary(bundle: RunBundle, generation: number): string {
  const asr = bundle.generations.find((item) => item.id === generation)?.attack_success_rate
  const promoted = bundle.patches.find((patch) => patch.generation === generation + 1 && patch.status === 'PROMOTED')
  if (promoted?.child_harness_id) return `${pct(asr)} breach → ${promoted.child_harness_id.split('-').pop()} promoted`
  if (asr !== undefined && asr > 0) return 'breach · no promotion'
  if (asr !== undefined) return 'held'
  return 'no record'
}

function episodesForCandidate(bundle: RunBundle, candidateId: string): Episode[] {
  return bundle.episodes
    .filter((episode) => attackCandidateId(episode.attack_id) === candidateId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
}

function averageLatency(bundle: RunBundle, role: ModelCallRecord['role'], generation?: number): number | null {
  const calls = bundle.modelCalls.filter(
    (call) => call.role === role && call.error === null && (generation === undefined || call.generation === generation),
  )
  if (calls.length === 0) return null
  return Math.round(calls.reduce((sum, call) => sum + call.latency_ms, 0) / calls.length)
}

/* -------------------------------------------------------------------------- */
/* Workspace: every generation lives in its own region of one large canvas.    */
/* -------------------------------------------------------------------------- */

const SIZE = {
  red: { w: 380, h: 210 },
  'red-evolution': { w: 360, h: 230 },
  'red-mutation': { w: 310, h: 180 },
  attack: { w: 336, h: 226 },
  sandbox: { w: 336, h: 206 },
  evaluator: { w: 336, h: 214 },
  memory: { w: 380, h: 224 },
  blue: { w: 380, h: 212 },
  patch: { w: 340, h: 238 },
  candidate: { w: 340, h: 238 },
  judge: { w: 340, h: 238 },
  champion: { w: 410, h: 236 },
  events: { w: 440, h: 350 },
  report: { w: 440, h: 336 },
  generation: { w: 1080, h: 58 },
  run: { w: 430, h: 300 },
} as const

const COLUMN_SPAN = 1820
const ROW = {
  generation: -230,
  red: 0,
  attack: 340,
  sandbox: 670,
  evaluator: 980,
  blue: 1360,
  patch: 1730,
  candidate: 1730,
  judge: 1730,
  champion: 0,
}

function generationCenter(generation: number): number {
  return generation * COLUMN_SPAN
}

export function generationNodeId(generation: number): string {
  return `gen-${generation}`
}

export function bundleRunId(bundle: RunBundle): string | null {
  return bundle.report?.run_id ?? bundle.generations[0]?.run_id ?? bundle.patches[0]?.run_id ?? null
}

export interface MemoryRecallEntry {
  memoryId: string
  similarity: number | null
  runId: string | null
  generation: number | null
  attackFamily: string | null
  patchId: string | null
  outcome: string | null
  origin: 'live' | 'patch'
}

export interface MemoryRecall {
  entries: MemoryRecallEntry[]
  backend: string | null
  count: number
  origin: 'live' | 'patch' | 'none'
}

function memoryEntry(raw: unknown, origin: 'live' | 'patch'): MemoryRecallEntry | null {
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>
  if (typeof record.memory_id !== 'string' || record.memory_id.length === 0) return null
  return {
    memoryId: record.memory_id,
    similarity: typeof record.similarity === 'number' ? record.similarity : null,
    runId: typeof record.run_id === 'string' ? record.run_id : null,
    generation: typeof record.generation === 'number' ? record.generation : null,
    attackFamily: typeof record.attack_family === 'string' ? record.attack_family : null,
    patchId: typeof record.patch_id === 'string' ? record.patch_id : null,
    outcome: typeof record.outcome === 'string' ? record.outcome : null,
    origin,
  }
}

/**
 * The Atlas recall that answered generation ``generation``'s breach.
 *
 * Live ``memory_retrieved`` events carry the engineering generation (breach + 1), the same
 * convention as ``harness_patch_proposed``; events emitted at the breach generation are
 * accepted as a fallback so either emitter ordering still lands in one place. When no live
 * event exists for the window, the persisted patch provenance (ids only) is shown, and an
 * empty patch plus an empty event list is reported as "no recall", never invented.
 */
export function memoryRecall(bundle: RunBundle, events: ArenaEvent[], generation: number): MemoryRecall {
  const runId = bundleRunId(bundle)
  const recallEvents = events.filter(
    (event) => event.type === 'memory_retrieved' && (runId === null || event.run_id === runId),
  )
  const engineering = recallEvents.filter((event) => event.generation === generation + 1)
  const chosen = engineering.length > 0 ? engineering : recallEvents.filter((event) => event.generation === generation)
  if (chosen.length > 0) {
    const entries: MemoryRecallEntry[] = []
    let backend: string | null = null
    let count = 0
    for (const event of chosen) {
      const payload = event.payload as { count?: unknown; backend?: unknown; memories?: unknown }
      if (typeof payload.backend === 'string') backend = payload.backend
      const memories = Array.isArray(payload.memories) ? payload.memories : []
      for (const memory of memories) {
        const entry = memoryEntry(memory, 'live')
        if (entry) entries.push(entry)
      }
      count += typeof payload.count === 'number' ? payload.count : memories.length
    }
    return { entries, backend, count: count || entries.length, origin: 'live' }
  }

  const patchIds = [
    ...new Set(
      bundle.patches
        .filter((patch) => patch.generation === generation + 1)
        .flatMap((patch) => patch.patch.retrieved_memory_ids),
    ),
  ]
  if (patchIds.length > 0) {
    return {
      entries: patchIds.map((memoryId) => ({
        memoryId,
        similarity: null,
        runId: null,
        generation: null,
        attackFamily: null,
        patchId: null,
        outcome: null,
        origin: 'patch' as const,
      })),
      backend: null,
      count: patchIds.length,
      origin: 'patch',
    }
  }
  return { entries: [], backend: null, count: 0, origin: 'none' }
}

export function buildWorkspaceGraph(bundle: RunBundle, events: ArenaEvent[] = []): WorkspaceGraph {
  const windows: WindowSpec[] = []
  const edges: EdgeSpec[] = []
  const sortedGenerations = [...bundle.generations].sort((a, b) => a.id - b.id)
  const reportState = reportCheckpoint(bundle)

  const eventWindowId = 'events'
  windows.push({
    id: eventWindowId,
    kind: 'events',
    title: 'EVENT LOG',
    subtitle: 'live + persisted run events',
    state: 'idle',
    tone: 'slate',
    generation: sortedGenerations[sortedGenerations.length - 1]?.id ?? 0,
    ref: { kind: 'events', id: eventWindowId },
    x: generationCenter(1) - SIZE.events.w / 2,
    y: -760,
    w: SIZE.events.w,
    h: SIZE.events.h,
    badges: [],
  })

  windows.push({
    id: 'report',
    kind: 'report',
    title: 'RUN REPORT',
    subtitle: bundle.report?.run_id ?? 'no report persisted',
    state: bundle.report ? 'success' : 'waiting',
    tone: 'slate',
    generation: sortedGenerations[sortedGenerations.length - 1]?.id ?? 0,
    ref: { kind: 'report', id: 'report' },
    x: generationCenter(0) - SIZE.report.w / 2,
    y: -760,
    w: SIZE.report.w,
    h: SIZE.report.h,
    badges: bundle.report
      ? [`${bundle.report.total_model_calls} calls${reportState.checkpoint ? ' · export checkpoint' : ''}`]
      : [],
  })

  sortedGenerations.forEach((generation) => {
    const g = generation.id
    const centerX = generationCenter(g)
    const candidates = bundle.candidates
      .filter((candidate) => candidate.generation === g)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
    const patches = bundle.patches
      .filter((patch) => patch.generation === g + 1)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
    const redVersions = bundle.redVersions.filter((version) => version.generation === g)
    const blueVersions = bundle.blueVersions.filter((version) => version.generation === g + 1)
    const champion = championForGeneration(bundle, g + 1) ?? championOf(bundle)

    windows.push({
      id: generationNodeId(g),
      kind: 'generation',
      title: `GENERATION ${String(g).padStart(2, '0')}`,
      subtitle: lineageSummary(bundle, g),
      state: 'idle',
      tone: generation.attack_success_rate > 0 ? 'red' : 'green',
      generation: g,
      ref: { kind: 'generation', id: generationNodeId(g), generation: g },
      x: centerX - SIZE.generation.w / 2,
      y: ROW.generation,
      w: SIZE.generation.w,
      h: SIZE.generation.h,
      badges: [
        `ASR ${pct(generation.attack_success_rate)}`,
        `utility ${pct(generation.utility_rate)}`,
        `${candidates.length} attacks`,
        `${generation.total_battles} battles`,
      ],
    })

    const redId = `red:${g}`
    const redModel = redVersions[0]?.base_model ?? bundle.modelCalls.find((call) => call.role === 'red_attacker')?.model ?? bundle.report?.red_model ?? 'unknown model'
    const redProvider = bundle.modelCalls.find((call) => call.role === 'red_attacker')?.provider ?? bundle.report?.red_provider ?? 'unknown'
    const redLatency = averageLatency(bundle, 'red_attacker', g)
    const redErrors = bundle.modelCalls.filter((call) => call.role.startsWith('red') && call.error !== null && call.generation === g).length
    windows.push({
      id: redId,
      kind: 'red',
      title: 'RED AGENT',
      subtitle: `${redProvider} · ${redModel}`,
      state: candidates.length > 0 ? 'success' : 'running',
      tone: 'red',
      generation: g,
      ref: { kind: 'red', id: redId, generation: g },
      x: centerX - SIZE.red.w / 2,
      y: ROW.red,
      w: SIZE.red.w,
      h: SIZE.red.h,
      badges: redErrors > 0 ? [`${redErrors} call errors`] : [],
    })

    // Red's own evolution window: the mutations judged at this generation's boundary,
    // each with the measured comparison that promoted or rejected it.
    const mutations = bundle.redVersions
      .filter((version) => version.generation === g + 1)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
    if (mutations.length > 0) {
      const promoted = mutations.filter((version) => version.status === 'PROMOTED').length
      const rejected = mutations.filter((version) => version.status === 'REJECTED').length
      windows.push({
        id: `red-evolution:${g}`,
        kind: 'red-evolution',
        title: 'RED EVOLUTION',
        subtitle: `${mutations.length} mutation${mutations.length === 1 ? '' : 's'} evaluated`,
        state: promoted > 0 ? 'success' : rejected === mutations.length ? 'failed' : 'running',
        tone: 'red',
        generation: g,
        ref: { kind: 'red-evolution', id: `red-evolution:${g}`, generation: g },
        x: centerX - SIZE.red.w / 2 - SIZE['red-evolution'].w - 70,
        y: ROW.red,
        w: SIZE['red-evolution'].w,
        h: SIZE['red-evolution'].h,
        badges: [`${promoted} promoted`, `${rejected} rejected`],
      })
    }

    candidates.forEach((candidate, index) => {
      const spread = (index - (candidates.length - 1) / 2) * (SIZE.attack.w + 34)
      const x = centerX + spread
      const episodes = episodesForCandidate(bundle, candidate.id)
      const breaches = episodes.filter((episode) => episode.attack_success)
      const attackId = `attack:${g}:${candidate.id}`
      const sandboxId = `sandbox:${g}:${candidate.id}`
      const evaluatorId = `evaluator:${g}:${candidate.id}`
      // Small deterministic drift per row keeps the topology legible without the
      // windows snapping into a rigid grid; the flow still reads top to bottom.
      const sandboxX = x + (index % 2 === 0 ? -26 : 30)
      const evaluatorX = x + (index % 2 === 0 ? 34 : -22)

      windows.push({
        id: attackId,
        kind: 'attack',
        title: candidate.attack_family.replaceAll('_', ' '),
        subtitle: `${candidate.carrier} · ${candidate.scenario_id}`,
        state: breaches.length > 0 ? 'failed' : episodes.length > 0 ? 'success' : 'waiting',
        tone: 'red',
        generation: g,
        ref: { kind: 'attack', id: attackId, generation: g },
        x: x - SIZE.attack.w / 2,
        y: ROW.attack,
        w: SIZE.attack.w,
        h: SIZE.attack.h,
        badges: [candidate.id, `novelty ${fixed(candidate.novelty_score)}`],
      })
      windows.push({
        id: sandboxId,
        kind: 'sandbox',
        title: 'SANDBOX',
        subtitle: `${episodes.length} executed episode${episodes.length === 1 ? '' : 's'}`,
        state: sandboxState(episodes),
        tone: 'slate',
        generation: g,
        ref: { kind: 'sandbox', id: sandboxId, generation: g },
        x: sandboxX - SIZE.sandbox.w / 2,
        y: ROW.sandbox,
        w: SIZE.sandbox.w,
        h: SIZE.sandbox.h,
        badges: [],
      })
      windows.push({
        id: evaluatorId,
        kind: 'evaluator',
        title: breaches.length > 0 ? 'EVALUATOR · BREACH' : episodes.length > 0 ? 'EVALUATOR · HELD' : 'EVALUATOR',
        subtitle: breaches.length > 0 ? 'invariant violated' : episodes.length > 0 ? 'attack contained' : 'awaiting execution',
        state: breaches.length > 0 ? 'failed' : episodes.length > 0 ? 'success' : 'waiting',
        tone: breaches.length > 0 ? 'red' : 'green',
        generation: g,
        ref: { kind: 'evaluator', id: evaluatorId, generation: g },
        x: evaluatorX - SIZE.evaluator.w / 2,
        y: ROW.evaluator,
        w: SIZE.evaluator.w,
        h: SIZE.evaluator.h,
        badges: [`ASR ${pct(episodes.length ? breaches.length / episodes.length : null)}`],
      })

      edges.push(
        { id: `e-red-${candidate.id}`, source: redId, target: attackId, label: 'generated', tone: 'red', state: 'success', sourceHandle: 'b', targetHandle: 't' },
        { id: `e-exec-${candidate.id}`, source: attackId, target: sandboxId, label: 'execute', tone: 'slate', state: sandboxState(episodes), sourceHandle: 'b', targetHandle: 't' },
        {
          id: `e-eval-${candidate.id}`,
          source: sandboxId,
          target: evaluatorId,
          label: 'evidence',
          tone: breaches.length > 0 ? 'red' : 'green',
          state: breaches.length > 0 ? 'failed' : 'success',
          sourceHandle: 'b',
          targetHandle: 't',
        },
      )
    })

    const breachCandidate = candidates.find((candidate) =>
      episodesForCandidate(bundle, candidate.id).some((episode) => episode.attack_success),
    )
    const attempts = patches.length
    const repairs = patches.reduce((sum, patch) => sum + patch.repair_call_ids.length, 0)
    const valid = patches.filter((patch) => patch.valid).length
    // The subtitle must name the engineer that authored this generation's patches, not
    // the executor that ran episodes; they are different models (Nemotron vs Ling).
    const engineerCalls = bundle.modelCalls.filter(
      (call) => call.role === 'blue_harness_engineer' && call.generation === g + 1,
    )
    const engineerAuthor = [...engineerCalls].reverse().find((call) => call.error === null)
    const blueModel = engineerAuthor?.model ?? blueVersions[0]?.base_model ?? bundle.report?.blue_model ?? 'unknown model'
    const blueProvider = engineerAuthor?.provider ?? bundle.report?.blue_provider ?? 'unknown'
    const blueId = `blue:${g}`
    windows.push({
      id: blueId,
      kind: 'blue',
      title: 'BLUE ENGINEER',
      subtitle: `${blueProvider} · ${blueModel}`,
      state: breachCandidate ? (patches.length > 0 ? 'success' : 'running') : 'idle',
      tone: 'blue',
      generation: g,
      ref: { kind: 'blue', id: blueId, generation: g },
      x: centerX - SIZE.blue.w / 2,
      y: ROW.blue,
      w: SIZE.blue.w,
      h: SIZE.blue.h,
      badges: [`${attempts} patch attempts`, `${repairs} repairs`, `${valid} valid`],
    })
    // The Atlas recall that fed Blue before it authored this generation's patches. Shown
    // only when there is real recall evidence (live event or persisted patch provenance)
    // or when Blue was actually invoked and the recall came back empty.
    const recall = memoryRecall(bundle, events, g)
    const memoryId = `memory:${g}`
    if (recall.origin !== 'none' || patches.length > 0) {
      windows.push({
        id: memoryId,
        kind: 'memory',
        title: 'ATLAS MEMORY',
        subtitle:
          recall.origin === 'none' || recall.count === 0
            ? 'no relevant prior failures recalled'
            : `${recall.count} recalled${recall.backend ? ` · ${recall.backend}` : ''}`,
        state: recall.entries.length > 0 ? 'success' : 'idle',
        tone: 'cyan',
        generation: g,
        ref: { kind: 'memory', id: memoryId, generation: g },
        x: centerX - 630,
        y: ROW.blue,
        w: SIZE.memory.w,
        h: SIZE.memory.h,
        badges: recall.origin === 'live' ? ['live event'] : recall.origin === 'patch' ? ['patch provenance'] : [],
      })
      if (breachCandidate) {
        edges.push({
          id: `e-recall-${g}`,
          source: `evaluator:${g}:${breachCandidate.id}`,
          target: memoryId,
          label: 'recall',
          tone: 'cyan',
          state: 'success',
          sourceHandle: 'l',
          targetHandle: 't',
        })
      }
      edges.push({
        id: `e-context-${g}`,
        source: memoryId,
        target: blueId,
        label: 'context',
        tone: 'cyan',
        state: 'success',
        sourceHandle: 'r',
        targetHandle: 'l',
      })
    }
    if (breachCandidate) {
      edges.push({
        id: `e-breach-${g}`,
        source: `evaluator:${g}:${breachCandidate.id}`,
        target: blueId,
        label: 'breach',
        tone: 'red',
        state: 'failed',
        sourceHandle: 'b',
        targetHandle: 't',
      })
    }

    const championId = champion ? `champion:${g}` : null
    const championAfterAdaptation = patchRowsY(patches.length)
    patches.forEach((patch, index) => {
      const rowY = ROW.patch + index * 300
      const patchId = `patch:${g}:${patch.id}`
      const candidateId = `candidate:${g}:${patch.id}`
      const judgeId = `judge:${g}:${patch.id}`
      const patchX = centerX - 448
      const candidateX = centerX + 6
      const judgeX = centerX + 448

      windows.push({
        id: patchId,
        kind: 'patch',
        title: 'HARNESS PATCH',
        subtitle: patch.id,
        state: patch.status === 'REJECTED' ? 'failed' : patch.status === 'PROMOTED' ? 'success' : 'running',
        tone: patch.status === 'REJECTED' ? 'amber' : 'violet',
        generation: g,
        ref: { kind: 'patch', id: patchId, generation: g },
        x: patchX - SIZE.patch.w / 2,
        y: rowY,
        w: SIZE.patch.w,
        h: SIZE.patch.h,
        badges: [patch.status, patch.metrics ? `fitness ${fixed(patch.metrics.fitness)}` : 'validating'],
      })

      const harness = patch.child_harness_id ? bundle.harnesses.find((record) => record.version.id === patch.child_harness_id) : undefined
      windows.push({
        id: candidateId,
        kind: 'candidate',
        title: patch.child_harness_id ? `CANDIDATE · ${patch.child_harness_id.split('-').pop()}` : 'CANDIDATE',
        subtitle: patch.child_harness_id ?? 'not compiled',
        state: patch.status === 'PROMOTED' ? 'success' : patch.status === 'REJECTED' ? 'failed' : 'running',
        tone: patch.status === 'PROMOTED' ? 'green' : patch.status === 'REJECTED' ? 'slate' : 'cyan',
        generation: g,
        ref: { kind: 'candidate', id: candidateId, generation: g },
        x: candidateX - SIZE.candidate.w / 2,
        y: rowY,
        w: SIZE.candidate.w,
        h: SIZE.candidate.h,
        badges: patch.metrics ? [`${patch.metrics.battles} replays`, harness ? harness.deployment.status : 'compiling'] : [],
      })
      windows.push({
        id: judgeId,
        kind: 'judge',
        title: 'REPLAY / JUDGE',
        subtitle: `${patch.metrics?.battles ?? 0} episode battery`,
        state: patch.status === 'PROMOTED' ? 'success' : patch.status === 'REJECTED' ? 'failed' : 'running',
        tone: patch.status === 'PROMOTED' ? 'green' : patch.status === 'REJECTED' ? 'amber' : 'cyan',
        generation: g,
        ref: { kind: 'judge', id: judgeId, generation: g },
        x: judgeX - SIZE.judge.w / 2,
        y: rowY,
        w: SIZE.judge.w,
        h: SIZE.judge.h,
        badges: [patch.status],
      })

      edges.push(
        { id: `e-blue-${patch.id}`, source: blueId, target: patchId, label: 'proposed', tone: 'blue', state: 'success', sourceHandle: 'b', targetHandle: 't' },
        { id: `e-compile-${patch.id}`, source: patchId, target: candidateId, label: 'compiled', tone: 'violet', state: patch.child_harness_id ? 'success' : 'failed', sourceHandle: 'r', targetHandle: 'l' },
        { id: `e-replay-${patch.id}`, source: candidateId, target: judgeId, label: 'replay', tone: 'cyan', state: patch.status === 'PROMOTED' || patch.status === 'REJECTED' ? 'success' : 'running', sourceHandle: 'r', targetHandle: 'l' },
      )
      if (patch.status === 'PROMOTED' && championId) {
        edges.push({
          id: `e-promote-${patch.id}`,
          source: judgeId,
          target: championId,
          label: 'PROMOTED',
          tone: 'green',
          state: 'success',
          sourceHandle: 'b',
          targetHandle: 't',
        })
      }
    })

    if (champion && championId) {
      const enabledStages = champion.version.runtime_graph.nodes.filter((node) => node.enabled).length
      windows.push({
        id: championId,
        kind: 'champion',
        title: 'CHAMPION',
        subtitle: champion.version.id,
        state: 'success',
        tone: 'gold',
        generation: g,
        ref: { kind: 'champion', id: championId, generation: g },
        x: centerX - SIZE.champion.w / 2,
        y: championAfterAdaptation,
        w: SIZE.champion.w,
        h: SIZE.champion.h,
        badges: [`G${String(champion.version.generation).padStart(2, '0')}`, `block ${pct(champion.metrics.block_rate)}`, `${enabledStages} stages`],
      })
      const nextChampion = sortedGenerations.some((item) => item.id === g + 1)
      if (nextChampion) {
        edges.push({
          id: `e-lineage-${g}`,
          source: championId,
          target: `champion:${g + 1}`,
          label: 'lineage',
          tone: 'gold',
          state: 'success',
          sourceHandle: 'b',
          targetHandle: 't',
        })
      }
    }
  })

  const dedupedEdges = dedupeEdges(edges.filter((edge) => edge.source !== edge.target))
  return { windows: windows, edges: dedupedEdges }
}

function patchRowsY(count: number): number {
  return ROW.patch + count * 300 + 80
}

function sandboxState(episodes: Episode[]): NodeState {
  if (episodes.length === 0) return 'waiting'
  const failed = episodes.some((episode) => episode.runtime_trace.some((step) => step.status === 'FAIL'))
  return failed ? 'failed' : 'success'
}

function dedupeEdges(edges: EdgeSpec[]): EdgeSpec[] {
  const seen = new Set<string>()
  return edges.filter((edge) => (seen.has(edge.id) ? false : (seen.add(edge.id), true)))
}

function shortId(value: string): string {
  if (!value) return ''
  const parts = value.split('-')
  return parts[parts.length - 1] ?? value
}

/* -------------------------------------------------------------------------- */
/* Lineage: champion → patch → candidate, per generation.                      */
/* -------------------------------------------------------------------------- */

const LINEAGE_ROW = 580
const LINEAGE_SIZE = {
  champion: { w: 300, h: 170 },
  patch: { w: 310, h: 180 },
  candidate: { w: 310, h: 180 },
  generation: { w: 900, h: 54 },
}

export function buildLineageGraph(bundle: RunBundle): WorkspaceGraph {
  const windows: WindowSpec[] = []
  const edges: EdgeSpec[] = []
  const sorted = [...bundle.generations].sort((a, b) => a.id - b.id)

  sorted.forEach((generation) => {
    const g = generation.id
    const baseY = g * LINEAGE_ROW
    const champion = championForGeneration(bundle, g)
    const patches = bundle.patches
      .filter((patch) => patch.generation === g + 1)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
    const championId = `lin-champion:${g}`
    const redId = `lin-red:${g}`
    const generationRecord = bundle.generations.find((item) => item.id === g)
    const redChampionId = generationRecord?.red_agent_champion || ''
    const redChampion =
      bundle.redVersions.find((version) => version.id === redChampionId) ??
      bundle.redVersions
        .filter((version) => version.generation === g)
        .sort((a, b) => (b.fitness ?? 0) - (a.fitness ?? 0))[0] ??
      null
    const mutations = bundle.redVersions
      .filter((version) => version.generation === g + 1)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))

    windows.push({
      id: redId,
      kind: 'red',
      title: `RED ${redChampion ? redChampion.id.split('-').pop() : ''}`.trim(),
      subtitle: redChampion ? `fitness ${fixed(redChampion.fitness)}` : 'no Red version recorded',
      state: 'success',
      tone: 'red',
      generation: g,
      ref: { kind: 'red', id: `red:${g}`, generation: g },
      x: -1390,
      y: baseY,
      w: 330,
      h: 190,
      badges: redChampion ? [redChampion.status] : [],
    })

    mutations.forEach((mutation, index) => {
      const mutationId = `lin-red-mutation:${g}:${mutation.id}`
      windows.push({
        id: mutationId,
        kind: 'red-mutation',
        title: `MUTATION ${mutation.id.split('-').pop()}`,
        subtitle: mutation.parent_ids[0] ?? 'no parent',
        state: mutation.status === 'PROMOTED' ? 'success' : mutation.status === 'REJECTED' ? 'failed' : 'running',
        tone: mutation.status === 'PROMOTED' ? 'green' : mutation.status === 'REJECTED' ? 'amber' : 'red',
        generation: g,
        ref: { kind: 'red-mutation', id: mutationId, generation: g },
        x: -960,
        y: baseY + index * 200,
        w: LINEAGE_SIZE.patch.w,
        h: LINEAGE_SIZE.patch.h,
        badges: [mutation.status, `fitness ${fixed(mutation.fitness)}`],
      })
      edges.push({
        id: `le-mutate-${mutation.id}`,
        source: redId,
        target: mutationId,
        label: 'mutated',
        tone: 'red',
        state: 'success',
        sourceHandle: 'r',
        targetHandle: 'l',
      })
      if (mutation.status === 'PROMOTED' && g + 1 < sorted.length) {
        edges.push({
          id: `le-red-promote-${mutation.id}`,
          source: mutationId,
          target: `lin-red:${g + 1}`,
          label: 'promoted',
          tone: 'green',
          state: 'success',
          sourceHandle: 'b',
          targetHandle: 't',
        })
      }
    })

    windows.push({
      id: `lin-gen:${g}`,
      kind: 'generation',
      title: `GENERATION ${String(g).padStart(2, '0')}`,
      subtitle: lineageSummary(bundle, g),
      state: 'idle',
      tone: generation.attack_success_rate > 0 ? 'red' : 'green',
      generation: g,
      ref: { kind: 'generation', id: generationNodeId(g), generation: g },
      x: -450,
      y: baseY - 150,
      w: LINEAGE_SIZE.generation.w,
      h: LINEAGE_SIZE.generation.h,
      badges: [`ASR ${pct(generation.attack_success_rate)}`, `utility ${pct(generation.utility_rate)}`],
    })

    windows.push({
      id: championId,
      kind: 'champion',
      title: 'CHAMPION',
      subtitle: champion?.version.id ?? generation.blue_champion,
      state: 'success',
      tone: 'gold',
      generation: g,
      ref: { kind: 'champion', id: `champion:${g}`, generation: g },
      x: 0,
      y: baseY,
      w: LINEAGE_SIZE.champion.w,
      h: LINEAGE_SIZE.champion.h,
      badges: champion ? [`fitness ${fixed(champion.metrics.fitness)}`] : [],
    })

    patches.forEach((patch, index) => {
      const y = baseY + index * 220
      const patchId = `lin-patch:${g}:${patch.id}`
      const candidateId = `lin-candidate:${g}:${patch.id}`
      windows.push({
        id: patchId,
        kind: 'patch',
        title: `PATCH ${patch.id.split('-').pop()}`,
        subtitle: patch.status === 'PROMOTED' ? 'promoted' : patch.status === 'REJECTED' ? 'rejected' : patch.status,
        state: patch.status === 'REJECTED' ? 'failed' : patch.status === 'PROMOTED' ? 'success' : 'running',
        tone: patch.status === 'REJECTED' ? 'amber' : 'violet',
        generation: g,
        ref: { kind: 'patch', id: `patch:${g}:${patch.id}`, generation: g },
        x: 420,
        y,
        w: LINEAGE_SIZE.patch.w,
        h: LINEAGE_SIZE.patch.h,
        badges: patch.metrics ? [`fit ${fixed(patch.metrics.fitness, 2)}`] : [],
      })
      windows.push({
        id: candidateId,
        kind: 'candidate',
        title: patch.child_harness_id ? `CANDIDATE ${patch.child_harness_id.split('-').pop()}` : 'CANDIDATE',
        subtitle: patch.status,
        state: patch.status === 'PROMOTED' ? 'success' : patch.status === 'REJECTED' ? 'failed' : 'running',
        tone: patch.status === 'PROMOTED' ? 'green' : patch.status === 'REJECTED' ? 'slate' : 'cyan',
        generation: g,
        ref: { kind: 'candidate', id: `candidate:${g}:${patch.id}`, generation: g },
        x: 810,
        y,
        w: LINEAGE_SIZE.candidate.w,
        h: LINEAGE_SIZE.candidate.h,
        badges: patch.metrics ? [`util ${pct(patch.metrics.utility_rate)}`] : [],
      })
      edges.push(
        { id: `le-propose-${patch.id}`, source: championId, target: patchId, label: 'proposed', tone: 'violet', state: 'success', sourceHandle: 'r', targetHandle: 'l' },
        { id: `le-compile-${patch.id}`, source: patchId, target: candidateId, label: 'compiled', tone: 'cyan', state: patch.child_harness_id ? 'success' : 'failed', sourceHandle: 'r', targetHandle: 'l' },
      )
      if (patch.status === 'PROMOTED' && g + 1 < sorted.length) {
        edges.push({
          id: `le-promote-${patch.id}`,
          source: candidateId,
          target: `lin-champion:${g + 1}`,
          label: 'promoted',
          tone: 'green',
          state: 'success',
          sourceHandle: 'b',
          targetHandle: 't',
        })
      }
    })
  })

  return { windows, edges }
}

/* -------------------------------------------------------------------------- */
/* Runs: one window per persisted run.                                         */
/* -------------------------------------------------------------------------- */

export function buildRunsGraph(runs: RunSummary[], selectedRunId: string | null): WorkspaceGraph {
  const windows: WindowSpec[] = runs.map((run, index) => {
    const column = index % 3
    const row = Math.floor(index / 3)
    const state = runStateOf(run)
    return {
      id: `run:${run.run_id}`,
      kind: 'run' as const,
      title: run.run_id,
      subtitle:
        state === 'COMPLETE'
          ? 'run report persisted'
          : state === 'RUNNING'
            ? 'running — no report yet'
            : 'incomplete — no final report',
      state: run.run_id === selectedRunId ? ('success' as const) : ('idle' as const),
      tone: run.run_id === selectedRunId ? ('cyan' as const) : ('slate' as const),
      generation: run.generations,
      ref: { kind: 'run' as const, id: run.run_id },
      x: column * 500,
      y: row * 380,
      w: SIZE.run.w,
      h: SIZE.run.h,
      badges: [`${run.generations} generations`, `${run.episodes} episodes`, `${run.model_calls} calls`],
    }
  })
  return { windows, edges: [] }
}

/* -------------------------------------------------------------------------- */
/* Timeline: real events when live, persisted records otherwise.               */
/* -------------------------------------------------------------------------- */

export interface TimelineItem {
  id: string
  ts: string
  text: string
  detail: string
  tone: NodeTone
  ref: NodeRef | null
}

export function buildTimeline(bundle: RunBundle, events: ArenaEvent[], runId: string | null): TimelineItem[] {
  const live = events.filter((event) => runId === null || event.run_id === runId)
  if (live.length > 0) {
    return live.map((event, index) => liveItem(event, index)).sort((a, b) => a.ts.localeCompare(b.ts))
  }
  return persistedTimeline(bundle)
}

function liveItem(event: ArenaEvent, index: number): TimelineItem {
  const payload = event.payload
  const text = (value: unknown, fallback: string) => (typeof value === 'string' ? value : fallback)
  const breachGeneration = Math.max(0, event.generation - 1)
  let item: Omit<TimelineItem, 'id' | 'ts'>
  switch (event.type) {
    case 'generation_started':
      item = { text: `Generation ${String(event.generation).padStart(2, '0')} started`, detail: '', tone: 'cyan', ref: { kind: 'generation', id: generationNodeId(event.generation), generation: event.generation } }
      break
    case 'attack_candidates_generated':
      item = { text: `Red generated ${String(payload.count ?? '?')} attack candidate(s)`, detail: text(payload.red_agent_version_id, ''), tone: 'red', ref: { kind: 'red', id: `red:${event.generation}`, generation: event.generation } }
      break
    case 'memory_retrieved': {
      const recalled = typeof payload.count === 'number' ? payload.count : 0
      item = {
        text: recalled > 0 ? `ATLAS recalled ${recalled} similar failure(s)` : 'ATLAS memory: no relevant prior failures',
        detail: text(payload.backend, ''),
        tone: 'cyan',
        ref: { kind: 'memory', id: `memory:${breachGeneration}`, generation: breachGeneration },
      }
      break
    }
    case 'harness_patch_proposed':
      item = { text: `HarnessPatch ${text(payload.patch_id, '')} proposed`, detail: text(payload.parent_harness_id, ''), tone: 'violet', ref: { kind: 'patch', id: `patch:${breachGeneration}:${text(payload.patch_id, '')}`, generation: breachGeneration } }
      break
    case 'candidate_compiled':
      item = { text: `Candidate ${text(payload.harness_id, '')} compiled`, detail: text(payload.patch_id, ''), tone: 'cyan', ref: { kind: 'candidate', id: `candidate:${breachGeneration}:${text(payload.patch_id, '')}`, generation: breachGeneration } }
      break
    case 'candidate_rejected':
      item = { text: `Candidate ${text(payload.patch_id, '')} rejected`, detail: text(payload.reason, ''), tone: 'amber', ref: { kind: 'patch', id: `patch:${breachGeneration}:${text(payload.patch_id, '')}`, generation: breachGeneration } }
      break
    case 'regression_completed':
      item = { text: 'Benign regression completed', detail: `${String(payload.benign_pass ?? '?')}/${String(payload.benign_total ?? '?')} pass · ${text(payload.harness_id, '')}`, tone: 'green', ref: { kind: 'champion', id: `champion:${breachGeneration}`, generation: breachGeneration } }
      break
    case 'champion_comparison':
      item = { text: 'Champion comparison replayed', detail: text(payload.candidate_id, ''), tone: 'gold', ref: { kind: 'evaluator', id: `evaluator:${event.generation}:${text(payload.candidate_id, '')}`, generation: event.generation } }
      break
    case 'harness_promoted':
      item = { text: 'Candidate promoted', detail: text(payload.harness_id, ''), tone: 'green', ref: { kind: 'champion', id: `champion:${breachGeneration}`, generation: breachGeneration } }
      break
    case 'red_agent_evolved':
      item = { text: `Red mutation ${shortId(text(payload.child_id, ''))} created`, detail: text(payload.mutation_note, ''), tone: 'red', ref: { kind: 'red-evolution', id: `red-evolution:${event.generation}`, generation: event.generation } }
      break
    case 'red_candidate_promoted':
      item = { text: `Red promoted ${shortId(text(payload.child_id, ''))}`, detail: text(payload.reason, ''), tone: 'green', ref: { kind: 'red-evolution', id: `red-evolution:${event.generation}`, generation: event.generation } }
      break
    case 'red_candidate_rejected':
      item = { text: `Red mutation ${shortId(text(payload.child_id, ''))} rejected`, detail: text(payload.reason, ''), tone: 'amber', ref: { kind: 'red-evolution', id: `red-evolution:${event.generation}`, generation: event.generation } }
      break
    case 'battle_finished':
      item = { text: 'Battle episode finished', detail: text(payload.episode_id, ''), tone: 'slate', ref: null }
      break
    case 'run_report':
      item = { text: 'Run report persisted', detail: text(payload.run_id, ''), tone: 'gold', ref: { kind: 'report', id: 'report' } }
      break
    default:
      item = { text: event.type.replaceAll('_', ' '), detail: '', tone: 'slate', ref: null }
  }
  return { id: `live-${index}`, ts: event.created_at, ...item }
}

function persistedTimeline(bundle: RunBundle): TimelineItem[] {
  const items: TimelineItem[] = []
  bundle.generations
    .slice()
    .sort((a, b) => a.id - b.id)
    .forEach((generation) => {
      items.push({
        id: `gen-${generation.id}`,
        ts: generation.created_at,
        text: `Generation ${String(generation.id).padStart(2, '0')} persisted`,
        detail: `ASR ${pct(generation.attack_success_rate)} · utility ${pct(generation.utility_rate)} · ${generation.total_battles} battles`,
        tone: generation.attack_success_rate > 0 ? 'red' : 'green',
        ref: { kind: 'generation', id: generationNodeId(generation.id), generation: generation.id },
      })
    })
  bundle.candidates.forEach((candidate) => {
    items.push({
      id: `candidate-${candidate.id}`,
      ts: candidate.created_at,
      text: `Red generated ${candidate.id}`,
      detail: `${candidate.attack_family.replaceAll('_', ' ')} · ${candidate.carrier}`,
      tone: 'red',
      ref: { kind: 'attack', id: `attack:${candidate.generation}:${candidate.id}`, generation: candidate.generation },
    })
  })
  bundle.episodes
    .filter((episode) => episode.proposed_tool_calls.length > 0 || episode.attack_success)
    .forEach((episode) => {
      items.push({
        id: `episode-${episode.id}`,
        ts: episode.created_at,
        text: `${episode.id} ${episode.attack_success ? 'BREACH' : 'held'}`,
        detail: `${episode.scenario_id} · ${episode.latency_ms}ms · ${episode.executed_tool_calls.length} tool calls`,
        tone: episode.attack_success ? 'red' : 'green',
        ref: { kind: 'evaluator', id: `evaluator:${episode.generation}:${attackCandidateId(episode.attack_id)}`, generation: episode.generation },
      })
    })
  bundle.redVersions
    .filter((version) => version.status === 'PROMOTED' || version.status === 'REJECTED')
    .forEach((version) => {
      const breachGeneration = Math.max(0, version.generation - 1)
      items.push({
        id: `red-decision-${version.id}`,
        ts: version.created_at,
        text: `Red mutation ${shortId(version.id)} ${version.status.toLowerCase()}`,
        detail: version.decision_reason || version.mutation_note,
        tone: version.status === 'PROMOTED' ? 'green' : 'amber',
        ref: { kind: 'red-evolution', id: `red-evolution:${breachGeneration}`, generation: breachGeneration },
      })
    })
  bundle.patches.forEach((patch) => {
    const breachGeneration = Math.max(0, patch.generation - 1)
    patch.transitions.forEach((transition, index) => {
      items.push({
        id: `patch-${patch.id}-${index}`,
        ts: transition.at,
        text: `${patch.id} ${transition.status.toLowerCase().replaceAll('_', ' ')}`,
        detail: transition.detail,
        tone: transition.status === 'PROMOTED' ? 'green' : transition.status === 'REJECTED' ? 'amber' : 'violet',
        ref: { kind: 'patch', id: `patch:${breachGeneration}:${patch.id}`, generation: breachGeneration },
      })
    })
  })
  if (bundle.report) {
    items.push({
      id: 'report',
      ts: bundle.report.created_at,
      text: 'Run report persisted',
      detail: `${bundle.report.attacks_generated} attacks · ${bundle.report.candidates_promoted} promoted · ${bundle.report.total_model_calls} model calls`,
      tone: 'gold',
      ref: { kind: 'report', id: 'report' },
    })
  }
  return items.sort((a, b) => a.ts.localeCompare(b.ts))
}
