import type { ArenaEvent } from '../../types'
import { championForGeneration, championOf, memoryRecall, pct, type RunBundle } from '../../lib/viewmodel'

interface MetricsHudProps {
  bundle: RunBundle
  generation: number
  events: ArenaEvent[]
}

function shortId(id: string): string {
  const parts = id.split('-')
  return parts.length > 2 ? parts.slice(-2).join('-') : id
}

/** Slim, non-interactive strip over the canvas: only values persisted or streamed by the run. */
export function MetricsHud({ bundle, generation, events }: MetricsHudProps) {
  const record = bundle.generations.find((item) => item.id === generation)
  const redChampion =
    record?.red_agent_champion ||
    bundle.redVersions
      .filter((version) => version.generation === generation)
      .sort((a, b) => (b.fitness ?? 0) - (a.fitness ?? 0))[0]?.id ||
    ''
  const blueChampion = championForGeneration(bundle, generation + 1) ?? championOf(bundle)
  const recall = memoryRecall(bundle, events, generation)
  // Memory recalls are event-driven for the HUD; the patch-provenance fallback belongs to
  // the ATLAS MEMORY window, not to this live counter.
  const memory = recall.origin === 'live' ? String(recall.count) : '—'
  return (
    <div className="metrics-hud" aria-label="Run metrics">
      <span className="metrics-gen mono">G{String(generation).padStart(2, '0')}</span>
      <HudItem label="ASR" value={pct(record?.attack_success_rate)} />
      <HudItem label="BENIGN" value={pct(record?.utility_rate)} />
      <HudItem label="RED CHAMPION" value={redChampion ? shortId(redChampion) : '—'} title={redChampion} />
      <HudItem
        label="BLUE CHAMPION"
        value={blueChampion ? shortId(blueChampion.version.id) : '—'}
        title={blueChampion?.version.id}
      />
      <HudItem label="MEMORY" value={memory} title={recall.origin === 'live' ? (recall.backend ?? undefined) : 'no memory_retrieved event for this generation'} />
    </div>
  )
}

function HudItem({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span className="metrics-item" title={title}>
      <b>{label}</b>
      <i>{value}</i>
    </span>
  )
}
