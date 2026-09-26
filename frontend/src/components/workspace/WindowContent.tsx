import type { ArenaEvent, RunSummary } from '../../types'
import type { MemoryRecallEntry, NodeRef, RunBundle, TimelineItem, WindowSpec } from '../../lib/viewmodel'
import type { UiMode } from '../../hooks/useRunData'
import { attackCandidateId, championForGeneration, championOf, fixed, memoryRecall, pct, reportCheckpoint } from '../../lib/viewmodel'

export interface WindowContentProps {
  spec: WindowSpec
  bundle: RunBundle
  events: ArenaEvent[]
  runs: RunSummary[]
  timeline: TimelineItem[]
  mode: UiMode
  onFollow: (ref: NodeRef) => void
}

export function WindowContent({ spec, bundle, events, runs, timeline, mode, onFollow }: WindowContentProps) {
  switch (spec.kind) {
    case 'red':
      return <RedContent bundle={bundle} generation={spec.generation} mode={mode} />
    case 'red-evolution':
      return <RedEvolutionContent bundle={bundle} generation={spec.generation} mode={mode} />
    case 'red-mutation':
      return <RedMutationContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'attack':
      return <AttackContent bundle={bundle} generation={spec.generation} tail={refTail(spec.ref.id)} mode={mode} />
    case 'sandbox':
      return <SandboxContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'evaluator':
      return <EvaluatorContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'memory':
      return <MemoryContent bundle={bundle} generation={spec.generation} events={events} mode={mode} />
    case 'blue':
      return <BlueContent bundle={bundle} generation={spec.generation} mode={mode} />
    case 'patch':
      return <PatchContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'candidate':
      return <CandidateContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'judge':
      return <JudgeContent bundle={bundle} tail={refTail(spec.ref.id)} mode={mode} />
    case 'champion':
      return <ChampionContent bundle={bundle} generation={spec.generation} mode={mode} />
    case 'events':
      return <EventsContent timeline={timeline} onFollow={onFollow} />
    case 'report':
      return <ReportContent bundle={bundle} mode={mode} />
    case 'generation':
      return <GenerationContent bundle={bundle} generation={spec.generation} />
    case 'run':
      return <RunContent runs={runs} runId={spec.ref.id} />
  }
}

function refTail(refId: string): string {
  return refId.split(':').slice(2).join(':')
}

/* ---------------------------------------------------------------- primitives */

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="win-row">
      <span>{label}</span>
      <b className={`mono ${tone ? `text-${tone}` : ''}`} title={value}>{value}</b>
    </div>
  )
}

function Section({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="win-section">
      <div className="win-section-head">
        <span className="eyebrow">{title}</span>
        {action}
      </div>
      {children}
    </div>
  )
}

function Meter({ value, tone = 'cyan' }: { value: number | null | undefined; tone?: string }) {
  return (
    <div className={`meter tone-${tone}`}>
      <i style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="win-empty">{text}</p>
}

function CallLines({ calls, mode }: { calls: RunBundle['modelCalls']; mode: UiMode }) {
  if (calls.length === 0) return <Empty text="no inference calls persisted" />
  return (
    <div className="call-lines">
      {calls.map((call) => (
        <div className={`call-line ${call.error ? 'is-error' : ''}`} key={call.id}>
          <span className={`call-dot ${call.error ? 'is-error' : ''}`} />
          <span className="mono">{call.role.replace('_', ' ')}</span>
          <span className="call-model mono">{call.model.split('/').pop()}</span>
          <span className="mono muted">{call.error ? 'ERROR' : `${(call.latency_ms / 1000).toFixed(1)}s`}</span>
          {mode === 'dev' && <span className="mono muted call-id">{call.id.slice(0, 14)}</span>}
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------- red */

function RedContent({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const versions = bundle.redVersions.filter((version) => version.generation === generation)
  const candidates = bundle.candidates.filter((candidate) => candidate.generation === generation)
  const calls = bundle.modelCalls.filter((call) => call.role.startsWith('red') && call.generation === generation)
  const latest = calls[calls.length - 1]
  const avg = calls.length ? Math.round(calls.reduce((sum, call) => sum + call.latency_ms, 0) / calls.length) : null
  return (
    <>
      <div className="win-statusline">
        {latest?.error ? `provider error on last call` : candidates.length > 0 ? `${candidates.length} attack candidates generated` : 'generating adversarial attacks…'}
      </div>
      {versions.slice(0, 1).map((version) => (
        <div className="win-block" key={version.id}>
          <div className="mono model-line">{version.base_model}</div>
          <div className="mono muted">{version.id} · gen {version.generation}</div>
          <p className="win-prose">{trim(version.system_strategy, 180)}</p>
        </div>
      ))}
      <div className="win-grid2">
        <Row label="candidates" value={String(candidates.length)} />
        <Row label="avg latency" value={avg !== null ? `${(avg / 1000).toFixed(1)}s` : '—'} />
        <Row label="tactic prior" value={versions[0] ? topKey(versions[0].tactic_prior) : '—'} />
        <Row label="exploration" value={versions[0] ? versions[0].exploration_level.toFixed(2) : '—'} />
      </div>
      <Section title={`MODEL CALLS · ${calls.length}`}>
        <CallLines calls={calls.slice(-4)} mode={mode} />
      </Section>
    </>
  )
}

/* ------------------------------------------------------------------ attack */

function AttackContent({ bundle, generation, tail, mode }: { bundle: RunBundle; generation: number; tail: string; mode: UiMode }) {
  const candidate = bundle.candidates.find((item) => item.id === tail)
  if (!candidate) return <Empty text={`attack ${tail} not found`} />
  const episodes = bundle.episodes.filter((item) => attackCandidateId(item.attack_id) === candidate.id)
  const breached = episodes.some((item) => item.attack_success)
  return (
    <>
      <div className={`win-verdict ${breached ? 'is-breach' : episodes.length ? 'is-held' : ''}`}>
        {breached ? 'BREACH' : episodes.length ? 'CONTAINED' : 'PENDING'}
      </div>
      <div className="win-grid2">
        <Row label="family" value={candidate.attack_family.replaceAll('_', ' ')} />
        <Row label="carrier" value={candidate.carrier} />
        <Row label="target" value={`${candidate.target_capability} · ${candidate.scenario_id}`} />
        <Row label="novelty" value={fixed(candidate.novelty_score)} />
      </div>
      <Section title={mode === 'dev' ? 'PAYLOAD' : 'INJECTED CONTENT'}>
        <pre className="win-pre">{trim(candidate.payload, 340)}</pre>
      </Section>
      <div className="win-foot mono muted">
        {candidate.generated_by_model} · gen {generation}
        {mode === 'dev' && ` · ${candidate.model_call_id.slice(0, 18)}`}
      </div>
    </>
  )
}

/* ----------------------------------------------------------------- sandbox */

function SandboxContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const episodes = bundle.episodes
    .filter((item) => attackCandidateId(item.attack_id) === tail)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
  if (episodes.length === 0) return <Empty text="no execution yet" />
  const executed = episodes.reduce((sum, item) => sum + item.executed_tool_calls.length, 0)
  const proposed = episodes.reduce((sum, item) => sum + item.proposed_tool_calls.length, 0)
  const latest = episodes[episodes.length - 1]
  return (
    <>
      <div className="win-grid2">
        <Row label="episodes" value={String(episodes.length)} />
        <Row label="latest" value={`${latest.latency_ms}ms`} />
        <Row label="tool calls" value={`${executed} executed / ${proposed} proposed`} />
        <Row label="model calls" value={String(episodes.reduce((sum, item) => sum + item.model_calls, 0))} />
      </div>
      <Section title="EXECUTION TRACE">
        {latest.runtime_trace.length === 0 ? (
          <Empty text="no stage trace persisted for the latest episode" />
        ) : (
          <div className="trace-lines">
            {latest.runtime_trace.map((step, index) => (
              <div className="trace-line" key={`${step.stage}-${index}`}>
                <span className={`trace-dot status-${step.status.toLowerCase()}`} />
                <span>{step.stage}</span>
                <span className={`mono status-${step.status.toLowerCase()}`}>{step.status}</span>
              </div>
            ))}
          </div>
        )}
      </Section>
      <Section title="LATEST EPISODE">
        <div className="episode-lines">
          {episodes.slice(-3).map((episode) => (
            <div className="episode-line" key={episode.id}>
              <span className={`ep-dot ${episode.attack_success ? 'is-breach' : ''}`} />
              <span className="mono">{episode.id}</span>
              <span className="mono muted">{episode.scenario_id}</span>
              <span className="mono muted">{episode.latency_ms}ms</span>
              {mode === 'dev' && <span className="mono muted">{episode.model_calls} calls</span>}
            </div>
          ))}
        </div>
      </Section>
    </>
  )
}

/* --------------------------------------------------------------- evaluator */

function EvaluatorContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const episodes = bundle.episodes.filter((item) => attackCandidateId(item.attack_id) === tail)
  const breaches = episodes.filter((item) => item.attack_success)
  const failure = breaches[0] ? bundle.failures.find((item) => item.episode_id === breaches[0].id) : undefined
  const asr = episodes.length ? breaches.length / episodes.length : null
  if (episodes.length === 0) return <Empty text="awaiting sandbox evidence" />
  return (
    <>
      <div className={`win-verdict ${breaches.length > 0 ? 'is-breach' : 'is-held'}`}>
        {breaches.length > 0 ? 'BREACH · invariant violated' : 'HELD · attack contained'}
      </div>
      <div className="metric-lines">
        <MetricLine label="attack success rate" value={asr} tone={asr && asr > 0 ? 'red' : 'green'} />
        <MetricLine label="security" value={episodes[0].security_score} tone={breaches.length > 0 ? 'red' : 'green'} />
        <MetricLine label="utility" value={episodes[0].utility_score} tone="cyan" />
      </div>
      <Section title="FAILURE EVIDENCE">
        {failure ? (
          <>
            <p className="win-prose">{failure.summary}</p>
            {failure.analysis?.candidate_changes.length ? (
              <div className="chip-line">
                {failure.analysis.candidate_changes.slice(0, 3).map((change) => (
                  <span className="chip" key={change}>{change}</span>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <Empty text="no failure memory recorded for this attack" />
        )}
      </Section>
      {mode === 'dev' && breaches[0] && <div className="win-foot mono muted">evidence episode {breaches[0].id}</div>}
    </>
  )
}

function MetricLine({ label, value, tone }: { label: string; value: number | null | undefined; tone: string }) {
  return (
    <div className="metric-line">
      <span>{label}</span>
      <Meter value={value} tone={tone} />
      <b className={`mono text-${tone}`}>{pct(value)}</b>
    </div>
  )
}

/* ------------------------------------------------------------------ memory */

function MemoryContent({
  bundle,
  generation,
  events,
  mode,
}: {
  bundle: RunBundle
  generation: number
  events: ArenaEvent[]
  mode: UiMode
}) {
  const recall = memoryRecall(bundle, events, generation)
  const entries = recall.entries
  return (
    <>
      <div className="win-statusline">
        {recall.origin === 'none' || recall.count === 0
          ? 'no relevant prior failures recalled'
          : `${recall.count} similar failure${recall.count === 1 ? '' : 's'} recalled`}
      </div>
      <div className="mono model-line">
        {recall.origin === 'live'
          ? `recall backend · ${recall.backend ?? 'not reported'}`
          : recall.origin === 'patch'
            ? 'persisted patch provenance (ids only)'
            : '—'}
      </div>
      {entries.length > 0 ? (
        <div className="memory-rows">
          {entries.map((entry) => (
            <MemoryRow entry={entry} key={`${entry.origin}-${entry.memoryId}`} mode={mode} />
          ))}
        </div>
      ) : (
        <p className="win-prose muted">No relevant prior failures recalled</p>
      )}
    </>
  )
}

function MemoryRow({ entry, mode }: { entry: MemoryRecallEntry; mode: UiMode }) {
  return (
    <div className="memory-row">
      <div className="memory-row-head">
        <span className="mono memory-id" title={entry.memoryId}>
          {entry.memoryId.length > 26 ? `${entry.memoryId.slice(0, 26)}…` : entry.memoryId}
        </span>
        <span className="mono memory-sim">
          {entry.similarity === null ? 'similarity —' : `sim ${entry.similarity.toFixed(2)}`}
        </span>
      </div>
      <div className="memory-row-meta mono">
        <span>{entry.attackFamily ?? 'family —'}</span>
        <span>
          {entry.runId ? `${entry.runId.slice(0, 18)}…` : 'run —'}
          {entry.generation !== null ? ` · G${String(entry.generation).padStart(2, '0')}` : ''}
        </span>
        <span>{entry.patchId ? `patch ${entry.patchId}` : 'patch —'}</span>
        <span
          className={
            entry.outcome === 'PROMOTED' ? 'text-green' : entry.outcome === 'REJECTED' ? 'text-amber' : ''
          }
        >
          {entry.outcome ?? (mode === 'dev' ? 'outcome unknown' : 'outcome —')}
        </span>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------- blue */

function BlueContent({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const responseGeneration = generation + 1
  const patches = bundle.patches.filter((patch) => patch.generation === responseGeneration)
  const calls = bundle.modelCalls.filter((call) => call.role.startsWith('blue') && call.generation === responseGeneration)
  const engineerCalls = calls.filter((call) => call.role === 'blue_harness_engineer')
  const versions = bundle.blueVersions.filter((version) => version.generation === responseGeneration)
  const breach = bundle.episodes.some((episode) => episode.generation === generation && episode.attack_success)
  const repairs = patches.reduce((sum, patch) => sum + patch.repair_call_ids.length, 0)
  const valid = patches.filter((patch) => patch.valid).length
  const latest = calls[calls.length - 1]
  const engineerModel = [...engineerCalls].reverse().find((call) => call.error === null)?.model ?? '—'
  const executorModel = versions[0]?.base_model ?? calls.find((call) => call.role === 'blue_executor')?.model ?? '—'
  // More than one engineer model in one generation means the primary failed and the
  // configured fallback authored at least one patch; the ledger rows show which.
  const fallbackUsed = new Set(engineerCalls.map((call) => call.model)).size > 1
  return (
    <>
      <div className="win-statusline">
        {patches.length > 0
          ? `authoring ${patches.length} harness patch${patches.length === 1 ? '' : 'es'}`
          : breach
            ? 'invoked — analysing breach evidence'
            : 'standing by — no breach to answer'}
      </div>
      <div className="mono model-line">engineer: {engineerModel}</div>
      <div className="win-grid2">
        <Row label="executor" value={executorModel} />
        <Row label="patches" value={String(patches.length)} />
        <Row label="repairs" value={String(repairs)} />
        <Row label="valid" value={`${valid}/${patches.length}`} />
        <Row label="fallback" value={fallbackUsed ? 'used' : 'not used'} tone={fallbackUsed ? 'amber' : undefined} />
        <Row label="last call" value={latest ? `${latest.error ? 'ERROR' : `${(latest.latency_ms / 1000).toFixed(1)}s`}` : '—'} tone={latest?.error ? 'red' : undefined} />
      </div>
      {fallbackUsed && (
        <div className="chip-line">
          <span className="chip">fallback engaged — see per-patch authoring path</span>
        </div>
      )}
      {patches.length > 0 && (
        <Section title="PATCH ATTEMPTS">
          <div className="patch-lines">
            {patches.map((patch) => (
              <div className="patch-line" key={patch.id}>
                <span className={`patch-dot status-${patch.status.toLowerCase()}`} />
                <span className="mono">{patch.id.split('-').pop()}</span>
                <span className={`mono ${patch.status === 'PROMOTED' ? 'text-green' : patch.status === 'REJECTED' ? 'text-amber' : 'text-violet'}`}>{patch.status}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
      <Section title={`ENGINEER CALLS · ${engineerCalls.length}`}>
        <CallLines calls={engineerCalls.slice(-4)} mode={mode} />
      </Section>
    </>
  )
}

/* ------------------------------------------------------------------- patch */

function PatchContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const patch = bundle.patches.find((item) => item.id === tail)
  if (!patch) return <Empty text={`patch ${tail} not found`} />
  const added = patch.patch.operations.filter((op) => op.op === 'ADD_STAGE')
  const removed = patch.patch.operations.filter((op) => op.op === 'REMOVE_STAGE')
  const other = patch.patch.operations.filter((op) => op.op !== 'ADD_STAGE' && op.op !== 'REMOVE_STAGE')
  const sourceEpisode = bundle.episodes.find((episode) => episode.attack_success && episode.generation === patch.generation - 1)
  const authorCall = bundle.modelCalls.find((call) => call.id === patch.model_call_id)
  return (
    <>
      <div className={`win-verdict ${patch.status === 'PROMOTED' ? 'is-held' : patch.status === 'REJECTED' ? 'is-warn' : ''}`}>
        {patch.status}
      </div>
      <Section title="STRUCTURED DIFF">
        <div className="op-lines">
          {added.map((op) => (
            <div className="op-line" key={`a-${op.target}`}>
              <b className="text-green">+</b>
              <span className="mono">{op.target}</span>
            </div>
          ))}
          {removed.map((op) => (
            <div className="op-line" key={`r-${op.target}`}>
              <b className="text-red">−</b>
              <span className="mono">{op.target}</span>
            </div>
          ))}
          {other.map((op) => (
            <div className="op-line" key={`o-${op.target}`}>
              <b className="text-cyan">~</b>
              <span className="mono">
                {op.target} → {shortValue(op.value)}
              </span>
            </div>
          ))}
        </div>
      </Section>
      <div className="win-grid2">
        <Row label="parent" value={patch.parent_harness_id} />
        <Row label="validation" value={patch.valid ? 'valid' : patch.rejection_reason} tone={patch.valid ? 'green' : 'red'} />
        <Row label="source" value={sourceEpisode?.id ?? 'breach evidence'} />
        <Row label="repairs" value={String(patch.repair_call_ids.length)} />
        <Row label="author" value={authorCall?.model ?? 'not in this snapshot'} />
        {mode === 'dev' && <Row label="model call" value={patch.model_call_id} />}
      </div>
      {mode === 'dev' && <p className="win-prose muted">{trim(patch.patch.analysis, 220)}</p>}
      {mode === 'demo' && <p className="win-prose">{trim(patch.patch.expected_effect || patch.patch.analysis, 220)}</p>}
    </>
  )
}

/* --------------------------------------------------------------- candidate */

function CandidateContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const patch = bundle.patches.find((item) => item.id === tail)
  if (!patch) return <Empty text={`candidate ${tail} not found`} />
  const harness = patch.child_harness_id ? bundle.harnesses.find((record) => record.version.id === patch.child_harness_id) : undefined
  const metrics = patch.metrics
  return (
    <>
      <div className="win-grid2">
        <Row label="harness" value={patch.child_harness_id ?? 'not compiled'} />
        <Row label="parent" value={patch.parent_harness_id} />
        <Row label="compiled" value={harness?.deployment.compiled_at ? 'yes' : 'no'} tone={harness?.deployment.compiled_at ? 'green' : 'amber'} />
        <Row label="lifecycle" value={patch.status} />
      </div>
      <div className="metric-lines">
        <MetricLine label="fitness" value={metrics?.fitness ?? harness?.metrics.fitness} tone="green" />
        <MetricLine label="block rate" value={metrics?.block_rate ?? harness?.metrics.block_rate} tone="cyan" />
        <MetricLine label="utility" value={metrics?.utility_rate ?? harness?.metrics.utility_rate} tone="violet" />
      </div>
      {mode === 'dev' && metrics && Object.keys(metrics.slices).length > 0 && (
        <Section title="TEST BATTERY">
          <div className="table">
            <div className="table-head mono">
              <span>slice</span>
              <span>eps</span>
              <span>security</span>
              <span>utility</span>
            </div>
            {Object.entries(metrics.slices).map(([name, slice]) => (
              <div className="table-row mono" key={name}>
                <span>{name}</span>
                <span>{slice.episodes}</span>
                <span className={slice.security < 1 ? 'text-red' : 'text-green'}>{pct(slice.security)}</span>
                <span className={slice.utility < 0.5 ? 'text-amber' : 'text-green'}>{pct(slice.utility)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
      <div className="win-foot mono muted">{metrics ? `${metrics.battles} replay battles` : 'evaluation pending'}</div>
    </>
  )
}

/* ------------------------------------------------------------------- judge */

function JudgeContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const patch = bundle.patches.find((item) => item.id === tail)
  if (!patch) return <Empty text={`verdict ${tail} not found`} />
  const metrics = patch.metrics
  const signal = bundle.report?.anti_overfitting.find((item) => item.candidate_id.startsWith(patch.id.replace('PATCH-', 'A-')))
  // One battery, two questions: did it stop the attacks, and did the benign tasks survive?
  const maliciousSlices = metrics ? Object.entries(metrics.slices).filter(([name]) => name !== 'benign') : []
  const maliciousEpisodes = maliciousSlices.reduce((sum, [, slice]) => sum + slice.episodes, 0)
  const maliciousBlocked = maliciousSlices.reduce((sum, [, slice]) => sum + slice.episodes * slice.security, 0)
  const benign = metrics?.slices.benign
  const decision = patch.transitions[patch.transitions.length - 1]?.detail || patch.rejection_reason
  return (
    <>
      <div className={`win-verdict judge-decision ${patch.status === 'PROMOTED' ? 'is-held' : patch.status === 'REJECTED' ? 'is-warn' : ''}`}>
        {patch.status === 'PROMOTED' ? 'PROMOTED' : patch.status === 'REJECTED' ? 'REJECTED' : 'REPLAYING'}
      </div>
      <div className="judge-sides">
        <div className="judge-side">
          <span className="side-label">MALICIOUS · SHOULD BLOCK</span>
          <span className="side-value mono text-cyan">
            {maliciousEpisodes > 0
              ? `${Math.round(maliciousBlocked)}/${maliciousEpisodes} blocked · ${pct(maliciousBlocked / maliciousEpisodes)}`
              : 'not in this battery'}
          </span>
        </div>
        <div className="judge-side">
          <span className="side-label">BENIGN · SHOULD WORK</span>
          <span className="side-value mono text-green">
            {benign
              ? `${Math.round(benign.episodes * benign.utility)}/${benign.episodes} passed · ${pct(benign.utility)}`
              : 'not in this battery'}
          </span>
        </div>
      </div>
      <Section title="DECISION REASON">
        <p className="win-prose judge-reason">{decision || 'replay battery still running'}</p>
      </Section>
      {metrics && (
        <div className="win-grid2">
          <Row label="fitness" value={fixed(metrics.fitness)} />
          <Row label="battles" value={String(metrics.battles)} />
          <Row label="block rate" value={pct(metrics.block_rate)} />
          <Row label="utility" value={pct(metrics.utility_rate)} />
          <Row label="latency penalty" value={fixed(metrics.latency_penalty, 2)} />
          <Row label="cost penalty" value={fixed(metrics.cost_penalty, 2)} />
        </div>
      )}
      {mode === 'dev' && signal && (
        <div className="win-foot mono muted">
          {signal.generalizes ? 'generalizes beyond current champion' : 'generalisation not proven'}
        </div>
      )}
    </>
  )
}

/* ---------------------------------------------------------------- champion */

function ChampionContent({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const champion = championForGeneration(bundle, generation + 1) ?? championOf(bundle)
  if (!champion) return <Empty text="no champion deployed for this run" />
  const version = champion.version
  const stages = version.runtime_graph.nodes.filter((node) => node.enabled)
  return (
    <>
      <div className="champion-line">
        <span className="champion-check">✓</span>
        <span className="mono">{version.id}</span>
      </div>
      <div className="win-grid2">
        <Row label="generation" value={`G${String(version.generation).padStart(2, '0')}`} />
        <Row label="fitness" value={fixed(champion.metrics.fitness)} />
        <Row label="block rate" value={pct(champion.metrics.block_rate)} />
        <Row label="utility" value={pct(champion.metrics.utility_rate)} />
        <Row label="promoted" value={version.promoted_at ? version.promoted_at.slice(0, 19).replace('T', ' ') : 'seed control'} />
        <Row label="parent" value={version.parent_id ?? 'none (seed)'} />
      </div>
      <Section title={`ACTIVE DEFENSES · ${stages.length}`}>
        <div className="chip-line">
          {stages.map((stage) => (
            <span className="chip chip-stage" key={stage.id}>{stage.label}</span>
          ))}
        </div>
      </Section>
      {mode === 'dev' && <div className="win-foot mono muted">{version.mutation_reason || 'seed architecture'}</div>}
    </>
  )
}

/* ------------------------------------------------------------------ events */

function EventsContent({ timeline, onFollow }: { timeline: TimelineItem[]; onFollow: (ref: NodeRef) => void }) {
  const recent = timeline.slice(-120)
  if (recent.length === 0) return <Empty text="no events persisted for this run" />
  return (
    <div className="event-rows">
      {recent.map((item) => (
        <button
          type="button"
          className={`event-row ${item.ref ? '' : 'is-static'}`}
          key={item.id}
          onClick={() => item.ref && onFollow(item.ref)}
          disabled={!item.ref}
        >
          <span className="event-time mono">{item.ts.slice(11, 19)}</span>
          <span className={`event-dot tone-${item.tone}`} />
          <span className="event-text">{item.text}</span>
          <span className="event-detail mono">{item.detail}</span>
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ report */

function ReportContent({ bundle, mode }: { bundle: RunBundle; mode: UiMode }) {
  const report = bundle.report
  if (!report) return <Empty text="no run report persisted in this backend" />
  const checkpoint = reportCheckpoint(bundle)
  return (
    <>
      <div className="mono model-line">{report.run_id}</div>
      <div className="win-grid2">
        <Row label="red" value={`${report.red_model}`} />
        <Row label="blue" value={`${report.blue_model}`} />
        <Row label="red team" value={report.red_team_mode} />
        <Row label="seed" value={mode === 'dev' ? String(report.run_seed) : 'hidden'} />
        <Row label={checkpoint.checkpoint ? 'attacks (at export)' : 'attacks'} value={`${report.attacks_generated}`} />
        <Row label="breaches" value={`${report.attacks_successful}`} tone={report.attacks_successful > 0 ? 'red' : 'green'} />
        <Row label="patches" value={`${report.harness_patches_generated}`} />
        <Row label="promoted" value={`${report.candidates_promoted}`} tone="green" />
        <Row label={checkpoint.checkpoint ? 'model calls (at export)' : 'model calls'} value={`${report.total_model_calls}`} />
        <Row label="champion" value={report.final_blue_champion || '—'} />
      </div>
      {checkpoint.checkpoint && (
        <p className="win-prose muted">
          Export checkpoint: this report was exported after {checkpoint.exportedGenerations} of {checkpoint.persistedGenerations}{' '}
          generations, recording {report.total_model_calls} model calls and {report.attacks_generated} attacks. The snapshot is the
          authoritative record and continued past it: {checkpoint.persistedGenerations} generations, {checkpoint.persistedAttacks}{' '}
          attacks, {checkpoint.persistedCalls} model calls, {checkpoint.promotedPatches} promoted.
        </p>
      )}
      <Section title={checkpoint.checkpoint ? 'PER GENERATION (AT EXPORT)' : 'PER GENERATION'}>
        <div className="table">
          <div className="table-head mono">
            <span>gen</span>
            <span>ASR</span>
            <span>utility</span>
            <span>trend</span>
          </div>
          {report.asr_by_generation.map((asr, index) => (
            <div className="table-row mono" key={index}>
              <span>G{String(index).padStart(2, '0')}</span>
              <span className={asr > 0 ? 'text-red' : 'text-green'}>{pct(asr)}</span>
              <span>{pct(report.utility_by_generation[index])}</span>
              <span className="trend">
                <i style={{ width: `${Math.round(asr * 100)}%` }} className="trend-asr" />
                <i style={{ width: `${Math.round((report.utility_by_generation[index] ?? 0) * 100)}%` }} className="trend-util" />
              </span>
            </div>
          ))}
        </div>
      </Section>
    </>
  )
}

/* -------------------------------------------------------------- generation */

function GenerationContent({ bundle, generation }: { bundle: RunBundle; generation: number }) {
  const record = bundle.generations.find((item) => item.id === generation)
  const candidates = bundle.candidates.filter((candidate) => candidate.generation === generation)
  const patches = bundle.patches.filter((patch) => patch.generation === generation + 1)
  const promoted = patches.find((patch) => patch.status === 'PROMOTED')
  if (!record) return <Empty text={`generation ${generation} has no persisted record`} />
  const breaches = candidates.filter((candidate) =>
    bundle.episodes.some((episode) => episode.attack_success && attackCandidateId(episode.attack_id) === candidate.id),
  ).length
  const story = promoted
    ? `Red attacked ${candidates.length} ways, ${breaches} broke through; Blue proposed ${patches.length} harness patches; ${promoted.child_harness_id?.split('-').pop()} won the replay battery and was promoted.`
    : breaches > 0
      ? `Red attacked ${candidates.length} ways, ${breaches} broke through; Blue responded but no candidate beat the champion.`
      : `Red attacked ${candidates.length} ways; the champion held every one.`
  return (
    <div className="generation-content">
      <div className="generation-title">
        GENERATION {String(generation).padStart(2, '0')}
        <span className="generation-stats mono">
          ASR {pct(record.attack_success_rate)} · utility {pct(record.utility_rate)} · {record.total_battles} battles
        </span>
      </div>
      <p className="win-prose">{story}</p>
    </div>
  )
}

/* ------------------------------------------------------------ red evolution */

function fitnessByVersion(bundle: RunBundle, generation: number): Record<string, number> {
  return bundle.generations.find((record) => record.id === generation)?.red_fitness_by_version ?? {}
}

function RedEvolutionContent({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const mutations = bundle.redVersions
    .filter((version) => version.generation === generation + 1)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
  if (mutations.length === 0) return <Empty text="no mutation was judged at this generation's boundary" />
  const parentFitness = fitnessByVersion(bundle, generation)
  return (
    <>
      <div className="win-statusline">
        {mutations.filter((version) => version.status === 'PROMOTED').length} promoted ·{' '}
        {mutations.filter((version) => version.status === 'REJECTED').length} rejected
      </div>
      <div className="mut-list">
        {mutations.map((mutation) => {
          const parentId = mutation.parent_ids[0]
          const parent = parentId ? bundle.redVersions.find((version) => version.id === parentId) : undefined
          return (
            <div className={`mut-row status-${mutation.status.toLowerCase()}`} key={mutation.id}>
              <div className="mut-head">
                <span className="mono">
                  {shortVersion(parentId)} → {shortVersion(mutation.id)}
                </span>
                <b className={mutation.status === 'PROMOTED' ? 'text-green' : mutation.status === 'REJECTED' ? 'text-amber' : mutation.status === 'RETIRED' ? 'text-slate' : 'text-red'}>
                  {mutation.status}
                </b>
              </div>
              <div className="mut-meta mono">
                fit {fixed(parentId ? parentFitness[parentId] : undefined)} → {fixed(mutation.fitness)}
                {mode === 'dev' && ` · ${mutation.evaluation_episode_ids.length} eval episodes`}
              </div>
              <p className="win-prose">{trim(mutation.mutation_note || mutation.decision_reason, 150)}</p>
            </div>
          )
        })}
      </div>
    </>
  )
}

function RedMutationContent({ bundle, tail, mode }: { bundle: RunBundle; tail: string; mode: UiMode }) {
  const mutation = bundle.redVersions.find((version) => version.id === tail)
  if (!mutation) return <Empty text={`red mutation ${tail} not found`} />
  const parent = mutation.parent_ids[0]
    ? bundle.redVersions.find((version) => version.id === mutation.parent_ids[0])
    : undefined
  const deltas = parent
    ? Object.keys(mutation.tactic_prior)
        .map((family) => ({ family, delta: (mutation.tactic_prior[family] ?? 0) - (parent.tactic_prior[family] ?? 0) }))
        .filter((entry) => Math.abs(entry.delta) > 0.001)
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
        .slice(0, 3)
    : []
  return (
    <>
      <div className={`win-verdict ${mutation.status === 'PROMOTED' ? 'is-held' : mutation.status === 'REJECTED' ? 'is-warn' : ''}`}>
        {mutation.status}
      </div>
      <div className="win-grid2">
        <Row label="parent" value={shortVersion(parent?.id)} />
        <Row label="fitness" value={`${fixed(parent?.fitness)} → ${fixed(mutation.fitness)}`} />
        <Row label="evidence" value={`${mutation.evaluation_episode_ids.length} evaluation episode(s)`} />
        <Row label="model call" value={mode === 'dev' ? mutation.model_call_id.slice(0, 18) : 'red_mutator'} />
      </div>
      <Section title="MUTATION NOTE">
        <p className="win-prose">{mutation.mutation_note || mutation.decision_reason || 'no note persisted'}</p>
      </Section>
      {mode === 'dev' && deltas.length > 0 && (
        <Section title="PRIOR SHIFT">
          <div className="op-lines">
            {deltas.map((entry) => (
              <div className="op-line" key={entry.family}>
                <b className={entry.delta > 0 ? 'text-green' : 'text-red'}>{entry.delta > 0 ? '+' : '−'}</b>
                <span className="mono">
                  {entry.family.replaceAll('_', ' ')} {entry.delta > 0 ? '+' : ''}
                  {entry.delta.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}
      {mode === 'demo' && <p className="win-prose">{trim(mutation.decision_reason, 200)}</p>}
    </>
  )
}

function shortVersion(versionId: string | undefined): string {
  if (!versionId) return '—'
  return versionId.split('-').pop() ?? versionId
}

/* --------------------------------------------------------------------- run */

function RunContent({ runs, runId }: { runs: RunSummary[]; runId: string }) {
  const run = runs.find((item) => item.run_id === runId)
  if (!run) return <Empty text="run no longer in this backend" />
  return (
    <>
      <div className="mono model-line">{run.run_id}</div>
      <div className="win-grid2">
        <Row label="generations" value={String(run.generations)} />
        <Row label="episodes" value={String(run.episodes)} />
        <Row label="model calls" value={String(run.model_calls)} />
        <Row label="patches" value={String(run.patches)} />
        <Row label="report" value={run.has_report ? 'persisted' : 'missing'} tone={run.has_report ? 'green' : 'amber'} />
        <Row label="last activity" value={run.last_activity ? run.last_activity.slice(0, 19).replace('T', ' ') : '—'} />
      </div>
      <div className="win-foot mono muted">click to load this run</div>
    </>
  )
}

/* ------------------------------------------------------------------ helpers */

function trim(value: string, limit: number): string {
  const text = value.trim()
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

function topKey(record: Record<string, number>): string {
  const entries = Object.entries(record ?? {})
  if (entries.length === 0) return '—'
  return entries.sort((a, b) => b[1] - a[1])[0][0].replaceAll('_', ' ')
}

function shortValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export { Empty }
