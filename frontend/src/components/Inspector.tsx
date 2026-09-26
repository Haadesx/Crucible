import { useState } from 'react'

import type { UiMode } from '../hooks/useRunData'
import { attackCandidateId, championOf, fixed, pct, type NodeRef, type RunBundle } from '../lib/viewmodel'
import type {
  AttackCandidate,
  BlueAgentVersion,
  Episode,
  FailureMemory,
  HarnessPatchRecord,
  HarnessRecord,
  HarnessVersion,
  ModelCallRecord,
} from '../types'

interface InspectorProps {
  node: NodeRef | null
  bundle: RunBundle
  mode: UiMode
  onClose: () => void
  onSelect: (node: NodeRef) => void
}

export function Inspector({ node, bundle, mode, onClose, onSelect }: InspectorProps) {
  if (!node) {
    return (
      <aside className="inspector">
        <div className="inspector-empty">
          <strong>INSPECTOR</strong>
          <p>Select any card on the canvas to see the real evidence behind it: prompts, model calls, traces, patches and replay results.</p>
        </div>
      </aside>
    )
  }
  return (
    <aside className="inspector">
      <div className="inspector-head">
        <span className="eyebrow">{node.kind.toUpperCase()} INSPECTOR</span>
        <button type="button" className="inspector-close" onClick={onClose} aria-label="Close inspector">×</button>
      </div>
      <InspectorBody node={node} bundle={bundle} mode={mode} onSelect={onSelect} />
    </aside>
  )
}

function InspectorBody({ node, bundle, mode, onSelect }: Omit<InspectorProps, 'onClose'> & { node: NodeRef }) {
  const generation = node.generation ?? 0
  switch (node.kind) {
    case 'red':
      return <RedInspector bundle={bundle} generation={generation} mode={mode} />
    case 'attack':
      return <AttackInspector bundle={bundle} candidateId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'sandbox':
      return <SandboxInspector bundle={bundle} candidateId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'evaluator':
      return <EvaluatorInspector bundle={bundle} candidateId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'blue':
      return <BlueInspector bundle={bundle} generation={generation} mode={mode} onSelect={onSelect} />
    case 'patch':
      return <PatchInspector bundle={bundle} patchId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'candidate':
      return <CandidateInspector bundle={bundle} patchId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'judge':
      return <JudgeInspector bundle={bundle} patchId={node.id.split(':')[2]} mode={mode} onSelect={onSelect} />
    case 'champion':
      return <ChampionInspector bundle={bundle} generation={generation} mode={mode} />
    default:
      return (
        <>
          <div className="inspector-title">
            <strong>{node.kind.replaceAll('_', ' ')}</strong>
            <span className="mono muted">{node.id}</span>
          </div>
          <p className="inspector-muted">
            This window renders its evidence inline on the canvas. Select an execution window — red, attack, sandbox, evaluator, blue,
            patch, candidate, judge or champion — for the full evidence trail.
          </p>
        </>
      )
  }
}

/* ------------------------------------------------------------------ shared */

function KV({ label, value, tone, mono = true }: { label: string; value: string; tone?: string; mono?: boolean }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <b className={`${mono ? 'mono' : ''} ${tone ? `text-${tone}` : ''}`}>{value}</b>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="inspector-section">
      <div className="eyebrow">{title}</div>
      {children}
    </section>
  )
}

function Tabs({ tabs, active, onChange }: { tabs: string[]; active: string; onChange: (tab: string) => void }) {
  return (
    <div className="inspector-tabs">
      {tabs.map((tab) => (
        <button type="button" key={tab} className={active === tab ? 'is-active' : ''} onClick={() => onChange(tab)}>
          {tab}
        </button>
      ))}
    </div>
  )
}

function CallList({ calls, mode, empty }: { calls: ModelCallRecord[]; mode: UiMode; empty: string }) {
  const [open, setOpen] = useState<string | null>(null)
  if (calls.length === 0) return <p className="inspector-muted">{empty}</p>
  return (
    <div className="call-list">
      {calls.map((call) => (
        <div className={`call-row ${call.error ? 'call-error' : ''}`} key={call.id}>
          <div className="call-head">
            <span className="mono">{call.role.replaceAll('_', ' ')}</span>
            <span className={`call-state ${call.error ? 'text-red' : 'text-green'}`}>{call.error ? 'ERROR' : 'OK'}</span>
          </div>
          <div className="call-meta mono">
            {call.provider}/{call.model} · {call.latency_ms}ms · {call.created_at.slice(11, 19)}
          </div>
          {mode === 'dev' && <div className="call-meta mono muted">{call.id} · {call.artifact_type || 'artifact'} · {call.prompt_chars} prompt chars</div>}
          {call.error && <div className="call-error-text">{call.error}</div>}
          <button type="button" className="link-button" onClick={() => setOpen(open === call.id ? null : call.id)}>
            {open === call.id ? 'hide output' : 'show output'}
          </button>
          {open === call.id && <pre className="code-block">{call.output_text || '(no output persisted)'}</pre>}
        </div>
      ))}
    </div>
  )
}

function EpisodeList({ episodes, onSelect, mode }: { episodes: Episode[]; onSelect: (node: NodeRef) => void; mode: UiMode }) {
  if (episodes.length === 0) return <p className="inspector-muted">No executed episodes persisted for this node.</p>
  return (
    <div className="episode-list">
      {episodes.map((episode) => (
        <div className="episode-row" key={episode.id}>
          <div className="episode-head">
            <strong className="mono">{episode.id}</strong>
            <span className={episode.attack_success ? 'text-red' : 'text-green'}>{episode.attack_success ? 'BREACH' : 'HELD'}</span>
          </div>
          <div className="episode-meta mono">
            {episode.scenario_id} · G{String(episode.generation).padStart(2, '0')} · {episode.latency_ms}ms · {episode.model_calls} calls
          </div>
          <div className="episode-trace">
            {episode.runtime_trace.slice(0, mode === 'demo' ? 4 : 8).map((step, index) => (
              <span key={`${step.stage}-${index}`} className={`trace-chip status-${step.status.toLowerCase()}`}>
                {step.stage}
              </span>
            ))}
          </div>
          {episode.proposed_tool_calls.length > 0 && (
            <div className="episode-calls">
              {episode.proposed_tool_calls.map((call, index) => {
                const decision = episode.gateway_decisions[index]
                return (
                  <div key={call.call_id} className="episode-call-row">
                    <span className="mono">{call.name}</span>
                    <b className={decision?.decision === 'allow' ? 'text-green' : decision?.decision === 'deny' ? 'text-red' : 'text-amber'}>
                      {decision?.decision.toUpperCase() ?? 'PENDING'}
                    </b>
                    <small>{decision?.reason_codes[0] ?? ''}</small>
                  </div>
                )
              })}
            </div>
          )}
          <button
            type="button"
            className="link-button"
            onClick={() => onSelect({ kind: 'evaluator', id: `evaluator:${episode.generation}:${attackCandidateId(episode.attack_id)}`, generation: episode.generation })}
          >
            open evaluator evidence
          </button>
        </div>
      ))}
    </div>
  )
}

function FailureCard({ failure }: { failure: FailureMemory }) {
  const analysis = failure.analysis
  return (
    <div className="failure-card">
      <div className="episode-head">
        <strong>{analysis?.root_stage ?? failure.type}</strong>
        <span className="mono">{failure.similarity > 0 ? `${pct(failure.similarity)} match` : 'new failure'}</span>
      </div>
      <p>{analysis?.weakness ?? failure.summary}</p>
      {analysis && analysis.candidate_changes.length > 0 && (
        <div className="failure-changes">
          {analysis.candidate_changes.slice(0, 4).map((change) => (
            <span key={change}>{change}</span>
          ))}
        </div>
      )}
      {analysis && analysis.evidence.length > 0 && <pre className="code-block">{analysis.evidence.join('\n')}</pre>}
    </div>
  )
}

function dnaRows(version: HarnessVersion): Array<{ label: string; value: string; on: boolean }> {
  return [
    { label: 'context', value: version.context_policy.isolation_mode, on: version.context_policy.isolation_mode !== 'FLAT' },
    { label: 'trust', value: version.trust_policy.enabled ? (version.trust_policy.external_content_trusted ? 'trusted' : 'untrusted') : 'off', on: version.trust_policy.enabled },
    { label: 'memory', value: version.memory_policy.filter_mode, on: version.memory_policy.filter_mode !== 'OFF' },
    { label: 'goal binding', value: version.tool_policy.goal_binding_enabled ? 'on' : 'off', on: version.tool_policy.goal_binding_enabled },
    { label: 'risk gate', value: version.tool_policy.gateway_enabled ? version.tool_policy.risk_threshold.toFixed(2) : 'off', on: version.tool_policy.gateway_enabled },
    { label: 'verifier', value: version.verifier_policy.enabled ? version.verifier_policy.verifier_model : 'off', on: version.verifier_policy.enabled },
  ]
}

function HarnessDNA({ record }: { record: HarnessRecord }) {
  return (
    <div className="dna-grid">
      {dnaRows(record.version).map((row) => (
        <div key={row.label} className={`dna-cell ${row.on ? 'is-on' : ''}`}>
          <span>{row.label}</span>
          <b>{row.value}</b>
        </div>
      ))}
    </div>
  )
}

function StageList({ version }: { version: HarnessVersion }) {
  const nodes = version.runtime_graph.nodes
  const enabled = nodes.filter((item) => item.enabled)
  return (
    <div className="stage-list">
      {enabled.map((item) => (
        <span className="stage-chip" key={item.id}>
          {item.label}
        </span>
      ))}
      <span className="stage-chip stage-off">{nodes.length - enabled.length} disabled</span>
    </div>
  )
}

/* --------------------------------------------------------------- inspector */

function RedInspector({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const versions = bundle.redVersions.filter((version) => version.generation === generation)
  const calls = bundle.modelCalls.filter((call) => call.role.startsWith('red') && call.generation === generation)
  const candidates = bundle.candidates.filter((candidate) => candidate.generation === generation)
  return (
    <>
      <div className="inspector-title">
        <strong>Red agent · G{String(generation).padStart(2, '0')}</strong>
        <span className="mono muted">{versions.map((version) => version.id).join(' · ') || 'no version persisted'}</span>
      </div>
      <Section title="AGENT VERSIONS">
        {versions.map((version) => (
          <div className="agent-card" key={version.id}>
            <KV label="VERSION" value={version.id} />
            <KV label="MODEL" value={version.base_model} />
            <KV label="FITNESS" value={fixed(version.fitness)} />
            <KV label="PARENTS" value={version.parent_ids.join(' · ') || 'seed'} />
            <p className="strategy-text">{version.system_strategy}</p>
            {mode === 'dev' && <KV label="MODEL CALL" value={version.model_call_id} />}
          </div>
        ))}
        {versions.length === 0 && <p className="inspector-muted">No Red agent version persisted for this generation.</p>}
      </Section>
      <Section title={`GENERATED ATTACKS · ${candidates.length}`}>
        <div className="pill-row">
          {candidates.map((candidate) => (
            <span className="pill" key={candidate.id}>{candidate.id.split('-').pop()}</span>
          ))}
        </div>
      </Section>
      <Section title={`MODEL CALLS · ${calls.length}`}>
        <CallList calls={calls} mode={mode} empty="No Red inference calls persisted for this generation." />
      </Section>
    </>
  )
}

function findCandidate(bundle: RunBundle, candidateId: string): AttackCandidate | undefined {
  return bundle.candidates.find((candidate) => candidate.id === candidateId)
}

function AttackInspector({ bundle, candidateId, mode, onSelect }: { bundle: RunBundle; candidateId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const candidate = findCandidate(bundle, candidateId)
  const [tab, setTab] = useState('overview')
  if (!candidate) return <p className="inspector-muted">Attack candidate {candidateId} not found in this run.</p>
  const episodes = bundle.episodes.filter((episode) => attackCandidateId(episode.attack_id) === candidateId)
  const call = bundle.modelCalls.find((item) => item.id === candidate.model_call_id)
  const breach = episodes.some((episode) => episode.attack_success)
  return (
    <>
      <div className="inspector-title">
        <strong>Attack {candidate.id}</strong>
        <span className={breach ? 'text-red' : 'text-green'}>{breach ? 'BREACH' : episodes.length ? 'HELD' : 'PENDING'}</span>
      </div>
      <Tabs tabs={['overview', 'prompt', 'raw output', 'execution']} active={tab} onChange={setTab} />
      {tab === 'overview' && (
        <>
          <KV label="GENERATION" value={`G${String(candidate.generation).padStart(2, '0')}`} />
          <KV label="ATTACK FAMILY" value={candidate.attack_family.replaceAll('_', ' ')} />
          <KV label="CARRIER" value={candidate.carrier} />
          <KV label="TARGET" value={candidate.target_capability} />
          <KV label="SCENARIO" value={candidate.scenario_id} />
          <KV label="GENERATED BY" value={candidate.generated_by_model} />
          <KV label="NOVELTY" value={fixed(candidate.novelty_score)} />
          <KV label="FITNESS" value={fixed(candidate.fitness)} />
          {mode === 'dev' && <KV label="MODEL CALL" value={candidate.model_call_id} />}
          {candidate.parent_attack_ids.length > 0 && <KV label="PARENTS" value={candidate.parent_attack_ids.join(', ')} />}
          {candidate.attack_plan && <Section title="ATTACK PLAN"><p className="strategy-text">{candidate.attack_plan}</p></Section>}
          <Section title="EXECUTED EPISODES">
            <EpisodeList episodes={episodes} onSelect={onSelect} mode={mode} />
          </Section>
        </>
      )}
      {tab === 'prompt' && <pre className="code-block">{candidate.payload}</pre>}
      {tab === 'raw output' && (call ? <pre className="code-block">{call.output_text || '(no output persisted)'}</pre> : <p className="inspector-muted">Origin model call not found.</p>)}
      {tab === 'execution' && <EpisodeList episodes={episodes} onSelect={onSelect} mode={mode} />}
    </>
  )
}

function SandboxInspector({ bundle, candidateId, mode, onSelect }: { bundle: RunBundle; candidateId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const episodes = bundle.episodes.filter((episode) => attackCandidateId(episode.attack_id) === candidateId)
  return (
    <>
      <div className="inspector-title">
        <strong>Sandbox execution</strong>
        <span className="muted mono">{episodes.length} episode(s)</span>
      </div>
      {episodes.map((episode) => (
        <Section key={episode.id} title={episode.id}>
          <KV label="STATUS" value={episode.attack_success ? 'completed · breach' : 'completed · contained'} tone={episode.attack_success ? 'red' : 'green'} />
          <KV label="DURATION" value={`${episode.latency_ms}ms`} />
          <KV label="TOOL CALLS" value={`${episode.executed_tool_calls.length} executed / ${episode.proposed_tool_calls.length} proposed`} />
          <KV label="FINAL RESPONSE" value={episode.final_response || '—'} mono={false} />
          <div className="trace-table">
            {episode.runtime_trace.map((step, index) => (
              <div className="trace-row" key={`${step.stage}-${index}`}>
                <span className={`trace-dot status-${step.status.toLowerCase()}`} />
                <b>{step.stage}</b>
                <span className={`mono status-${step.status.toLowerCase()}`}>{step.status}</span>
                <small className="mono">{Object.entries(step.details).slice(0, 2).map(([key, value]) => `${key}=${String(value)}`).join(' · ')}</small>
              </div>
            ))}
            {episode.runtime_trace.length === 0 && <p className="inspector-muted">No runtime trace was persisted for this episode.</p>}
          </div>
          {mode === 'dev' && episode.sandbox_snapshot && Object.keys(episode.sandbox_snapshot).length > 0 && (
            <pre className="code-block">{JSON.stringify(episode.sandbox_snapshot, null, 2)}</pre>
          )}
        </Section>
      ))}
      <button type="button" className="link-button" onClick={() => onSelect({ kind: 'evaluator', id: `evaluator:${episodes[0]?.generation ?? 0}:${candidateId}`, generation: episodes[0]?.generation ?? 0 })}>
        open evaluator verdict
      </button>
    </>
  )
}

function EvaluatorInspector({ bundle, candidateId, mode, onSelect }: { bundle: RunBundle; candidateId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const episodes = bundle.episodes.filter((episode) => attackCandidateId(episode.attack_id) === candidateId)
  const breaches = episodes.filter((episode) => episode.attack_success)
  const failure = breaches[0] ? bundle.failures.find((item) => item.episode_id === breaches[0].id) : undefined
  return (
    <>
      <div className="inspector-title">
        <strong>Evaluator · {candidateId}</strong>
        <span className={breaches.length > 0 ? 'text-red' : 'text-green'}>{breaches.length > 0 ? 'BREACH' : 'HELD'}</span>
      </div>
      <KV label="EPISODES" value={String(episodes.length)} />
      <KV label="BREACHES" value={String(breaches.length)} />
      <KV label="ASR" value={pct(episodes.length ? breaches.length / episodes.length : null)} />
      <KV label="SECURITY" value={pct(episodes[0]?.security_score)} />
      <KV label="UTILITY" value={pct(episodes[0]?.utility_score)} />
      <KV label="DETERMINISTIC" value="yes — evaluator owns the verdict" />
      {failure ? (
        <Section title="FAILURE ANALYSIS">
          <FailureCard failure={failure} />
        </Section>
      ) : (
        <Section title="FAILURE ANALYSIS">
          <p className="inspector-muted">{breaches.length === 0 ? 'No breach recorded; no failure memory was created.' : 'Failure memory not persisted for this episode.'}</p>
        </Section>
      )}
      <EpisodeList episodes={episodes} onSelect={onSelect} mode={mode} />
    </>
  )
}

function findPatch(bundle: RunBundle, patchId: string): HarnessPatchRecord | undefined {
  return bundle.patches.find((patch) => patch.id === patchId)
}

function patchOpsSummary(patch: HarnessPatchRecord) {
  const added = patch.patch.operations.filter((op) => op.op === 'ADD_STAGE')
  const removed = patch.patch.operations.filter((op) => op.op === 'REMOVE_STAGE')
  const other = patch.patch.operations.filter((op) => op.op !== 'ADD_STAGE' && op.op !== 'REMOVE_STAGE')
  return { added, removed, other }
}

/** Every ledger call that took part in authoring this patch, oldest first. */
function authoringPath(bundle: RunBundle, patch: HarnessPatchRecord): ModelCallRecord[] {
  const ids = new Set([...patch.repair_call_ids, patch.model_call_id])
  return bundle.modelCalls
    .filter((call) => ids.has(call.id))
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
}

function PatchInspector({ bundle, patchId, mode, onSelect }: { bundle: RunBundle; patchId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const patch = findPatch(bundle, patchId)
  const [tab, setTab] = useState('changes')
  if (!patch) return <p className="inspector-muted">Patch {patchId} not found in this run.</p>
  const { added, removed, other } = patchOpsSummary(patch)
  const engineerCall = bundle.modelCalls.find((call) => call.id === patch.model_call_id)
  // The patch is produced in generation N as the answer to generation N-1's breach.
  const sourceEpisode = bundle.episodes.find(
    (episode) => episode.attack_success && episode.generation === patch.generation - 1,
  )
  const sourceFailure = sourceEpisode ? bundle.failures.find((failure) => failure.episode_id === sourceEpisode.id) : undefined
  return (
    <>
      <div className="inspector-title">
        <strong>HarnessPatch {patch.id}</strong>
        <span className={patch.status === 'PROMOTED' ? 'text-green' : patch.status === 'REJECTED' ? 'text-amber' : 'text-violet'}>{patch.status}</span>
      </div>
      <Tabs tabs={['changes', 'validation', 'structured patch', 'raw output']} active={tab} onChange={setTab} />
      {tab === 'changes' && (
        <>
          <KV label="PARENT" value={patch.parent_harness_id} />
          <KV label="CHILD" value={patch.child_harness_id ?? 'not compiled'} />
          <KV label="AUTHORED BY" value={engineerCall ? `${engineerCall.provider}/${engineerCall.model}` : 'engineer call not found'} />
          <KV label="SOURCE FAILURE" value={sourceFailure?.id ?? sourceEpisode?.id ?? 'breach evidence'} />
          <Section title="CHANGES">
            <div className="change-list">
              {added.map((op) => (
                <div className="change-row" key={`${op.op}-${op.target}`}>
                  <b className="text-green">+ stage</b>
                  <span className="mono">{op.target}</span>
                  <small>{op.reason}</small>
                </div>
              ))}
              {removed.map((op) => (
                <div className="change-row" key={`${op.op}-${op.target}`}>
                  <b className="text-red">− stage</b>
                  <span className="mono">{op.target}</span>
                  <small>{op.reason}</small>
                </div>
              ))}
              {other.map((op) => (
                <div className="change-row" key={`${op.op}-${op.target}`}>
                  <b className="text-cyan">~ {op.op.replaceAll('_', ' ').toLowerCase()}</b>
                  <span className="mono">
                    {op.target} → {JSON.stringify(op.value)}
                  </span>
                  <small>{op.reason}</small>
                </div>
              ))}
            </div>
          </Section>
          <Section title="BLUE ANALYSIS">
            <p className="strategy-text">{patch.patch.analysis}</p>
            {patch.patch.expected_effect && <p className="strategy-text muted">Expected: {patch.patch.expected_effect}</p>}
          </Section>
          <Section title={`AUTHORING PATH · ${authoringPath(bundle, patch).length} call(s)`}>
            {authoringPath(bundle, patch).map((call) => {
              const accepted = call.id === patch.model_call_id
              return (
                <div className="episode-call-row" key={call.id}>
                  <span className="mono">{call.model}</span>
                  <b className={accepted ? 'text-green' : call.error ? 'text-red' : 'text-amber'}>
                    {accepted ? 'ACCEPTED' : call.error ? 'ERROR' : 'REJECTED'}
                  </b>
                  <small>{call.error ?? (accepted ? 'authored the patch' : 'output failed schema/compiler validation')}</small>
                </div>
              )
            })}
          </Section>
          {patch.patch.retrieved_memory_ids.length > 0 && (
            <Section title="RETRIEVED MEMORY">
              <div className="pill-row">
                {patch.patch.retrieved_memory_ids.map((id) => <span className="pill" key={id}>{id}</span>)}
              </div>
            </Section>
          )}
          {patch.child_harness_id && (
            <button type="button" className="link-button" onClick={() => onSelect({ kind: 'candidate', id: `candidate:${patch.generation - 1}:${patch.id}`, generation: patch.generation - 1 })}>
              open candidate harness
            </button>
          )}
        </>
      )}
      {tab === 'validation' && (
        <>
          <KV label="VALID" value={patch.valid ? 'yes' : 'no'} tone={patch.valid ? 'green' : 'red'} />
          <KV label="REJECTION" value={patch.rejection_reason || 'none'} />
          <Section title="LIFECYCLE">
            <div className="transition-list">
              {patch.transitions.map((transition, index) => (
                <div className="transition-row" key={`${transition.status}-${index}`}>
                  <span className={`transition-dot ${transition.status === 'PROMOTED' ? 'text-green' : transition.status === 'REJECTED' ? 'text-amber' : ''}`} />
                  <b>{transition.status}</b>
                  <small className="mono">{transition.at.slice(11, 19)}</small>
                  <span>{transition.detail}</span>
                </div>
              ))}
            </div>
          </Section>
          {engineerCall && (
            <Section title="REPAIRS">
              <KV label="REPAIR CALLS" value={String(patch.repair_call_ids.length)} />
              {patch.repair_call_ids.map((id) => <KV key={id} label="LEDGER" value={id} />)}
            </Section>
          )}
        </>
      )}
      {tab === 'structured patch' && <pre className="code-block">{JSON.stringify(patch.patch, null, 2)}</pre>}
      {tab === 'raw output' && <pre className="code-block">{patch.raw_response || '(raw response not persisted)'}</pre>}
      {mode === 'dev' && (
        <Section title="LEDGER">
          <KV label="ENGINEER CALL" value={patch.model_call_id || '—'} />
          <KV label="CREATED" value={patch.created_at} />
        </Section>
      )}
    </>
  )
}

function CandidateInspector({ bundle, patchId, mode, onSelect }: { bundle: RunBundle; patchId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const patch = findPatch(bundle, patchId)
  const harness = patch?.child_harness_id ? bundle.harnesses.find((record) => record.version.id === patch.child_harness_id) : undefined
  if (!patch || !harness) return <p className="inspector-muted">Candidate harness for {patchId} is not compiled or persisted.</p>
  const version = harness.version
  const metrics = patch.metrics
  return (
    <>
      <div className="inspector-title">
        <strong>{version.id}</strong>
        <span className={patch.status === 'PROMOTED' ? 'text-green' : patch.status === 'REJECTED' ? 'text-amber' : 'text-cyan'}>{patch.status}</span>
      </div>
      <KV label="PARENT" value={patch.parent_harness_id} />
      <KV label="COMPILED" value={harness.deployment.compiled_at ? 'yes' : 'no'} tone={harness.deployment.compiled_at ? 'green' : 'amber'} />
      <KV label="LIFECYCLE" value={patch.status} />
      <KV label="FITNESS" value={fixed(metrics?.fitness ?? harness.metrics.fitness)} />
      <KV label="UTILITY" value={pct(metrics?.utility_rate ?? harness.metrics.utility_rate)} />
      <KV label="BLOCK RATE" value={pct(metrics?.block_rate ?? harness.metrics.block_rate)} />
      <KV label="REPLAYS" value={String(metrics?.battles ?? harness.metrics.battles)} />
      <Section title="SLICES">
        {metrics && Object.keys(metrics.slices).length > 0 ? (
          Object.entries(metrics.slices).map(([name, slice]) => (
            <KV key={name} label={name.toUpperCase()} value={`${slice.episodes} eps · sec ${pct(slice.security)} · util ${pct(slice.utility)}`} />
          ))
        ) : (
          <p className="inspector-muted">No slice breakdown persisted.</p>
        )}
      </Section>
      <Section title="HARNESS DNA">
        <HarnessDNA record={harness} />
      </Section>
      <Section title="ACTIVE STAGES">
        <StageList version={version} />
      </Section>
      <button type="button" className="link-button" onClick={() => onSelect({ kind: 'patch', id: `patch:${patch.generation - 1}:${patch.id}`, generation: patch.generation - 1 })}>
        open originating patch
      </button>
      {mode === 'dev' && <KV label="RUN" value={version.run_id ?? '—'} />}
    </>
  )
}

function JudgeInspector({ bundle, patchId, mode, onSelect }: { bundle: RunBundle; patchId: string; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  const patch = findPatch(bundle, patchId)
  if (!patch) return <p className="inspector-muted">No judge record for {patchId}.</p>
  const signal = bundle.report?.anti_overfitting.find((item) => item.candidate_id.startsWith(patchId.replace('PATCH-', 'A-')))
  return (
    <>
      <div className="inspector-title">
        <strong>Replay verdict</strong>
        <span className={patch.status === 'PROMOTED' ? 'text-green' : patch.status === 'REJECTED' ? 'text-amber' : 'text-cyan'}>{patch.status}</span>
      </div>
      <KV label="DECISION" value={patch.transitions[patch.transitions.length - 1]?.detail || 'in flight'} mono={false} />
      {patch.metrics && (
        <>
          <KV label="BATTLES" value={String(patch.metrics.battles)} />
          <KV label="FITNESS" value={fixed(patch.metrics.fitness)} />
          <KV label="BLOCK RATE" value={pct(patch.metrics.block_rate)} />
          <KV label="UTILITY" value={pct(patch.metrics.utility_rate)} />
          <KV label="LATENCY PENALTY" value={fixed(patch.metrics.latency_penalty)} />
          <KV label="COST PENALTY" value={fixed(patch.metrics.cost_penalty)} />
        </>
      )}
      {signal && (
        <Section title="ANTI-OVERFITTING">
          <KV label="GENERALIZES" value={signal.generalizes ? 'yes' : 'not proven'} tone={signal.generalizes ? 'green' : 'amber'} />
          <KV label="BEAT CHAMPION" value={signal.beat_current_champion ? 'yes' : 'no'} />
          <KV label="SAMPLED" value={signal.sampled_champion_ids.length ? signal.sampled_champion_ids.join(' · ') : 'no historical champions sampled'} />
        </Section>
      )}
      <button type="button" className="link-button" onClick={() => onSelect({ kind: 'patch', id: `patch:${patch.generation - 1}:${patch.id}`, generation: patch.generation - 1 })}>
        open patch evidence
      </button>
      {mode === 'dev' && <KV label="PATCH" value={patch.id} />}
    </>
  )
}

function BlueInspector({ bundle, generation, mode, onSelect }: { bundle: RunBundle; generation: number; mode: UiMode; onSelect: (node: NodeRef) => void }) {
  // Blue's patches are authored in generation N+1 as the answer to generation N's breach.
  const versions = bundle.blueVersions.filter((version) => version.generation === generation + 1)
  const calls = bundle.modelCalls.filter((call) => call.role.startsWith('blue') && call.generation === generation + 1)
  const patches = bundle.patches.filter((patch) => patch.generation === generation + 1)
  const engineerCalls = calls.filter((call) => call.role === 'blue_harness_engineer')
  const engineerModel = [...engineerCalls].reverse().find((call) => call.error === null)?.model ?? '—'
  const fallbackUsed = new Set(engineerCalls.map((call) => call.model)).size > 1
  return (
    <>
      <div className="inspector-title">
        <strong>Blue engineer · G{String(generation).padStart(2, '0')}</strong>
        <span className="mono muted">{versions.map((version: BlueAgentVersion) => version.id).join(' · ') || 'standby'}</span>
      </div>
      <Section title="ENGINEER ATTRIBUTION">
        <KV label="ENGINEER MODEL (PATCH AUTHOR)" value={engineerModel} />
        <KV label="EXECUTOR MODEL (EPISODES)" value={versions[0]?.base_model ?? '—'} />
        <KV label="FALLBACK" value={fallbackUsed ? 'used this generation' : 'not used'} tone={fallbackUsed ? 'amber' : undefined} />
      </Section>
      <Section title="AGENT VERSIONS">
        {versions.map((version) => (
          <div className="agent-card" key={version.id}>
            <KV label="VERSION" value={version.id} />
            <KV label="MODEL" value={version.base_model} />
            <KV label="TARGET HARNESS" value={version.harness_version_id} />
            <KV label="FITNESS" value={fixed(version.fitness)} />
            {mode === 'dev' && <KV label="MEMORY POLICY" value={version.memory_policy_id} />}
          </div>
        ))}
        {versions.length === 0 && <p className="inspector-muted">No Blue agent version for this generation.</p>}
      </Section>
      <Section title={`PATCH ATTEMPTS · ${patches.length}`}>
        <div className="pill-row">
          {patches.map((patch) => (
            <button
              type="button"
              key={patch.id}
              className={`pill pill-button ${patch.status === 'PROMOTED' ? 'pill-green' : patch.status === 'REJECTED' ? 'pill-amber' : ''}`}
              onClick={() => onSelect({ kind: 'patch', id: `patch:${generation}:${patch.id}`, generation })}
            >
              {patch.id.split('-').pop()} · {patch.status}
            </button>
          ))}
        </div>
      </Section>
      <Section title={`MODEL CALLS · ${calls.length}`}>
        <CallList calls={calls} mode={mode} empty="No Blue inference calls for this generation." />
      </Section>
    </>
  )
}

function ChampionInspector({ bundle, generation, mode }: { bundle: RunBundle; generation: number; mode: UiMode }) {
  const champion = championOf(bundle)
  if (!champion) return <p className="inspector-muted">No champion is deployed for this run.</p>
  const version = champion.version
  return (
    <>
      <div className="inspector-title">
        <strong>{version.id}</strong>
        <span className="text-gold">{version.promoted_at ? 'DEPLOYED' : 'SEED'}</span>
      </div>
      <KV label="GENERATION" value={`G${String(version.generation).padStart(2, '0')}`} />
      <KV label="FITNESS" value={fixed(champion.metrics.fitness)} />
      <KV label="BLOCK RATE" value={pct(champion.metrics.block_rate)} />
      <KV label="UTILITY" value={pct(champion.metrics.utility_rate)} />
      <KV label="PROMOTED" value={version.promoted_at ?? 'seed control (never mutated)'} />
      <KV label="PARENT" value={version.parent_id ?? 'none'} />
      {mode === 'dev' && <KV label="RUN" value={version.run_id ?? '—'} />}
      <Section title="HARNESS DNA">
        <HarnessDNA record={champion} />
      </Section>
      <Section title={`ACTIVE DEFENSES · ${version.runtime_graph.nodes.filter((item) => item.enabled).length}`}>
        <StageList version={version} />
      </Section>
      <Section title={`MUTATION · G${String(generation).padStart(2, '0')}`}>
        <p className="strategy-text">{version.mutation_reason || 'Seed architecture — no mutation applied.'}</p>
      </Section>
    </>
  )
}
