import { Handle, NodeResizer, Position, type Node, type NodeProps } from '@xyflow/react'

import type { WindowSpec } from '../../lib/viewmodel'
import type { NodeRef } from '../../lib/viewmodel'
import { WindowContent, type WindowContentProps } from './WindowContent'

export interface RuntimeNodeData extends WindowContentProps {
  onOpen?: (spec: WindowSpec) => void
  onResize?: (id: string, width: number, height: number) => void
  onFollowRef?: (ref: NodeRef) => void
  dimmed?: boolean
  [key: string]: unknown
}

export type RuntimeNode = Node<RuntimeNodeData, 'runtime'>

export function RuntimeWindow({ data, selected }: NodeProps<RuntimeNode>) {
  const { spec } = data
  return (
    <div
      className={`rt-window tone-${spec.tone} state-${spec.state} kind-${spec.kind} ${selected ? 'is-selected' : ''} ${data.dimmed ? 'is-dimmed' : ''}`}
    >
      <Handle id="t" type="target" position={Position.Top} className="rt-handle" />
      <Handle id="b" type="source" position={Position.Bottom} className="rt-handle" />
      <Handle id="l" type="target" position={Position.Left} className="rt-handle" />
      <Handle id="r" type="source" position={Position.Right} className="rt-handle" />
      {spec.kind !== 'generation' && (
        <NodeResizer
          isVisible={selected}
          minWidth={220}
          minHeight={110}
          lineClassName="rt-resize-line"
          handleClassName="rt-resize-handle"
          onResizeEnd={(_event, params) => data.onResize?.(spec.id, params.width, params.height)}
        />
      )}
      <header className="rt-titlebar">
        <span className={`rt-dot state-${spec.state}`} />
        <span className="rt-title" title={`${spec.title} · ${spec.subtitle}`}>{spec.title}</span>
        {spec.badges[0] && <span className="rt-badge mono" title={spec.badges.join(' · ')}>{spec.badges[0]}</span>}
        <span className="rt-grow" />
        <span className={`rt-state mono state-${spec.state}`}>{stateText(spec.state)}</span>
        {spec.kind !== 'generation' && (
          <button
            type="button"
            className="rt-open nodrag"
            title="Inspect evidence"
            onClick={(event) => {
              event.stopPropagation()
              data.onOpen?.(spec)
            }}
          >
            ⋯
          </button>
        )}
      </header>
      <div className="rt-body nodrag nowheel">
        <WindowContent {...data} />
      </div>
    </div>
  )
}

function stateText(state: WindowSpec['state']): string {
  switch (state) {
    case 'running':
      return 'RUNNING'
    case 'waiting':
      return 'WAITING'
    case 'success':
      return 'OK'
    case 'failed':
      return 'FAILED'
    case 'blocked':
      return 'BLOCKED'
    default:
      return 'IDLE'
  }
}
