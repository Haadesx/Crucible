import type { Episode, MatrixCell, MatrixTest } from '../../types'
import type { RunBundle } from '../../lib/viewmodel'
import { outcomeLabel } from './VersionMatrix'

interface CellInspectorProps {
  cell: MatrixCell | null
  test: MatrixTest | null
  bundle: RunBundle
}

export function CellInspector({ cell, test, bundle }: CellInspectorProps) {
  if (!cell || !test) {
    return <p className="versions-empty mono">click a matrix cell to inspect its episode evidence</p>
  }
  const episode: Episode | undefined = bundle.episodes.find((item) => item.id === cell.episode_id)
  const denials = episode?.gateway_decisions.filter((decision) => decision.decision !== 'allow') ?? []
  return (
    <div className="cell-inspector">
      <div className={`cell-verdict outcome-${cell.outcome.toLowerCase()}`}>{outcomeLabel(cell.outcome)}</div>
      <p className="cell-reason">{cell.reason || 'no reason recorded'}</p>
      <dl className="inspector-kv mono">
        <dt>test</dt>
        <dd>{test.label}</dd>
        <dt>kind</dt>
        <dd>{test.kind} · {test.slice}</dd>
        <dt>family</dt>
        <dd>{test.family ?? '—'}</dd>
        <dt>scenario</dt>
        <dd>{test.scenario_id}</dd>
        <dt>attack</dt>
        <dd>{test.attack_id}</dd>
        <dt>version</dt>
        <dd>{cell.version}</dd>
        <dt>episode</dt>
        <dd>{cell.episode_id || '—'}</dd>
      </dl>
      {episode ? (
        <>
          <div className="inspector-flags mono">
            <span className={episode.attack_success ? 'text-red' : 'text-green'}>
              attack {episode.attack_success ? 'succeeded' : 'blocked'}
            </span>
            <span className={episode.legitimate_task_success ? 'text-green' : 'text-amber'}>
              task {episode.legitimate_task_success ? 'completed' : 'not completed'}
            </span>
          </div>
          <section className="inspector-section">
            <h4>INJECTED CONTENT</h4>
            <pre className="inspector-pre">{episode.attack_payload.slice(0, 360)}</pre>
          </section>
          <section className="inspector-section">
            <h4>CALLS · {episode.executed_tool_calls.length} executed / {episode.proposed_tool_calls.length} proposed</h4>
            <ul className="inspector-list mono">
              {episode.proposed_tool_calls.map((call, index) => {
                const decision = episode.gateway_decisions[index]
                return (
                  <li key={call.call_id}>
                    <span className={decision && decision.decision !== 'allow' ? 'text-amber' : 'text-green'}>
                      {decision?.decision ?? '—'}
                    </span>{' '}
                    {call.name}
                    {decision && decision.reason_codes.length > 0 ? ` · ${decision.reason_codes.join(',')}` : ''}
                  </li>
                )
              })}
            </ul>
            {denials.length === 0 && episode.attack_success && (
              <p className="inspector-note mono">no deny/approval gate fired — the breach executed as proposed</p>
            )}
          </section>
          <section className="inspector-section">
            <h4>RUNTIME TRACE</h4>
            <ul className="inspector-list mono">
              {episode.runtime_trace.slice(-8).map((step, index) => (
                <li key={`${step.stage}-${index}`} className={step.status === 'FAIL' ? 'text-red' : ''}>
                  {step.stage} · {step.status}
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : (
        <p className="inspector-note mono">episode {cell.episode_id || '—'} is not in the loaded bundle</p>
      )}
    </div>
  )
}
