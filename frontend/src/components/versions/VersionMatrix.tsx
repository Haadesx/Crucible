import { Fragment } from 'react'

import type { MatrixCell, MatrixTest, MatrixVersion, RunMatrix } from '../../types'

interface VersionMatrixProps {
  matrix: RunMatrix
  selectedCell: MatrixCell | null
  selectedVersion: string | null
  onSelectCell: (cell: MatrixCell, test: MatrixTest) => void
  onSelectVersion: (version: MatrixVersion) => void
}

const GROUPS: Array<{ kind: 'adversarial' | 'benign'; title: string; hint: string }> = [
  { kind: 'adversarial', title: 'ADVERSARIAL', hint: 'malicious tests · should be blocked' },
  { kind: 'benign', title: 'BENIGN', hint: 'legitimate tasks · should still work' },
]

export function outcomeLabel(outcome: string): string {
  switch (outcome) {
    case 'BREACH':
      return 'BREACH'
    case 'BLOCKED':
      return 'BLOCKED'
    case 'BENIGN_PASS':
      return 'PASS'
    case 'FALSE_POSITIVE':
      return 'FALSE POS'
    case 'TASK_FAILED':
      return 'TASK FAILED'
    default:
      return outcome
  }
}

export function VersionMatrix({
  matrix,
  selectedCell,
  selectedVersion,
  onSelectCell,
  onSelectVersion,
}: VersionMatrixProps) {
  const cellIndex = new Map(matrix.cells.map((cell) => [`${cell.version}|${cell.test_key}`, cell]))
  return (
    <div className="matrix-wrap">
      <table className="matrix">
        <thead>
          <tr>
            <th className="matrix-corner">TEST</th>
            {matrix.versions.map((version) => (
              <th key={version.label} className={selectedVersion === version.label ? 'is-selected' : ''}>
                <button type="button" className="matrix-version-head" onClick={() => onSelectVersion(version)}>
                  <span className="version-label">{version.label}</span>
                  <span className="version-sub mono">
                    {version.status === 'BASELINE' ? 'baseline' : `G${String(version.generation).padStart(2, '0')}`}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {GROUPS.map((group) => {
            const tests = matrix.tests.filter((test) => test.kind === group.kind)
            if (tests.length === 0) return null
            return (
              <Fragment key={group.kind}>
                <tr className="matrix-group">
                  <th colSpan={matrix.versions.length + 1}>
                    <span className={`matrix-group-title group-${group.kind}`}>{group.title}</span>
                    <span className="matrix-group-hint">{group.hint}</span>
                  </th>
                </tr>
                {tests.map((test) => (
                  <tr key={test.key}>
                    <th className="matrix-test" title={`${test.scenario_id} · ${test.attack_id}`}>
                      <span className="matrix-test-label">{test.label}</span>
                      <span className="matrix-test-meta mono">{test.family ?? test.slice}</span>
                    </th>
                    {matrix.versions.map((version) => {
                      const cell = cellIndex.get(`${version.label}|${test.key}`)
                      const isSelected =
                        cell !== undefined &&
                        selectedCell?.version === cell.version &&
                        selectedCell?.test_key === cell.test_key
                      return (
                        <td key={version.label}>
                          <button
                            type="button"
                            className={`matrix-cell ${cell ? `outcome-${cell.outcome.toLowerCase()}` : 'outcome-missing'} ${
                              isSelected ? 'is-selected' : ''
                            }`}
                            title={cell ? `${outcomeLabel(cell.outcome)} · ${cell.reason}` : 'not run'}
                            onClick={() => cell && onSelectCell(cell, test)}
                            disabled={!cell}
                          >
                            {cell ? outcomeLabel(cell.outcome) : 'not run'}
                          </button>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export const OUTCOME_LEGEND: Array<{ outcome: string; text: string }> = [
  { outcome: 'BREACH', text: 'malicious test succeeded' },
  { outcome: 'BLOCKED', text: 'malicious test correctly blocked' },
  { outcome: 'BENIGN_PASS', text: 'legitimate task still worked' },
  { outcome: 'FALSE_POSITIVE', text: 'legitimate task wrongly blocked' },
  { outcome: 'TASK_FAILED', text: 'model did not do the task — not a false positive' },
]
