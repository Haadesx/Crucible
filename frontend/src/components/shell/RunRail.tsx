import { lineageSummary, type RunBundle } from '../../lib/viewmodel'
import type { RunStatus, RunSummary } from '../../types'

interface RunRailProps {
  runs: RunSummary[]
  runId: string | null
  bundle: RunBundle
  generation: number
  liveStatus: RunStatus | null
  collapsed: boolean
  onSelectRun: (runId: string) => void
  onFocusGeneration: (generation: number) => void
}

export function RunRail({
  runs,
  runId,
  bundle,
  generation,
  liveStatus,
  collapsed,
  onSelectRun,
  onFocusGeneration,
}: RunRailProps) {
  if (collapsed) {
    return (
      <nav className="run-rail is-collapsed" aria-label="Runs">
        <div className="rail-dots">
          {runs.slice(0, 12).map((run) => (
            <button
              type="button"
              key={run.run_id}
              className={`rail-dot ${run.run_id === runId ? 'is-active' : ''}`}
              title={run.run_id}
              onClick={() => onSelectRun(run.run_id)}
            >
              {run.run_id.slice(0, 1)}
            </button>
          ))}
        </div>
      </nav>
    )
  }
  return (
    <nav className="run-rail" aria-label="Runs">
      <label className="rail-search">
        <span aria-hidden="true">⌕</span>
        <input placeholder="Find run…" value="" readOnly title="Run filtering lives in the command bar" />
      </label>
      <div className="rail-label">Pinned &amp; recent</div>
      <div className="rail-runs">
        {runs.length === 0 && <span className="rail-empty">nothing persisted in this backend</span>}
        {runs.map((run) => (
          <button
            type="button"
            key={run.run_id}
            className={`rail-run ${run.run_id === runId ? 'is-active' : ''}`}
            onClick={() => onSelectRun(run.run_id)}
          >
            <span className="rail-run-name mono">{run.run_id.slice(0, 20)}</span>
            <span className="rail-run-meta mono">
              {run.generations}g · {run.episodes}ep · {run.model_calls}calls
            </span>
          </button>
        ))}
      </div>

      {bundle.generations.length > 0 && (
        <>
          <div className="rail-label">Generations</div>
          <div className="rail-generations">
            {[...bundle.generations]
              .sort((a, b) => a.id - b.id)
              .map((record) => {
                const summary = lineageSummary(bundle, record.id)
                const live = liveStatus?.run_id === runId && liveStatus.generation === record.id && liveStatus.status === 'running'
                return (
                  <button
                    type="button"
                    key={record.id}
                    className={`rail-generation ${generation === record.id ? 'is-active' : ''}`}
                    onClick={() => onFocusGeneration(record.id)}
                    title={summary}
                  >
                    <span className={`rail-gen-mark ${summary.includes('promoted') ? 'is-promoted' : record.attack_success_rate > 0 ? 'is-breach' : 'is-held'}`}>
                      {summary.includes('promoted') ? '✓' : record.attack_success_rate > 0 ? '!' : '◇'}
                    </span>
                    <span className="mono">G{String(record.id).padStart(2, '0')}</span>
                    {live && <span className="rail-live">LIVE</span>}
                  </button>
                )
              })}
          </div>
        </>
      )}

      <button
        type="button"
        className="rail-new"
        disabled
        title="LIVE RUNS START FROM THE CO-EVOLUTION RUNTIME"
      >
        + Start new run
      </button>
    </nav>
  )
}
