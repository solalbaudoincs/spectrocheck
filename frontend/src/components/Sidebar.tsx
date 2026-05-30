import { useState } from 'react'
import type { Playlist, RekordboxStatus } from '../api'

type Mode = 'rekordbox' | 'folder'

export function Sidebar({
  status,
  mode,
  setMode,
  playlist,
  setPlaylist,
  usbRoots,
  contentsRoot,
  setContentsRoot,
  folderPath,
  setFolderPath,
  onScan,
  scanning,
  done,
  total,
}: {
  status: RekordboxStatus | null
  mode: Mode
  setMode: (m: Mode) => void
  playlist: string
  setPlaylist: (s: string) => void
  usbRoots: string[]
  contentsRoot: string
  setContentsRoot: (s: string) => void
  folderPath: string
  setFolderPath: (s: string) => void
  onScan: () => void
  scanning: boolean
  done: number
  total: number
}) {
  const [filter, setFilter] = useState('')
  const playlists: Playlist[] = (status?.playlists ?? []).filter((p) => !p.is_folder)
  const shown = filter.trim()
    ? playlists.filter((p) => p.name.toLowerCase().includes(filter.trim().toLowerCase()))
    : playlists

  const canScan =
    !scanning && (mode === 'folder' ? folderPath.trim().length > 0 : playlist.trim().length > 0)

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-line bg-surface">
      {/* source */}
      <div className="border-b border-line px-3.5 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">Source</div>
        {mode === 'rekordbox' ? (
          <div className="mt-1.5 space-y-1">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="text-sm font-medium text-ink">
                Rekordbox {status?.version ?? ''}
              </span>
            </div>
            {status?.dbPath && (
              <div className="mono truncate text-[10px] text-muted" title={status.dbPath}>
                {status.dbPath}
              </div>
            )}
            <div className="text-[11px] text-muted">
              {contentsRoot ? (
                <>
                  maps to <span className="text-body">{contentsRoot}</span>
                </>
              ) : (
                'analysing original file paths'
              )}
            </div>
          </div>
        ) : (
          <div className="mt-1.5 text-sm font-medium text-ink">Local folder</div>
        )}
      </div>

      {/* mode */}
      <div className="flex gap-1 px-3.5 pt-3">
        {(['rekordbox', 'folder'] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${
              mode === m ? 'bg-panel text-ink ring-1 ring-line' : 'text-muted hover:text-body'
            }`}
          >
            {m === 'rekordbox' ? 'Playlists' : 'Folder'}
          </button>
        ))}
      </div>

      {/* body */}
      {mode === 'rekordbox' ? (
        <>
          <div className="px-3.5 py-2.5">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={`Filter ${playlists.length} playlists`}
              className="w-full rounded-md border border-line bg-input px-2.5 py-1.5 text-xs text-body transition focus:border-accent"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
            {status && !status.available && (
              <div className="px-2 py-3 text-xs text-rose-400">
                {status.error || 'Rekordbox DB not readable'}
              </div>
            )}
            {shown.map((p) => {
              const sel = p.name === playlist
              return (
                <button
                  key={p.id}
                  onClick={() => setPlaylist(p.name)}
                  className={`flex w-full items-center gap-2 rounded-md border-l-2 px-2.5 py-1.5 text-left transition ${
                    sel
                      ? 'border-accent bg-accent/10 text-ink'
                      : 'border-transparent text-body hover:bg-panel'
                  }`}
                >
                  <span className="truncate text-[13px]">{p.name}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-[11px] text-muted">{p.count}</span>
                </button>
              )
            })}
          </div>
        </>
      ) : (
        <div className="flex-1 px-3.5 py-3">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
            Folder to scan (recursive)
          </label>
          <input
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="D:\Music   or   /Users/me/Music"
            className="mono mt-1.5 w-full rounded-md border border-line bg-input px-2.5 py-1.5 text-xs text-body transition focus:border-accent"
          />
        </div>
      )}

      {/* footer: USB target + scan */}
      <div className="space-y-2.5 border-t border-line p-3.5">
        {mode === 'rekordbox' && (
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              USB Contents
            </label>
            <input
              list="usb-roots"
              value={contentsRoot}
              onChange={(e) => setContentsRoot(e.target.value)}
              placeholder="auto-detect"
              className="mono mt-1 w-full rounded-md border border-line bg-input px-2.5 py-1.5 text-xs text-body transition focus:border-accent"
            />
            <datalist id="usb-roots">
              {usbRoots.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </div>
        )}
        <button
          onClick={onScan}
          disabled={!canScan}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-accent py-2 text-sm font-semibold text-white transition hover:bg-accent-2 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {scanning && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          )}
          {scanning ? `Scanning ${done}/${total}` : 'Scan'}
        </button>
      </div>
    </aside>
  )
}
