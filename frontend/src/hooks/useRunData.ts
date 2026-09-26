import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api, subscribeToArena } from '../lib/api'
import { emptyBundle, runStateOf, type NodeRef, type RunBundle, type RunState } from '../lib/viewmodel'
import type { ArenaEvent, RunStatus, RunSummary, SystemStatus } from '../types'

export type UiMode = 'demo' | 'dev'

interface RunDataState {
  bundle: RunBundle
  runId: string | null
  generation: number
  selectedNode: NodeRef | null
  mode: UiMode
  systemStatus: SystemStatus | null
  runs: RunSummary[]
  liveStatus: RunStatus | null
  events: ArenaEvent[]
  loading: boolean
  busy: boolean
  error: string | null
  isLiveRun: boolean
  runState: RunState | null
  runLastActivity: string | null
  setRunId: (runId: string) => void
  setGeneration: (generation: number) => void
  selectNode: (node: NodeRef | null) => void
  setMode: (mode: UiMode) => void
  stop: () => Promise<void>
  refresh: () => Promise<void>
}

export function useRunData(): RunDataState {
  const [bundle, setBundle] = useState<RunBundle>(emptyBundle)
  const [runId, setRunIdState] = useState<string | null>(null)
  const [generation, setGenerationState] = useState(0)
  const [selectedNode, setSelectedNode] = useState<NodeRef | null>(null)
  const [mode, setMode] = useState<UiMode>('demo')
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [liveStatus, setLiveStatus] = useState<RunStatus | null>(null)
  const [events, setEvents] = useState<ArenaEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const refreshTimer = useRef<number | undefined>(undefined)
  const runIdRef = useRef<string | null>(null)

  runIdRef.current = runId

  const loadRun = useCallback(async (targetRunId: string | null) => {
    if (!targetRunId) {
      setBundle(emptyBundle())
      return
    }
    const [report, generations, harnesses, activeHarness, redVersions, blueVersions, candidates, patches, episodes, modelCalls, failures] =
      await Promise.all([
        api.report(targetRunId),
        api.generations(targetRunId),
        api.harnesses(targetRunId),
        api.activeHarness(targetRunId),
        api.redVersions(targetRunId),
        api.blueVersions(targetRunId),
        api.attackCandidates(targetRunId),
        api.patches(targetRunId),
        api.episodes(targetRunId),
        api.modelCalls(targetRunId),
        api.failures(targetRunId),
      ])
    setBundle({ report, generations, harnesses, activeHarness, redVersions, blueVersions, candidates, patches, episodes, modelCalls, failures })
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextRunList, nextSystem] = await Promise.all([
        api.status(),
        api.runs(),
        api.systemStatus(),
      ])
      setSystemStatus(nextSystem)
      setLiveStatus(nextStatus)
      setRuns(nextRunList)
      const target = runIdRef.current ?? nextStatus.run_id ?? nextRunList[0]?.run_id ?? null
      if (!runIdRef.current && target) setRunIdState(target)
      if (target) await loadRun(target)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'DarwinGuard API unavailable')
    } finally {
      setLoading(false)
    }
  }, [loadRun])

  useEffect(() => {
    void refresh()
    const statusPoll = window.setInterval(() => {
      void api.status().then(setLiveStatus).catch(() => undefined)
    }, 2_000)
    const runPoll = window.setInterval(() => {
      void api.runs().then(setRuns).catch(() => undefined)
    }, 3_000)
    const close = subscribeToArena(
      (event) => {
        setEvents((current) => [...current.slice(-300), event])
        window.clearTimeout(refreshTimer.current)
        refreshTimer.current = window.setTimeout(() => {
          void refresh()
        }, 150)
      },
      () => setError('Live event stream disconnected; REST fallback remains available.'),
    )
    return () => {
      close()
      window.clearInterval(statusPoll)
      window.clearInterval(runPoll)
      window.clearTimeout(refreshTimer.current)
    }
  }, [refresh])

  const setRunId = useCallback(
    (next: string) => {
      setRunIdState(next)
      setSelectedNode(null)
      setEvents([])
      void loadRun(next)
    },
    [loadRun],
  )

  const generationIds = useMemo(
    () => bundle.generations.map((record) => record.id).sort((a, b) => a - b),
    [bundle.generations],
  )
  const initializedRun = useRef<string | null>(null)

  useEffect(() => {
    if (generationIds.length === 0) return
    if (initializedRun.current !== runId) {
      initializedRun.current = runId
      setGenerationState(generationIds[generationIds.length - 1])
      return
    }
    if (!generationIds.includes(generation)) {
      setGenerationState(generationIds[generationIds.length - 1])
    }
  }, [generationIds, generation, runId])

  const setGeneration = useCallback((next: number) => {
    setGenerationState(next)
    setSelectedNode(null)
  }, [])

  const stop = useCallback(async () => {
    setBusy(true)
    try {
      await api.stop()
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to stop evolution')
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const isLiveRun = Boolean(liveStatus?.run_id && liveStatus.run_id === runId && (liveStatus.status === 'running' || liveStatus.status === 'started'))
  // Completion and liveness both come from the run's persisted summary, never from a UI
  // timer: COMPLETE = report written; RUNNING = no report but activity within ~120s;
  // anything older is INCOMPLETE.
  const selectedRun = runs.find((run) => run.run_id === runId) ?? null
  const runState = runStateOf(selectedRun)

  return {
    bundle,
    runId,
    generation: generationIds.length > 0 ? generation : 0,
    selectedNode,
    mode,
    systemStatus,
    runs,
    liveStatus,
    events,
    loading,
    busy,
    error,
    setRunId,
    setGeneration,
    selectNode: setSelectedNode,
    setMode,
    stop,
    refresh,
    isLiveRun,
    runState,
    runLastActivity: selectedRun?.last_activity ?? null,
  }
}

export type RunData = RunDataState
