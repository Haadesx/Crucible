import type { HarnessPatchRecord, MatrixVersion, RunMatrix } from '../../types'
import type { RunBundle } from '../../lib/viewmodel'
import { fixed, pct } from '../../lib/viewmodel'

interface VersionInspectorProps {
  version: MatrixVersion | null
  matrix: RunMatrix
  bundle: RunBundle
}

function shortId(id: string): string {
  const parts = id.split('-')
  return parts.length > 2 ? `…${parts.slice(-2).join('-')}` : id
}

export function VersionInspector({ version, matrix, bundle }: VersionInspectorProps) {
  if (!version) {
    return <p className="versions-empty mono">click a version header or the matrix to inspect its patch and decision</p>
  }
  const patch: HarnessPatchRecord | undefined = version.patch_id
    ? bundle.patches.find((item) => item.id === version.patch_id)
    : undefined
  const slices = patch?.metrics?.slices ?? {}
  return (
    <div className="version-inspector">
      <div className="version-head">
        <span className="version-label-lg">{version.label}</span>
        <span className={`version-status mono ${version.status === 'PROMOTED' ? 'text-green' : 'text-slate'}`}>
          {version.status}
        </span>
      </div>
      <dl className="inspector-kv mono">
        <dt>harness</dt>
        <dd title={version.harness_id}>{shortId(version.harness_id)}</dd>
        <dt>parent</dt>
        <dd title={version.parent_id ?? ''}>{version.parent_id ? shortId(version.parent_id) : 'seed'}</dd>
        <dt>generation</dt>
        <dd>G{String(version.generation).padStart(2, '0')}</dd>
        <dt>engineer</dt>
        <dd>{version.engineer_model ?? (version.status === 'BASELINE' ? 'seed harness' : '—')}</dd>
        <dt>fitness</dt>
        <dd>{fixed(version.fitness)}</dd>
        <dt>block rate</dt>
        <dd>{pct(version.block_rate)}</dd>
        <dt>utility</dt>
        <dd>{pct(version.utility_rate)}</dd>
      </dl>
      {patch ? (
        <>
          <section className="inspector-section">
            <h4>HARNESS PATCH · {patch.id}</h4>
            <ul className="inspector-list mono">
              {patch.patch.operations.map((operation, index) => (
                <li key={`${operation.op}-${index}`}>
                  <span className="text-violet">{operation.op}</span> {operation.target}
                  {operation.reason ? ` · ${operation.reason.slice(0, 80)}` : ''}
                </li>
              ))}
            </ul>
          </section>
          <section className="inspector-section">
            <h4>REPLAY SLICES</h4>
            {Object.keys(slices).length > 0 ? (
              <table className="inspector-slices mono">
                <thead>
                  <tr>
                    <th>slice</th>
                    <th>eps</th>
                    <th>security</th>
                    <th>utility</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(slices).map(([name, slice]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{slice.episodes}</td>
                      <td className={slice.security < 1 ? 'text-red' : 'text-green'}>{pct(slice.security)}</td>
                      <td className={slice.utility < 0.5 ? 'text-amber' : 'text-green'}>{pct(slice.utility)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="inspector-note mono">no replay slices persisted</p>
            )}
          </section>
          <section className="inspector-section">
            <h4>DECISION</h4>
            <p className="inspector-note">{patch.transitions[patch.transitions.length - 1]?.detail || patch.rejection_reason || 'pending'}</p>
          </section>
        </>
      ) : (
        <p className="inspector-note mono">
          {version.status === 'BASELINE' ? 'seed harness — no patch authored' : 'patch record not in this snapshot'}
        </p>
      )}
      {matrix.rejected.length > 0 && (
        <section className="inspector-section">
          <h4>REJECTED CANDIDATES · {matrix.rejected.length}</h4>
          <ul className="inspector-list">
            {matrix.rejected.map((rejected) => (
              <li key={rejected.harness_id}>
                <span className="mono text-amber">{rejected.patch_id}</span>
                <span className="rejected-reason">{rejected.reason || 'rejected'}</span>
                <span className="mono muted">
                  fit {fixed(rejected.fitness)} · util {pct(rejected.utility_rate)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
