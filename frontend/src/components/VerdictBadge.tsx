import type { Verdict } from '../api'

// Verdict colours are *status* signals (not the brand accent), kept consistent
// everywhere a verdict appears: badge, chip, detail header.
const STYLES: Record<Verdict, { box: string; text: string; dot: string }> = {
  OK: { box: 'bg-emerald-500/10 ring-emerald-500/30', text: 'text-emerald-300', dot: 'bg-emerald-400' },
  SUSPECT: { box: 'bg-amber-500/10 ring-amber-500/30', text: 'text-amber-300', dot: 'bg-amber-400' },
  TRANSCODE: { box: 'bg-rose-500/15 ring-rose-500/40', text: 'text-rose-300', dot: 'bg-rose-400' },
  'LOSSY SOURCE': { box: 'bg-red-500/15 ring-red-500/40', text: 'text-red-300', dot: 'bg-red-400' },
  ERROR: { box: 'bg-slate-500/10 ring-slate-500/30', text: 'text-slate-400', dot: 'bg-slate-500' },
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const s = STYLES[verdict] ?? STYLES.ERROR
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ${s.box} ${s.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {verdict}
    </span>
  )
}
