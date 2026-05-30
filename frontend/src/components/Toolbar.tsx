import type { ReactNode } from 'react'
import type { Playlist } from '../api'

type Mode = 'rekordbox' | 'folder'

export function Toolbar({
  mode,
  setMode,
  rekordboxAvailable,
  rekordboxError,
  playlists,
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
  mode: Mode
  setMode: (m: Mode) => void
  rekordboxAvailable: boolean
  rekordboxError?: string
  playlists: Playlist[]
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
  const canScan =
    !scanning && (mode === 'folder' ? folderPath.trim().length > 0 : playlist.trim().length > 0)

  const tab = (m: Mode, label: string) => (
    <button
      onClick={() => setMode(m)}
      className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
        mode === m ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="flex flex-wrap items-end gap-3 border-b border-slate-800 bg-[#0d111a] px-4 py-3">
      <div className="flex rounded-lg bg-slate-900 p-0.5 ring-1 ring-slate-800">
        {tab('rekordbox', 'Rekordbox playlist')}
        {tab('folder', 'Folder')}
      </div>

      {mode === 'rekordbox' ? (
        <>
          <Field label="Playlist">
            <select
              value={playlist}
              disabled={!rekordboxAvailable}
              onChange={(e) => setPlaylist(e.target.value)}
              className="mono w-72 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
            >
              {!rekordboxAvailable && <option>— Rekordbox unavailable —</option>}
              {playlists
                .filter((p) => !p.is_folder)
                .map((p) => (
                  <option key={p.id} value={p.name}>
                    {p.name} ({p.count})
                  </option>
                ))}
            </select>
          </Field>
          <Field label="USB Contents (optional)">
            <input
              list="usb-roots"
              value={contentsRoot}
              onChange={(e) => setContentsRoot(e.target.value)}
              placeholder="auto-detect"
              className="mono w-64 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200"
            />
            <datalist id="usb-roots">
              {usbRoots.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </Field>
        </>
      ) : (
        <Field label="Folder to scan (recursive)">
          <input
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="D:\Contents  or  C:\Users\me\Music"
            className="mono w-[28rem] rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200"
          />
        </Field>
      )}

      <button
        onClick={onScan}
        disabled={!canScan}
        className="flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {scanning && <Spinner />}
        {scanning ? `Scanning ${done}/${total}` : 'Scan'}
      </button>

      {!rekordboxAvailable && mode === 'rekordbox' && (
        <span className="text-xs text-rose-400">{rekordboxError || 'Rekordbox DB not readable'}</span>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      <div className="flex items-center gap-1">{children}</div>
    </label>
  )
}

function Spinner() {
  return (
    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
  )
}
