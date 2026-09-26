import type { Generation, RedAgentVersion } from '../../types'

interface GenerationChartProps {
  generations: Generation[]
  redVersions: RedAgentVersion[]
}

const W = 760
const H = 200
const PAD = 34

/**
 * Red vs Blue across generations, straight from persisted generation records:
 * attack success rate, benign utility, Red mean fitness and Blue champion fitness,
 * with markers where the Blue champion changed and counts of Red mutations the
 * selection promoted/rejected in that generation. Nothing is interpolated.
 */
export function GenerationChart({ generations, redVersions }: GenerationChartProps) {
  const rows = [...generations].sort((a, b) => a.id - b.id)
  if (rows.length < 2) {
    return <p className="versions-empty mono">fewer than two generations recorded for this run</p>
  }
  const x = (index: number) => PAD + (index * (W - PAD * 2)) / Math.max(1, rows.length - 1)
  const y = (value: number) => H - PAD - Math.max(0, Math.min(1, value)) * (H - PAD * 2 - 14)
  const line = (get: (row: Generation) => number) => rows.map((row, index) => `${x(index)},${y(get(row))}`).join(' ')
  const redByGen = (generation: number, status: string) =>
    redVersions.filter((version) => version.generation === generation && version.status === status).length
  return (
    <div className="trend-wrap">
      <svg className="trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Red and Blue across generations">
        {[0, 0.5, 1].map((value) => (
          <g key={value}>
            <line x1={PAD} x2={W - PAD} y1={y(value)} y2={y(value)} className="trend-grid" />
            <text x={4} y={y(value) + 3} className="trend-axis">
              {Math.round(value * 100)}%
            </text>
          </g>
        ))}
        {rows.map((row, index) =>
          index > 0 && row.blue_champion !== rows[index - 1].blue_champion ? (
            <g key={`p-${row.id}`}>
              <line x1={x(index)} x2={x(index)} y1={y(1)} y2={y(0)} className="trend-grid" strokeDasharray="3 3" />
              <text x={x(index) + 3} y={y(1) - 4} className="trend-axis">
                BLUE PATCH PROMOTED
              </text>
            </g>
          ) : null,
        )}
        <polyline points={line((row) => row.blue_mean_fitness)} className="trend-line trend-block" />
        <polyline points={line((row) => row.utility_rate)} className="trend-line trend-benign" />
        <polyline points={line((row) => row.red_mean_fitness)} className="trend-line trend-redfit" strokeDasharray="4 3" />
        <polyline points={line((row) => row.attack_success_rate)} className="trend-line trend-asr" />
        {rows.map((row, index) => {
          const promoted = redByGen(row.id, 'PROMOTED')
          const rejected = redByGen(row.id, 'REJECTED')
          return (
            <g key={row.id}>
              <circle cx={x(index)} cy={y(row.attack_success_rate)} r="3" className="trend-dot trend-asr" />
              <circle cx={x(index)} cy={y(row.utility_rate)} r="3" className="trend-dot trend-benign" />
              <circle cx={x(index)} cy={y(row.blue_mean_fitness)} r="3" className="trend-dot trend-block" />
              <text x={x(index) - 8} y={H - 18} className="trend-axis">
                G{String(row.id).padStart(2, '0')}
              </text>
              <text x={x(index) - 14} y={H - 6} className="trend-axis">
                red +{promoted} / −{rejected}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="trend-legend mono">
        <span className="trend-key trend-asr">attack success rate</span>
        <span className="trend-key trend-benign">benign utility</span>
        <span className="trend-key trend-redfit">red mean fitness</span>
        <span className="trend-key trend-block">blue champion fitness</span>
        <span>red +promoted / −rejected mutations</span>
      </div>
    </div>
  )
}
