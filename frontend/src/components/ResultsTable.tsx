import { useEffect, useRef, useState } from 'react'
import { FixedSizeList as List, type ListChildComponentProps } from 'react-window'
import type { TrackResult } from '../api'
import { VerdictBadge } from './VerdictBadge'

export type SortKey =
  | 'verdict'
  | 'name'
  | 'codec'
  | 'declaredKbps'
  | 'cutoffKhz'
  | 'trueQuality'
  | 'confidence'

export interface Sort {
  key: SortKey
  dir: 1 | -1
}

const COLS = '124px minmax(220px,1fr) 78px 70px 96px 152px 118px'
const ROW_H = 48

const HEADERS: { key: SortKey; label: string; align?: string }[] = [
  { key: 'verdict', label: 'Verdict' },
  { key: 'name', label: 'Track' },
  { key: 'codec', label: 'Codec' },
  { key: 'declaredKbps', label: 'kbps', align: 'justify-end' },
  { key: 'cutoffKhz', label: 'Cutoff', align: 'justify-end' },
  { key: 'trueQuality', label: 'True quality' },
  { key: 'confidence', label: 'Confidence' },
]

interface RowData {
  rows: TrackResult[]
  selected: string | null
  onSelect: (r: TrackResult) => void
}

function ConfBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-sky-400" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="tabular-nums text-[11px] text-slate-400">{value.toFixed(2)}</span>
    </div>
  )
}

function Row({ index, style, data }: ListChildComponentProps<RowData>) {
  const r = data.rows[index]
  const sel = data.selected === r.file
  return (
    <div
      style={{ ...style, gridTemplateColumns: COLS }}
      onClick={() => data.onSelect(r)}
      className={`mono grid cursor-pointer items-center gap-2 border-b border-slate-800/50 border-l-2 px-4 text-[13px] transition-colors ${
        sel
          ? 'border-l-sky-400 bg-sky-500/10'
          : `border-l-transparent ${index % 2 ? 'bg-slate-900/25' : ''} hover:bg-slate-800/30`
      }`}
    >
      <div>
        <VerdictBadge verdict={r.verdict} />
      </div>
      <div
        className="truncate text-slate-200"
        title={`${r.artist ? r.artist + ' · ' : ''}${r.name}`}
      >
        {r.name}
      </div>
      <div className="truncate text-slate-400">{r.codec || '·'}</div>
      <div className="text-right tabular-nums text-slate-300">{r.declaredKbps ?? '·'}</div>
      <div className="text-right tabular-nums text-slate-300">
        {r.cutoffKhz ? r.cutoffKhz.toFixed(1) : '·'}
      </div>
      <div className="truncate text-slate-300" title={r.trueQuality}>
        {r.trueQuality || '·'}
      </div>
      <div>
        {r.verdict === 'ERROR' ? <span className="text-slate-600">·</span> : <ConfBar value={r.confidence} />}
      </div>
    </div>
  )
}

function useHeight() {
  const ref = useRef<HTMLDivElement>(null)
  const [h, setH] = useState(480)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setH(e.contentRect.height)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return { ref, h }
}

export function ResultsTable({
  rows,
  sort,
  onSort,
  selected,
  onSelect,
}: {
  rows: TrackResult[]
  sort: Sort
  onSort: (k: SortKey) => void
  selected: string | null
  onSelect: (r: TrackResult) => void
}) {
  const { ref, h } = useHeight()
  return (
    <div className="fade-in flex min-h-0 flex-1 flex-col">
      <div
        className="grid items-center gap-2 border-b border-slate-800 bg-[#0d1119] px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500"
        style={{ gridTemplateColumns: COLS }}
      >
        {HEADERS.map((hd) => (
          <button
            key={hd.key}
            onClick={() => onSort(hd.key)}
            className={`flex items-center gap-1 transition-colors hover:text-slate-200 ${hd.align ?? 'justify-start'}`}
          >
            {hd.label}
            <span className="text-sky-400">
              {sort.key === hd.key ? (sort.dir === 1 ? '▲' : '▼') : ''}
            </span>
          </button>
        ))}
      </div>

      <div ref={ref} className="min-h-0 flex-1">
        {rows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-600">
            No tracks match the current filter.
          </div>
        ) : (
          <List
            height={h}
            width="100%"
            itemCount={rows.length}
            itemSize={ROW_H}
            itemData={{ rows, selected, onSelect }}
          >
            {Row}
          </List>
        )}
      </div>
    </div>
  )
}
