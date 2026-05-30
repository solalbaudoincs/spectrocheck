import type { Verdict } from '../api'
import { VerdictBadge } from './VerdictBadge'

const ORDER: Verdict[] = ['TRANSCODE', 'LOSSY SOURCE', 'SUSPECT', 'OK', 'ERROR']

export function FilterChips({
  counts,
  active,
  onToggle,
}: {
  counts: Record<string, number>
  active: Set<Verdict>
  onToggle: (v: Verdict) => void
}) {
  const present = ORDER.filter((v) => counts[v])
  if (!present.length) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {present.map((v) => {
        const on = active.size === 0 || active.has(v)
        return (
          <button
            key={v}
            onClick={() => onToggle(v)}
            title={`Show only ${v}`}
            className={`flex items-center gap-1.5 rounded-md border px-2 py-1 transition ${
              on ? 'border-line bg-panel' : 'border-transparent opacity-40 hover:opacity-80'
            }`}
          >
            <VerdictBadge verdict={v} />
            <span className="text-xs tabular-nums text-body">{counts[v]}</span>
          </button>
        )
      })}
    </div>
  )
}
