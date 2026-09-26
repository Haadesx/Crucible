import type {
  ArenaEvent,
  AttackCandidate,
  BlueAgentVersion,
  Episode,
  FailureMemory,
  Generation,
  HarnessComparisonResponse,
  HarnessDiff,
  HarnessPatchRecord,
  HarnessRecord,
  LineageResponse,
  ModelCallRecord,
  RedAgentVersion,
  ReplayResponse,
  RunMatrix,
  RunReport,
  RunStatus,
  RunSummary,
  SystemStatus,
} from '../types'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || `${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

async function optionalRequest<T>(path: string): Promise<T | null> {
  try {
    return await request<T>(path)
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 404) return null
    throw reason
  }
}

export const api = {
  status: () => request<RunStatus>('/arena/status'),
  stop: () => request<{ status: string }>('/arena/stop', { method: 'POST' }),
  reset: () => request<{ status: string }>('/arena/reset', { method: 'POST' }),
  lineage: (runId?: string | null) =>
    request<LineageResponse>(`/arena/lineage${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  generations: (runId?: string | null) =>
    request<Generation[]>(`/generations${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  harnesses: (runId?: string | null) =>
    request<HarnessRecord[]>(`/harnesses${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  harness: (harnessId: string) => request<HarnessRecord>(`/harnesses/${encodeURIComponent(harnessId)}`),
  activeHarness: (runId?: string | null) =>
    optionalRequest<HarnessRecord>(
      `/harnesses/active${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`,
    ),
  harnessDiff: (fromId: string, toId: string) =>
    request<HarnessDiff>(`/harnesses/${encodeURIComponent(fromId)}/diff/${encodeURIComponent(toId)}`),
  harnessFailures: (harnessId: string) =>
    request<FailureMemory[]>(`/harnesses/${encodeURIComponent(harnessId)}/failures`),
  failures: (runId?: string | null) =>
    request<FailureMemory[]>(`/memory/failures${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  compare: (attackId: string, harnessBId: string, scenarioId: string) =>
    request<HarnessComparisonResponse>('/replay/compare', {
      method: 'POST',
      body: JSON.stringify({
        attack_id: attackId,
        scenario_id: scenarioId,
        harness_a_id: null,
        harness_b_id: harnessBId,
      }),
    }),
  replay: (attackId: string, defenseId: string, scenarioId: string) =>
    request<ReplayResponse>('/replay', {
      method: 'POST',
      body: JSON.stringify({ attack_id: attackId, defense_id: defenseId, scenario_id: scenarioId }),
    }),
  systemStatus: () => request<SystemStatus>('/system/status'),
  runs: () => request<RunSummary[]>('/runs'),
  episodes: (runId?: string | null, limit = 200) =>
    request<Episode[]>(`/episodes?${queryParams(runId, limit)}`),
  modelCalls: (runId?: string | null, limit = 500) =>
    request<ModelCallRecord[]>(`/model-calls?${queryParams(runId, limit)}`),
  patches: (runId?: string | null, limit = 200) =>
    request<HarnessPatchRecord[]>(`/patches?${queryParams(runId, limit)}`),
  redVersions: (runId?: string | null) =>
    request<RedAgentVersion[]>(`/red-versions${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  blueVersions: (runId?: string | null) =>
    request<BlueAgentVersion[]>(`/blue-versions${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  attackCandidates: (runId?: string | null) =>
    request<AttackCandidate[]>(`/attack-candidates${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`),
  report: (runId: string) =>
    optionalRequest<RunReport>(`/runs/${encodeURIComponent(runId)}/report`),
  // The frozen Crucible matrix contract; a 404 means the endpoint is not deployed and the
  // versions view shows "matrix unavailable" rather than inventing a fallback.
  matrix: (runId: string) => optionalRequest<RunMatrix>(`/runs/${encodeURIComponent(runId)}/matrix`),
}

function queryParams(runId: string | null | undefined, limit: number): string {
  const params = new URLSearchParams({ limit: String(limit) })
  if (runId) params.set('run_id', runId)
  return params.toString()
}

export function eventSocketUrl(): string {
  if (API_URL) {
    const url = new URL(API_URL)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = '/ws/arena'
    return url.toString()
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/arena`
}

export function subscribeToArena(
  onEvent: (event: ArenaEvent) => void,
  onError?: () => void,
): () => void {
  const socket = new WebSocket(eventSocketUrl())
  socket.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data as string) as ArenaEvent)
    } catch {
      onError?.()
    }
  }
  socket.onerror = () => onError?.()
  return () => socket.close()
}
