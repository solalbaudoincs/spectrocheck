import { useEffect, useMemo, useRef, useState } from 'react'
import { api, subscribeScan } from './api'
import type { Health, RekordboxStatus, TrackResult, Verdict } from './api'
import { Sidebar } from './components/Sidebar'
import { FilterChips } from './components/FilterChips'
import { ResultsTable, type Sort, type SortKey } from './components/ResultsTable'
import { DetailPanel } from './components/DetailPanel'

type Mode = 'rekordbox' | 'folder'

const SEVERITY: Record<Verdict, number> = {
  TRANSCODE: 0,
  'LOSSY SOURCE': 1,
  SUSPECT: 2,
  OK: 3,
  ERROR: 4,
}

const DESC_DEFAULT: SortKey[] = ['declaredKbps', 'cutoffKhz', 'confidence']

const EXPORT_COLS = [
  'name', 'verdict', 'confidence', 'codec', 'declaredKbps', 'sampleRate',
  'cutoffKhz', 'expectedCutoffKhz', 'trueQuality', 'shelfDetected', 'durationSec',
  'artist', 'title', 'match', 'file', 'reason',
] as const

function downloadBlob(filename: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function rowsToCsv(rows: TrackResult[]): string {
  const esc = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const header = EXPORT_COLS.join(',')
  const body = rows
    .map((r) => EXPORT_COLS.map((c) => esc((r as unknown as Record<string, unknown>)[c])).join(','))
    .join('\n')
  return header + '\n' + body
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [pl, setPl] = useState<RekordboxStatus>({ available: false, playlists: [] })
  const [usbRoots, setUsbRoots] = useState<string[]>([])

  const [mode, setMode] = useState<Mode>('rekordbox')
  const [playlist, setPlaylist] = useState('')
  const [contentsRoot, setContentsRoot] = useState('')
  const [folderPath, setFolderPath] = useState('')

  const [results, setResults] = useState<TrackResult[]>([])
  const [scanning, setScanning] = useState(false)
  const [total, setTotal] = useState(0)

  const [active, setActive] = useState<Set<Verdict>>(new Set())
  const [sort, setSort] = useState<Sort>({ key: 'verdict', dir: 1 })
  const [selected, setSelected] = useState<TrackResult | null>(null)
  const [search, setSearch] = useState('')

  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false, error: 'backend unreachable' }))
    api
      .playlists()
      .then((s) => {
        setPl(s)
        const roots = s.usbRoots ?? []
        setUsbRoots(roots)
        if (roots[0]) setContentsRoot((c) => c || roots[0])
      })
      .catch(() => setPl({ available: false, playlists: [], error: 'failed to read Rekordbox DB' }))
    return () => esRef.current?.close()
  }, [])

  // Default the playlist to one containing "final", else the first non-empty one.
  useEffect(() => {
    if (playlist || !pl.playlists.length) return
    const real = pl.playlists.filter((p) => !p.is_folder)
    const pick = real.find((p) => /final/i.test(p.name)) ?? real.find((p) => p.count > 0) ?? real[0]
    if (pick) setPlaylist(pick.name)
  }, [pl, playlist])

  const startScan = async () => {
    esRef.current?.close()
    setResults([])
    setSelected(null)
    setActive(new Set())
    setScanning(true)
    setTotal(0)
    const req =
      mode === 'rekordbox'
        ? { playlist, contentsRoot: contentsRoot || undefined }
        : { path: folderPath }
    try {
      const s = await api.startScan(req)
      setTotal(s.total)
      esRef.current = subscribeScan(
        s.scanId,
        (r) => setResults((prev) => [...prev, r]),
        () => setScanning(false),
      )
    } catch (e) {
      setScanning(false)
      alert('Scan failed: ' + (e instanceof Error ? e.message : String(e)))
    }
  }

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const r of results) c[r.verdict] = (c[r.verdict] || 0) + 1
    return c
  }, [results])

  const view = useMemo(() => {
    let rows = results
    if (active.size) rows = rows.filter((r) => active.has(r.verdict))
    const q = search.trim().toLowerCase()
    if (q)
      rows = rows.filter(
        (r) => r.name.toLowerCase().includes(q) || (r.artist || '').toLowerCase().includes(q),
      )

    const { key, dir } = sort
    const val = (r: TrackResult): number | string => {
      if (key === 'verdict') return SEVERITY[r.verdict]
      if (key === 'trueQuality') return r.cutoffKhz
      const v = r[key]
      return v == null ? -Infinity : (v as number | string)
    }
    return [...rows].sort((a, b) => {
      const av = val(a)
      const bv = val(b)
      if (av < bv) return -1 * dir
      if (av > bv) return 1 * dir
      if (a.confidence !== b.confidence) return b.confidence - a.confidence
      return a.name.localeCompare(b.name)
    })
  }, [results, active, search, sort])

  const onSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: (s.dir === 1 ? -1 : 1) as 1 | -1 }
        : { key, dir: DESC_DEFAULT.includes(key) ? -1 : 1 },
    )

  const onToggleFilter = (v: Verdict) =>
    setActive((prev) => {
      const next = new Set(prev)
      if (next.has(v)) next.delete(v)
      else next.add(v)
      return next
    })

  const flagged = (counts.TRANSCODE || 0) + (counts['LOSSY SOURCE'] || 0)

  const exportView = (format: 'csv' | 'json') => {
    if (format === 'csv') downloadBlob('transcode-scan.csv', rowsToCsv(view), 'text/csv')
    else downloadBlob('transcode-scan.json', JSON.stringify(view, null, 2), 'application/json')
  }

  return (
    <div className="flex h-screen flex-col bg-base text-body">
      {/* header */}
      <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent/15 text-sm ring-1 ring-accent/30">
            🎛️
          </span>
          <h1 className="text-sm font-semibold tracking-tight text-ink">Transcode Detector</h1>
          <span className="hidden text-line-strong sm:inline">/</span>
          <span className="hidden text-xs text-muted sm:inline">
            flags audio whose real quality is below its tag
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-md bg-input px-2.5 py-1 ring-1 ring-line">
          <span className={`h-2 w-2 rounded-full ${health?.ok ? 'bg-emerald-400' : 'bg-rose-500'}`} />
          <span className="mono text-[11px] text-muted">
            {health?.ok
              ? (health.ffmpeg || '').split(' ').slice(0, 3).join(' ')
              : health?.error || 'checking…'}
          </span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <Sidebar
          status={pl}
          mode={mode}
          setMode={setMode}
          playlist={playlist}
          setPlaylist={setPlaylist}
          usbRoots={usbRoots}
          contentsRoot={contentsRoot}
          setContentsRoot={setContentsRoot}
          folderPath={folderPath}
          setFolderPath={setFolderPath}
          onScan={startScan}
          scanning={scanning}
          done={results.length}
          total={total}
        />

        <main className="flex min-h-0 flex-1 flex-col">
          {/* filter + summary + export bar */}
          <div className="flex flex-wrap items-center gap-3 border-b border-line bg-surface/60 px-4 py-2.5">
            <FilterChips counts={counts} active={active} onToggle={onToggleFilter} />
            <div className="ml-auto flex items-center gap-3">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="search track or artist"
                className="w-52 rounded-md border border-line bg-input px-2.5 py-1.5 text-xs text-body transition focus:border-accent"
              />
              <span className="text-xs text-muted">
                {results.length} scanned
                {flagged > 0 && <span className="ml-1.5 text-rose-400">{flagged} flagged</span>}
              </span>
              {results.length > 0 && (
                <div className="flex gap-1">
                  <button
                    onClick={() => exportView('csv')}
                    className="rounded-md border border-line px-2.5 py-1 text-xs text-body transition hover:border-line-strong hover:bg-panel"
                  >
                    CSV
                  </button>
                  <button
                    onClick={() => exportView('json')}
                    className="rounded-md border border-line px-2.5 py-1 text-xs text-body transition hover:border-line-strong hover:bg-panel"
                  >
                    JSON
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex min-h-0 flex-1">
            {results.length === 0 && !scanning ? (
              <div className="fade-in flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center text-muted">
                <div className="grid h-14 w-14 place-items-center rounded-2xl bg-accent/10 text-3xl ring-1 ring-accent/20">
                  📊
                </div>
                <p className="text-sm text-body">
                  Pick a playlist on the left, then hit{' '}
                  <span className="font-semibold text-accent-2">Scan</span>.
                </p>
                <p className="max-w-md text-xs leading-relaxed">
                  Each track is decoded and its high-frequency cutoff measured. A 320-tagged file
                  whose spectrum brick-walls at 16 kHz is a transcode, and the spectrogram proves it.
                </p>
              </div>
            ) : (
              <>
                <ResultsTable
                  rows={view}
                  sort={sort}
                  onSort={onSort}
                  selected={selected?.file ?? null}
                  onSelect={setSelected}
                />
                {selected && <DetailPanel row={selected} onClose={() => setSelected(null)} />}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
