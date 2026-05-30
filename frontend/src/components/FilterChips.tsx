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
            className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 transition ${
              on
                ? 'border-slate-700 bg-slate-800/60'
                : 'border-transparent opacity-40 hover:opacity-80'
            }`}
          >
            <VerdictBadge verdict={v} />
            <span className="mono text-xs tabular-nums text-slate-300">{counts[v]}</span>
          </button>
        )
      })}
    </div>
  )
}
