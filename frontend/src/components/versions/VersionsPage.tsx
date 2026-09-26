import { useMemo, useState, type ReactNode } from 'react'

import type { ArenaEvent, MatrixCell, MatrixTest, MatrixVersion, RunMatrix } from '../../types'
import type { RunBundle, TimelineItem } from '../../lib/viewmodel'
import { memoryRecall } from '../../lib/viewmodel'
import { CellInspector } from './CellInspector'
import { TrendChart } from './TrendChart'
import { GenerationChart } from './GenerationChart'
import { VersionInspector } from './VersionInspector'
import { OUTCOME_LEGEND, VersionMatrix } from './VersionMatrix'

interface VersionsPageProps {
  matrix: RunMatrix | null
  bundle: RunBundle
  events: ArenaEvent[]
  timeline: TimelineItem[]
  generation: number
}

/**
 * Native floating-window chrome: the same rt-* markup RuntimeWindow renders on the
 * Execution Trace canvas, so the matrix view reads as another workspace surface rather
 * than a dashboard page. No new design system, no new tokens.
 */
function VersionWindow({
  title,
  tone,
  state,
  badge,
  bodyClass,
  children,
}: {
  title: string
  tone: string
  state: string
  badge?: string
  bodyClass?: string
  children: ReactNode
}) {
  return (
    <section className={`rt-window tone-${tone} state-${state} versions-window`}>
      <header className="rt-titlebar">
        <span className={`rt-dot state-${state}`} />
        <span className="rt-title">{title}</span>
        {badge && <span className="rt-badge mono" title={badge}>{badge}</span>}
        <span className="rt-grow" />
        <span className={`rt-state mono state-${state}`}>{state.toUpperCase()}</span>
      </header>
      <div className={`rt-body versions-window-body ${bodyClass ?? ''}`}>{children}</div>
    </section>
  )
}

function cellTone(outcome: string): string {
  switch (outcome) {
    case 'BREACH':
      return 'red'
    case 'BLOCKED':
      return 'blue'
    case 'BENIGN_PASS':
      return 'green'
    case 'TASK_FAILED':
      return 'amber'
    default:
      return 'slate'
  }
}

// Wall-clock span of the persisted generation records (first to last), e.g. "2h42m".
function runSpan(generations: { created_at: string }[]): string | null {
  const times = generations.map((item) => Date.parse(item.created_at)).filter((value) => !Number.isNaN(value))
  if (times.length < 2) return null
  const minutes = Math.round((Math.max(...times) - Math.min(...times)) / 60_000)
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}m` : `${minutes}m`
}

export function VersionsPage({ matrix, bundle, events: liveEvents, timeline, generation }: VersionsPageProps) {
  // Live WebSocket events plus the run's persisted recalls, de-duplicated by id.
  const events = useMemo(() => {
    const key = (event: ArenaEvent) => `${event.type}|${event.run_id}|${event.generation}|${event.created_at}`
    const seen = new Set(liveEvents.map(key))
    return [...liveEvents, ...(matrix?.memory_events ?? []).filter((event) => !seen.has(key(event)))]
  }, [liveEvents, matrix])
  const [selectedCell, setSelectedCell] = useState<MatrixCell | null>(null)
  const [selectedTest, setSelectedTest] = useState<MatrixTest | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<MatrixVersion | null>(null)
  // The panel shows the run's latest real recall: a live memory_retrieved event wins,
  // otherwise persisted patch provenance, otherwise the selected generation's empty state.
  let recall = memoryRecall(bundle, events, generation)
  for (const id of new Set([...bundle.generations.map((item) => item.id), generation])) {
    const candidate = memoryRecall(bundle, events, id)
    if (candidate.origin === 'live' && candidate.count > 0) {
      recall = candidate
      break
    }
    if (recall.origin === 'none' && candidate.origin !== 'none') recall = candidate
  }

  const recallNote =
    recall.origin === 'none' || recall.count === 0
      ? 'no relevant prior failures recalled'
      : `${recall.count} recalled${recall.backend ? ` · ${recall.backend}` : ''}`

  if (!matrix) {
    return (
      <div className="versions-page">
        <VersionWindow title="VERSION × TEST MATRIX" tone="amber" state="waiting" badge="/matrix unavailable">
          <div className="versions-unavailable">
            <strong>MATRIX UNAVAILABLE</strong>
            <span className="mono">GET /runs/&lt;run&gt;/matrix returned no payload — the endpoint is not deployed here.</span>
          </div>
        </VersionWindow>
        <div className="versions-bottom">
          <VersionWindow title="ATLAS MEMORY" tone="cyan" state="idle" badge={recallNote}>
            <MemoryRows entries={recall.entries} origin={recall.origin} />
          </VersionWindow>
          <VersionWindow title="LIVE EVENT FEED" tone="slate" state="idle">
            <EventRows timeline={timeline} />
          </VersionWindow>
        </div>
      </div>
    )
  }

  return (
    <div className="versions-page">
      <div className="matrix-legend">
        {OUTCOME_LEGEND.map((item) => (
          <span className="legend-item" key={item.outcome}>
            <i className={`legend-swatch outcome-${item.outcome.toLowerCase()}`} />
            <b className="mono">{item.outcome.replace('_', ' ')}</b>
            <span className="legend-text">{item.text}</span>
          </span>
        ))}
      </div>
      <div className="versions-grid">
        <div className="versions-main">
          {bundle.generations.length >= 3 ? (
            <VersionWindow
              title="RED × BLUE ACROSS GENERATIONS"
              tone="violet"
              state="idle"
              badge={`long-horizon run · ${bundle.generations.length} generations${runSpan(bundle.generations) ? ` · ${runSpan(bundle.generations)} wall clock` : ''}`}
              bodyClass="versions-body-trend"
            >
              <GenerationChart generations={bundle.generations} redVersions={bundle.redVersions} />
            </VersionWindow>
          ) : null}
          <VersionWindow
            title="VERSION × TEST MATRIX"
            tone="cyan"
            state={selectedCell ? 'running' : 'idle'}
            badge={`${matrix.versions.length} versions · ${matrix.tests.length} tests`}
            bodyClass="versions-body-matrix"
          >
            <VersionMatrix
              matrix={matrix}
              selectedCell={selectedCell}
              selectedVersion={selectedVersion?.label ?? null}
              onSelectCell={(cell, test) => {
                setSelectedCell(cell)
                setSelectedTest(test)
              }}
              onSelectVersion={setSelectedVersion}
            />
          </VersionWindow>
          <VersionWindow
            title="TREND ACROSS PROMOTED VERSIONS"
            tone="violet"
            state="idle"
            badge={`${matrix.trend.length} versions`}
            bodyClass="versions-body-trend"
          >
            <TrendChart trend={matrix.trend} />
          </VersionWindow>
        </div>
        <aside className="versions-side">
          <VersionWindow
            title="HARNESS VERSION"
            tone="violet"
            state={selectedVersion ? 'success' : 'idle'}
            badge={selectedVersion?.label ?? 'none selected'}
            bodyClass="versions-body-side"
          >
            <VersionInspector version={selectedVersion} matrix={matrix} bundle={bundle} />
          </VersionWindow>
          <VersionWindow
            title="CELL EVIDENCE"
            tone={selectedCell ? cellTone(selectedCell.outcome) : 'slate'}
            state={selectedCell ? 'success' : 'idle'}
            badge={selectedTest?.label ?? 'no cell selected'}
            bodyClass="versions-body-side"
          >
            <CellInspector cell={selectedCell} test={selectedTest} bundle={bundle} />
          </VersionWindow>
        </aside>
      </div>
      <div className="versions-bottom">
        <VersionWindow
          title="ATLAS MEMORY"
          tone="cyan"
          state={recall.entries.length > 0 ? 'success' : 'idle'}
          badge={recallNote}
          bodyClass="versions-body-bottom"
        >
          <MemoryRows entries={recall.entries} origin={recall.origin} />
        </VersionWindow>
        <VersionWindow
          title="LIVE EVENT FEED"
          tone="slate"
          state="idle"
          badge={`${timeline.length} events`}
          bodyClass="versions-body-bottom"
        >
          <EventRows timeline={timeline} />
        </VersionWindow>
      </div>
    </div>
  )
}

function MemoryRows({ entries, origin }: { entries: ReturnType<typeof memoryRecall>['entries']; origin: string }) {
  if (entries.length === 0) {
    return (
      <p className="versions-empty mono">
        {origin === 'patch' ? 'persisted patch provenance only' : 'no relevant prior failures recalled'}
      </p>
    )
  }
  return (
    <div className="memory-rows">
      {entries.map((entry) => (
        <div className="memory-row" key={`${entry.origin}-${entry.memoryId}`}>
          <div className="memory-row-head">
            <span className="mono memory-id" title={entry.memoryId}>
              {entry.memoryId.length > 30 ? `${entry.memoryId.slice(0, 30)}…` : entry.memoryId}
            </span>
            <span className="mono memory-sim">
              {entry.similarity === null ? 'similarity —' : `sim ${entry.similarity.toFixed(2)}`}
            </span>
          </div>
          <div className="memory-row-meta mono">
            <span>{entry.attackFamily ?? 'family —'}</span>
            <span>
              {entry.runId ? `${entry.runId.slice(0, 20)}…` : 'run —'}
              {entry.generation !== null ? ` · G${String(entry.generation).padStart(2, '0')}` : ''}
            </span>
            <span>{entry.patchId ? `patch ${entry.patchId}` : 'patch —'}</span>
            <span className={entry.outcome === 'PROMOTED' ? 'text-green' : entry.outcome === 'REJECTED' ? 'text-amber' : ''}>
              {entry.outcome ?? 'outcome —'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function EventRows({ timeline }: { timeline: TimelineItem[] }) {
  const recent = timeline.slice(-30)
  if (recent.length === 0) return <p className="versions-empty mono">no events for this run yet</p>
  return (
    <div className="event-rows">
      {recent.map((item) => (
        <div className="event-row is-static" key={item.id}>
          <span className="event-time mono">{item.ts.slice(11, 19)}</span>
          <span className={`event-dot tone-${item.tone}`} />
          <span className="event-text">{item.text}</span>
          <span className="event-detail mono">{item.detail}</span>
        </div>
      ))}
    </div>
  )
}
