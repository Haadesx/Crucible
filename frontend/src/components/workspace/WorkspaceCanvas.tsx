import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type NodeChange,
  type NodeTypes,
  type OnNodesChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { ArenaEvent, RunSummary } from '../../types'
import type { NodeRef, RunBundle, TimelineItem, WindowSpec, WorkspaceGraph } from '../../lib/viewmodel'
import type { UiMode } from '../../hooks/useRunData'
import { RuntimeWindow, type RuntimeNode, type RuntimeNodeData } from './RuntimeWindow'
import type { NodeTone } from '../../lib/viewmodel'

export interface WorkspaceApi {
  focus: (nodeId: string, zoom?: number) => void
  fit: () => void
}

interface WorkspaceCanvasProps {
  graph: WorkspaceGraph
  bundle: RunBundle
  events: ArenaEvent[]
  runs: RunSummary[]
  timeline: TimelineItem[]
  mode: UiMode
  selectedId: string | null
  storageKey: string
  initialFocusId?: string | null
  onSelect: (spec: WindowSpec | null) => void
  onFollow: (ref: NodeRef) => void
  onLoadRun: (runId: string) => void
  onGenerationFocus?: (generation: number) => void
  apiRef: React.MutableRefObject<WorkspaceApi | null>
}

const TONE_COLOR: Record<NodeTone, string> = {
  red: '#ff4d6d',
  blue: '#4d7cff',
  green: '#43d992',
  amber: '#f0b657',
  cyan: '#4fd6ee',
  violet: '#a78bfa',
  gold: '#f5c451',
  slate: '#5c6b85',
}

interface Override {
  x?: number
  y?: number
  w?: number
  h?: number
}

const nodeTypes: NodeTypes = { runtime: RuntimeWindow }

function loadOverrides(key: string): Record<string, Override> {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as Record<string, Override>) : {}
  } catch {
    return {}
  }
}

export function WorkspaceCanvas(props: WorkspaceCanvasProps) {
  return (
    <ReactFlowProvider>
      <WorkspaceFlow {...props} />
    </ReactFlowProvider>
  )
}

function WorkspaceFlow({
  graph,
  bundle,
  events,
  runs,
  timeline,
  mode,
  selectedId,
  storageKey,
  initialFocusId,
  onSelect,
  onFollow,
  onLoadRun,
  onGenerationFocus,
  apiRef,
}: WorkspaceCanvasProps) {
  const { fitView, fitBounds, setCenter, zoomIn, zoomOut } = useReactFlow()
  const [overrides, setOverrides] = useState<Record<string, Override>>(() => loadOverrides(storageKey))
  const [zoom, setZoom] = useState(1)
  const [handMode, setHandMode] = useState(true)
  const fitted = useRef<string>('')
  const saveTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    setOverrides(loadOverrides(storageKey))
  }, [storageKey])

  useEffect(() => {
    window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(overrides))
      } catch {
        /* storage may be unavailable; layout persistence is best-effort */
      }
    }, 400)
    return () => window.clearTimeout(saveTimer.current)
  }, [overrides, storageKey])

  const specsById = useMemo(() => new Map(graph.windows.map((spec) => [spec.id, spec])), [graph.windows])

  const setOverride = useCallback((id: string, patch: Override) => {
    setOverrides((current) => ({ ...current, [id]: { ...current[id], ...patch } }))
  }, [])

  const nodes = useMemo<RuntimeNode[]>(
    () =>
      graph.windows.map((spec) => {
        const override = overrides[spec.id] ?? {}
        const data: RuntimeNodeData = {
          spec,
          bundle,
          events,
          runs,
          timeline,
          mode,
          onFollow,
          onOpen: (selected) => onSelect(selected),
          onResize: (id, width, height) => setOverride(id, { w: width, h: height }),
        }
        return {
          id: spec.id,
          type: 'runtime',
          position: { x: override.x ?? spec.x, y: override.y ?? spec.y },
          style: { width: override.w ?? spec.w, height: override.h ?? spec.h },
          data,
          selected: spec.id === selectedId,
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
          draggable: spec.kind !== 'generation',
        }
      }),
    [graph.windows, overrides, bundle, events, runs, timeline, mode, onSelect, onFollow, setOverride, selectedId],
  )

  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle ?? 'b',
        targetHandle: edge.targetHandle ?? 't',
        label: edge.label,
        type: 'smoothstep',
        animated: edge.state === 'running',
        className: `rt-edge edge-tone-${edge.tone} edge-state-${edge.state}`,
        markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13, color: TONE_COLOR[edge.tone] },
        labelStyle: { fill: '#8ea0bd', fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.04em' },
        labelBgStyle: { fill: 'rgba(6, 10, 18, 0.86)' },
        labelBgPadding: [5, 2] as [number, number],
        labelBgBorderRadius: 3,
        zIndex: edge.state === 'running' ? 4 : 1,
      })),
    [graph.edges],
  )

  const onNodesChange = useCallback(
    (changes: NodeChange<RuntimeNode>[]) => {
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          setOverride(change.id, { x: change.position.x, y: change.position.y })
        } else if (change.type === 'dimensions' && change.dimensions) {
          setOverrides((current) => {
            if (!current[change.id] && !change.resizing) return current
            return {
              ...current,
              [change.id]: { ...current[change.id], w: change.dimensions?.width, h: change.dimensions?.height },
            }
          })
        }
      }
    },
    [setOverride],
  )

  const initialFocusRef = useRef(initialFocusId)
  initialFocusRef.current = initialFocusId

  useEffect(() => {
    if (graph.windows.length === 0) return
    const key = `${storageKey}:${graph.windows.length}`
    if (fitted.current === key) return
    const target = initialFocusRef.current
    if (target && !graph.windows.some((spec) => spec.id === target)) return
    fitted.current = key
    const timer = window.setTimeout(() => {
      const spec = target ? graph.windows.find((item) => item.id === target) : undefined
      if (spec) {
        // setCenter needs no measurement, so the first paint lands on the selected
        // generation's Red window instead of falling back to fit-all.
        void setCenter(spec.x + spec.w / 2, spec.y + spec.h, { zoom: 0.82, duration: 500 })
      } else if (graph.windows.length > 0) {
        // fitBounds takes a flow-coordinate rectangle, so it is exact before nodes
        // have been measured (the reason a fitView fallback stayed at 100%).
        const bounds = graph.windows.reduce(
          (box, item) => ({
            minX: Math.min(box.minX, item.x),
            minY: Math.min(box.minY, item.y),
            maxX: Math.max(box.maxX, item.x + item.w),
            maxY: Math.max(box.maxY, item.y + item.h),
          }),
          { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
        )
        void fitBounds(
          { x: bounds.minX, y: bounds.minY, width: bounds.maxX - bounds.minX, height: bounds.maxY - bounds.minY },
          { padding: 0.08, duration: 500 },
        )
      }
    }, 60)
    return () => window.clearTimeout(timer)
  }, [graph.windows, storageKey, fitView, fitBounds, setCenter])

  useEffect(() => {
    apiRef.current = {
      focus: (nodeId, maxZoom = 1.05) => {
        void fitView({ nodes: [{ id: nodeId }], padding: 0.6, maxZoom, duration: 450 })
      },
      fit: () => {
        void fitView({ padding: 0.18, maxZoom: 0.72, duration: 450 })
      },
    }
    return () => {
      apiRef.current = null
    }
  }, [apiRef, fitView])

  return (
    <div className="workspace-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onMove={(_event, viewport) => setZoom(viewport.zoom)}
        onNodeClick={(_event, node) => {
          const spec = specsById.get(node.id)
          if (!spec) return
          if (spec.kind === 'run') {
            onLoadRun(spec.ref.id)
            return
          }
          if (spec.kind === 'generation') {
            onGenerationFocus?.(spec.generation)
            return
          }
          onSelect(spec)
        }}
        onPaneClick={() => onSelect(null)}
        minZoom={0.04}
        maxZoom={1.7}
        panOnDrag={handMode}
        selectionOnDrag={!handMode}
        panOnScroll
        zoomOnDoubleClick={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={26} size={1.1} color="rgba(122, 145, 184, 0.16)" />
        <Panel position="bottom-right" className="canvas-controls">
          <button
            type="button"
            className={handMode ? 'is-active' : ''}
            title="Pan mode"
            onClick={() => setHandMode(true)}
          >
            ✋
          </button>
          <button
            type="button"
            className={!handMode ? 'is-active' : ''}
            title="Select mode"
            onClick={() => setHandMode(false)}
          >
            ⬚
          </button>
          <button type="button" title="Fit view" onClick={() => void fitView({ padding: 0.18, maxZoom: 0.72, duration: 450 })}>
            FIT
          </button>
          <button type="button" title="Reset layout" onClick={() => { setOverrides({}); window.setTimeout(() => void fitView({ padding: 0.18, maxZoom: 0.72, duration: 450 }), 60) }}>
            ↺
          </button>
          <span className="canvas-controls-divider" />
          <button type="button" title="Zoom out" onClick={() => void zoomOut({ duration: 200 })}>
            −
          </button>
          <span className="canvas-zoom mono">{Math.round(zoom * 100)}%</span>
          <button type="button" title="Zoom in" onClick={() => void zoomIn({ duration: 200 })}>
            +
          </button>
        </Panel>
      </ReactFlow>
    </div>
  )
}
