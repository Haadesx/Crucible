import { useEffect, useMemo, useRef, useState } from 'react'

import { Inspector } from './components/Inspector'
import { MetricsHud } from './components/shell/MetricsHud'
import { RunRail } from './components/shell/RunRail'
import { TopBar, type WorkspaceView } from './components/shell/TopBar'
import { VersionsPage } from './components/versions/VersionsPage'
import { WorkspaceCanvas, type WorkspaceApi } from './components/workspace/WorkspaceCanvas'
import { useRunData } from './hooks/useRunData'
import { api } from './lib/api'
import {
  buildLineageGraph,
  buildRunsGraph,
  buildTimeline,
  buildWorkspaceGraph,
  type NodeRef,
} from './lib/viewmodel'
import type { ModelCallRecord, RunMatrix } from './types'

function latestSuccessfulCall(calls: ModelCallRecord[], role: ModelCallRecord['role']): ModelCallRecord | undefined {
  const successful = calls.filter((call) => call.role === role && call.error === null)
  return successful[successful.length - 1]
}

export default function App() {
  const data = useRunData()
  const [view, setView] = useState<WorkspaceView>('versions')
  const [railCollapsed, setRailCollapsed] = useState(false)
  const [matrix, setMatrix] = useState<RunMatrix | null>(null)
  const apiRef = useRef<WorkspaceApi | null>(null)

  useEffect(() => {
    document.title = 'Crucible'
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!data.runId) {
      setMatrix(null)
      return () => {
        cancelled = true
      }
    }
    api
      .matrix(data.runId)
      .then((next) => {
        if (!cancelled) setMatrix(next)
      })
      .catch(() => {
        if (!cancelled) setMatrix(null)
      })
    return () => {
      cancelled = true
    }
  }, [data.runId])

  // Model attribution from the persisted ledger, so historical runs keep their own models.
  const models = useMemo(() => {
    const red = latestSuccessfulCall(data.bundle.modelCalls, 'red_attacker')
    const executor = latestSuccessfulCall(data.bundle.modelCalls, 'blue_executor')
    const engineer = latestSuccessfulCall(data.bundle.modelCalls, 'blue_harness_engineer')
    const localRig = red?.base_url?.includes('ai-rig') ?? false
    return {
      red: red ? `${red.model}${localRig ? ' · local RTX 5090' : ''}` : '—',
      executor: executor?.model ?? '—',
      engineer: engineer?.model ?? '—',
    }
  }, [data.bundle.modelCalls])

  const canvasGraph = useMemo(
    () => buildWorkspaceGraph(data.bundle, data.events),
    [data.bundle, data.events],
  )
  const lineageGraph = useMemo(() => buildLineageGraph(data.bundle), [data.bundle])
  const runsGraph = useMemo(() => buildRunsGraph(data.runs, data.runId), [data.runs, data.runId])
  const timeline = useMemo(
    () => buildTimeline(data.bundle, data.events, data.runId),
    [data.bundle, data.events, data.runId],
  )

  const graph = view === 'lineage' ? lineageGraph : view === 'runs' ? runsGraph : canvasGraph
  const storageKey = `dg:${view}:${data.runId ?? 'none'}`

  const jumpToNode = (nodeId: string) => {
    if (view !== 'canvas') {
      setView('canvas')
      window.setTimeout(() => apiRef.current?.focus(nodeId), 180)
      return
    }
    apiRef.current?.focus(nodeId)
  }

  const follow = (ref: NodeRef) => {
    data.selectNode(ref)
    if (ref.generation !== undefined) data.setGeneration(ref.generation)
    if (view === 'canvas') apiRef.current?.focus(ref.id)
  }

  const focusGeneration = (generation: number) => {
    data.setGeneration(generation)
    jumpToNode(`red:${generation}`)
  }

  return (
    <div className="shell">
      <TopBar
        runId={data.runId}
        systemStatus={data.systemStatus}
        liveStatus={data.liveStatus}
        isLiveRun={data.isLiveRun}
        runState={data.runState}
        runLastActivity={data.runLastActivity}
        generation={data.generation}
        models={models}
        busy={data.busy}
        view={view}
        uiMode={data.mode}
        onView={(next) => {
          setView(next)
          data.selectNode(null)
        }}
        onUiMode={data.setMode}
        onStop={() => void data.stop()}
        onRefresh={() => void data.refresh()}
        onToggleRail={() => setRailCollapsed((value) => !value)}
        railCollapsed={railCollapsed}
      />
      <div className="shell-body">
        <RunRail
          runs={data.runs}
          runId={data.runId}
          bundle={data.bundle}
          generation={data.generation}
          liveStatus={data.liveStatus}
          collapsed={railCollapsed}
          onSelectRun={(runId) => data.setRunId(runId)}
          onFocusGeneration={focusGeneration}
        />
        <main className="workspace">
          {view !== 'versions' && (
            <MetricsHud bundle={data.bundle} generation={data.generation} events={data.events} />
          )}
          {data.loading ? (
            <div className="app-loading">LOADING PERSISTED EVIDENCE…</div>
          ) : view === 'versions' ? (
            <VersionsPage
              matrix={matrix}
              bundle={data.bundle}
              events={data.events}
              timeline={timeline}
              generation={data.generation}
            />
          ) : (
            <WorkspaceCanvas
              key={view}
              graph={graph}
              bundle={data.bundle}
              events={data.events}
              runs={data.runs}
              timeline={timeline}
              mode={data.mode}
              selectedId={data.selectedNode?.id ?? null}
              storageKey={storageKey}
              initialFocusId={view === 'canvas' ? `red:${data.generation}` : null}
              onSelect={(spec) => data.selectNode(spec ? spec.ref : null)}
              onFollow={follow}
              onLoadRun={(runId) => data.setRunId(runId)}
              onGenerationFocus={focusGeneration}
              apiRef={apiRef}
            />
          )}
          {data.error && (
            <div className="error-banner">
              <span>!</span>
              {data.error}
              <button type="button" onClick={() => void data.refresh()}>RETRY</button>
            </div>
          )}
        </main>
        {data.selectedNode && (
          <div className="inspector-drawer">
            <Inspector
              node={data.selectedNode}
              bundle={data.bundle}
              mode={data.mode}
              onClose={() => data.selectNode(null)}
              onSelect={follow}
            />
          </div>
        )}
      </div>
      <footer className="shell-foot">
        <span><i className="footer-dot" /> ALL AGENT ACTIONS SANDBOXED</span>
        <span>
          {data.systemStatus
            ? `${data.systemStatus.run_mode} MODE · ${data.systemStatus.persistence.label}`
            : 'PERSISTENCE STATUS UNAVAILABLE'}
        </span>
        <span>MODEL WEIGHTS FROZEN · HARNESS EVOLVES</span>
      </footer>
    </div>
  )
}
