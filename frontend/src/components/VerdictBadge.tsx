import type { Verdict } from '../api'

const STYLES: Record<Verdict, string> = {
  OK: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  SUSPECT: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  TRANSCODE: 'bg-rose-500/20 text-rose-300 ring-rose-500/40',
  'LOSSY SOURCE': 'bg-red-500/20 text-red-300 ring-red-500/40',
  ERROR: 'bg-slate-500/15 text-slate-400 ring-slate-500/30',
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ring-1 ${
        STYLES[verdict] ?? STYLES.ERROR
      }`}
    >
      {verdict}
    </span>
  )
}
