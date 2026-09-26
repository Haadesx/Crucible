import type { MatrixTrendPoint } from '../../types'

interface TrendChartProps {
  trend: MatrixTrendPoint[]
}

const W = 760
const H = 160
const PAD = 34

export function TrendChart({ trend }: TrendChartProps) {
  if (trend.length === 0) {
    return <p className="versions-empty mono">no trend data recorded for this run</p>
  }
  const x = (index: number) => PAD + (index * (W - PAD * 2)) / Math.max(1, trend.length - 1)
  const y = (value: number) => H - PAD - value * (H - PAD * 2)
  const line = (get: (point: MatrixTrendPoint) => number) =>
    trend.map((point, index) => `${x(index)},${y(get(point))}`).join(' ')
  return (
    <div className="trend-wrap">
      <svg className="trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Version trends">
        {[0, 0.5, 1].map((value) => (
          <g key={value}>
            <line x1={PAD} x2={W - PAD} y1={y(value)} y2={y(value)} className="trend-grid" />
            <text x={4} y={y(value) + 3} className="trend-axis">
              {Math.round(value * 100)}%
            </text>
          </g>
        ))}
        <polyline points={line((point) => point.block_rate)} className="trend-line trend-block" />
        <polyline points={line((point) => point.benign_success)} className="trend-line trend-benign" />
        <polyline points={line((point) => point.asr)} className="trend-line trend-asr" />
        {trend.map((point, index) => (
          <g key={point.version}>
            <circle cx={x(index)} cy={y(point.block_rate)} r="3" className="trend-dot trend-block" />
            <circle cx={x(index)} cy={y(point.benign_success)} r="3" className="trend-dot trend-benign" />
            <circle cx={x(index)} cy={y(point.asr)} r="3" className="trend-dot trend-asr" />
            <text x={x(index)} y={H - 8} className="trend-axis">
              {point.version}
            </text>
          </g>
        ))}
      </svg>
      <div className="trend-legend mono">
        <span className="trend-key trend-block">security block rate</span>
        <span className="trend-key trend-benign">benign task success</span>
        <span className="trend-key trend-asr">attack success rate</span>
      </div>
    </div>
  )
}
