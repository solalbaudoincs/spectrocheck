import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { FixedSizeList as List, type ListChildComponentProps } from 'react-window'
import type { TrackResult } from '../api'
import { VerdictBadge } from './VerdictBadge'
import { Cover } from './Cover'

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

const COLS = '46px 116px minmax(200px,1fr) 66px 62px 88px 150px 118px'
const ROW_H = 52

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
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-panel">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="tabular-nums text-[11px] text-muted">{value.toFixed(2)}</span>
    </div>
  )
}

function SkeletonRow({ style }: { style: CSSProperties }) {
  return (
    <div
      style={{ ...style, gridTemplateColumns: COLS }}
      className="grid items-center gap-2 border-b border-l-2 border-line/60 border-l-transparent px-3"
    >
      <div className="h-[34px] w-[34px] animate-pulse rounded bg-panel" />
      <div className="h-4 w-20 animate-pulse rounded bg-panel" />
      <div className="space-y-1.5">
        <div className="h-3 w-40 animate-pulse rounded bg-panel" />
        <div className="h-2.5 w-24 animate-pulse rounded bg-panel/60" />
      </div>
      <div className="h-3 w-8 animate-pulse rounded bg-panel" />
      <div className="ml-auto h-3 w-8 animate-pulse rounded bg-panel" />
      <div className="ml-auto h-3 w-10 animate-pulse rounded bg-panel" />
      <div className="h-3 w-20 animate-pulse rounded bg-panel" />
      <div className="h-1.5 w-14 animate-pulse rounded-full bg-panel" />
    </div>
  )
}

function Row({ index, style, data }: ListChildComponentProps<RowData>) {
  const r = data.rows[index]
  if (!r) return <SkeletonRow style={style} />
  const sel = data.selected === r.file
  return (
    <div
      style={{ ...style, gridTemplateColumns: COLS }}
      onClick={() => data.onSelect(r)}
      className={`grid cursor-pointer items-center gap-2 border-b border-line/60 border-l-2 px-3 text-[13px] transition-colors ${
        sel
          ? 'border-l-accent bg-accent/10'
          : `border-l-transparent ${index % 2 ? 'bg-white/[0.012]' : ''} hover:bg-panel/70`
      }`}
    >
      <Cover key={r.file} file={r.file} size={34} radius="rounded" />
      <div>
        <VerdictBadge verdict={r.verdict} />
      </div>
      <div className="min-w-0">
        <div className="truncate text-ink" title={r.name}>
          {r.name}
        </div>
        {r.artist && <div className="truncate text-[11px] text-muted">{r.artist}</div>}
      </div>
      <div className="truncate text-muted">{r.codec || '·'}</div>
      <div className="text-right tabular-nums text-body">{r.declaredKbps ?? '·'}</div>
      <div className="text-right tabular-nums text-body">
        {r.cutoffKhz ? r.cutoffKhz.toFixed(1) : '·'}
      </div>
      <div className="truncate text-body" title={r.trueQuality}>
        {r.trueQuality || '·'}
      </div>
      <div>{r.verdict === 'ERROR' ? <span className="text-muted">·</span> : <ConfBar value={r.confidence} />}</div>
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
  pending = 0,
  sort,
  onSort,
  selected,
  onSelect,
}: {
  rows: TrackResult[]
  pending?: number
  sort: Sort
  onSort: (k: SortKey) => void
  selected: string | null
  onSelect: (r: TrackResult) => void
}) {
  const { ref, h } = useHeight()
  const count = rows.length + pending
  return (
    <div className="fade-in flex min-h-0 flex-1 flex-col">
      <div
        className="grid items-center gap-2 border-b border-line bg-surface px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted"
        style={{ gridTemplateColumns: COLS }}
      >
        <span />
        {HEADERS.map((hd) => (
          <button
            key={hd.key}
            onClick={() => onSort(hd.key)}
            className={`flex items-center gap-1 transition-colors hover:text-body ${hd.align ?? 'justify-start'}`}
          >
            {hd.label}
            <span className="text-accent">
              {sort.key === hd.key ? (sort.dir === 1 ? '▲' : '▼') : ''}
            </span>
          </button>
        ))}
      </div>

      <div ref={ref} className="min-h-0 flex-1">
        {count === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            No tracks match the current filter.
          </div>
        ) : (
          <List
            height={h}
            width="100%"
            itemCount={count}
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
