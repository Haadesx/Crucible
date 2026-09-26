import { useState } from 'react'

import type { UiMode } from '../../hooks/useRunData'
import type { RunState } from '../../lib/viewmodel'
import { lastActivityAge } from '../../lib/viewmodel'
import type { RunStatus, SystemStatus } from '../../types'

export type WorkspaceView = 'versions' | 'canvas' | 'lineage' | 'runs'

const VIEW_LABELS: Record<WorkspaceView, string> = {
  versions: 'VERSIONS',
  canvas: 'EXECUTION TRACE',
  lineage: 'LINEAGE',
  runs: 'RUNS',
}

interface StateChip {
  label: string
  tone: string
  title: string
}

// The chip is the primary persistence state indicator; run_mode alone ("DEV") is not
// enough because a historical snapshot and a live dev snapshot both run in DEV mode.
// The COMPLETE/RUNNING/INCOMPLETE suffix is an operational liveness signal derived from
// the selected run's persisted summary (report + last activity), never a UI timer.
function runStateTitle(state: RunState, lastActivity: string | null): string {
  const age = lastActivityAge(lastActivity)
  if (state === 'COMPLETE') return 'final report persisted'
  if (state === 'RUNNING') return age ? `no final report yet · last activity ${age}` : 'no final report yet'
  return age ? `no final report · last activity ${age}` : 'no final report · activity unknown'
}

function stateChip(status: SystemStatus | null, runState: RunState | null, runLastActivity: string | null): StateChip {
  if (!status) {
    return {
      label: 'STATUS UNAVAILABLE',
      tone: 'unknown',
      title: 'The API did not answer /system/status',
    }
  }
  if (status.read_only) {
    return {
      label: 'HISTORICAL · READ ONLY',
      tone: 'historical',
      title: `Frozen evidence served read-only · ${status.persistence.label}`,
    }
  }
  const live =
    status.persistence.backend === 'mongodb' && status.persistence.atlas_connected
      ? { base: 'LIVE · ATLAS CONNECTED', tone: 'live-atlas' }
      : { base: 'LIVE · DEV SNAPSHOT', tone: 'live-dev' }
  if (runState === null) {
    return { label: live.base, tone: live.tone, title: status.persistence.label }
  }
  return {
    label: `${live.base} · ${runState}`,
    tone: live.tone,
    title: `${status.persistence.label} · ${runStateTitle(runState, runLastActivity)}`,
  }
}

interface TopBarProps {
  runId: string | null
  systemStatus: SystemStatus | null
  liveStatus: RunStatus | null
  isLiveRun: boolean
  runState: RunState | null
  runLastActivity: string | null
  generation: number
  models: { red: string; executor: string; engineer: string }
  busy: boolean
  view: WorkspaceView
  uiMode: UiMode
  onView: (view: WorkspaceView) => void
  onUiMode: (mode: UiMode) => void
  onStop: () => void
  onRefresh: () => void
  onToggleRail: () => void
  railCollapsed: boolean
}

export function TopBar({
  runId,
  systemStatus,
  liveStatus,
  isLiveRun,
  runState,
  runLastActivity,
  generation,
  models,
  busy,
  view,
  uiMode,
  onView,
  onUiMode,
  onStop,
  onRefresh,
  onToggleRail,
  railCollapsed,
}: TopBarProps) {
  const [copied, setCopied] = useState(false)
  const chip = stateChip(systemStatus, runState, runLastActivity)
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button type="button" className="topbar-icon" title="Toggle run rail" onClick={onToggleRail}>
          {railCollapsed ? '▸' : '◂'}
        </button>
        <span className="brand-mark">CR</span>
        <strong className="brand-name">Crucible</strong>
        <span className="brand-tagline">Evolve the harness. Keep the agent useful.</span>
        <span className="topbar-divider" />
        <span className="workspace-label mono" title={systemStatus?.persistence.label ?? ''}>
          <b>{runId ?? 'none'}</b>
        </span>
        <span className="topbar-gen mono">G{String(generation).padStart(2, '0')}</span>
        {isLiveRun && liveStatus && <span className="live-chip mono">● {liveStatus.status.toUpperCase()}</span>}
      </div>

      <div className="topbar-center">
        <div className="mode-switch" role="tablist" aria-label="Workspace view">
          {(Object.keys(VIEW_LABELS) as WorkspaceView[]).map((item) => (
            <button
              type="button"
              role="tab"
              aria-selected={view === item}
              key={item}
              className={view === item ? 'is-active' : ''}
              onClick={() => onView(item)}
            >
              {VIEW_LABELS[item]}
            </button>
          ))}
        </div>
      </div>

      <div className="topbar-right">
        <span className="topbar-models mono" title={`RED ${models.red} · BLUE EXECUTOR ${models.executor} · BLUE ENGINEER ${models.engineer}`}>
          <span className="model-tag"><b>RED</b> {models.red}</span>
          <span className="model-tag"><b>BLUE EXECUTOR</b> {models.executor}</span>
          <span className="model-tag"><b>BLUE ENGINEER</b> {models.engineer}</span>
        </span>
        <div className="segmented-small" role="group" aria-label="Presentation mode">
          <button type="button" className={uiMode === 'demo' ? 'is-active' : ''} onClick={() => onUiMode('demo')}>
            DEMO
          </button>
          <button type="button" className={uiMode === 'dev' ? 'is-active' : ''} onClick={() => onUiMode('dev')}>
            DEV
          </button>
        </div>
        <button type="button" className="topbar-icon" title="Refresh evidence" onClick={onRefresh}>
          ⟳
        </button>
        <button
          type="button"
          className="topbar-button"
          onClick={() => {
            void navigator.clipboard?.writeText(window.location.href)
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1200)
          }}
        >
          {copied ? 'COPIED' : 'SHARE'}
        </button>
        {isLiveRun ? (
          <button type="button" className="topbar-button is-danger" disabled={busy} onClick={onStop}>
            STOP
          </button>
        ) : (
          <button
            type="button"
            className="topbar-button is-primary"
            disabled
            title="LIVE RUNS START FROM THE CO-EVOLUTION RUNTIME"
          >
            ▶ START
          </button>
        )}
        <span className={`mode-pill mode-${chip.tone}`} title={chip.title}>
          <i />
          {chip.label}
        </span>
      </div>
    </header>
  )
}
