export type Verdict = 'OK' | 'SUSPECT' | 'TRANSCODE' | 'LOSSY SOURCE' | 'ERROR'

export interface TrackResult {
  file: string
  name: string
  codec: string
  declaredKbps: number | null
  sampleRate: number
  channels: number
  durationSec: number
  cutoffKhz: number
  expectedCutoffKhz: number
  trueQuality: string
  verdict: Verdict
  confidence: number
  shelfDetected: boolean
  shelfSlopeDb: number
  reason: string
  error: string | null
  // rekordbox extras (present in playlist scans)
  title?: string
  artist?: string
  match?: string
  usbPath?: string | null
  originalPath?: string
  declaredKbpsRB?: number | null
}

export interface Playlist {
  id: string
  name: string
  is_folder: boolean
  count: number
}

export interface Health {
  ok: boolean
  ffmpeg?: string
  error?: string
}

export interface RekordboxStatus {
  available: boolean
  playlists: Playlist[]
  error?: string
  version?: string | null
  dbPath?: string | null
  dbDir?: string | null
  usbRoots?: string[]
}

export interface ScanRequest {
  path?: string
  playlist?: string
  contentsRoot?: string
}

export interface StartScanResponse {
  scanId: string
  total: number
  mode: string
}

export interface DoneSummary {
  total: number
  done: number
  error?: string | null
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  health: () => fetch('/api/health').then(j<Health>),
  usbRoots: () => fetch('/api/rekordbox/usb-roots').then(j<{ roots: string[] }>),
  playlists: () => fetch('/api/rekordbox/playlists').then(j<RekordboxStatus>),
  startScan: (req: ScanRequest) =>
    fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }).then(j<StartScanResponse>),

  exportUrl: (id: string, format: 'csv' | 'json', verdicts?: string[]) => {
    const q = new URLSearchParams({ format })
    if (verdicts && verdicts.length) q.set('verdicts', verdicts.join(','))
    return `/api/scan/${id}/export?${q.toString()}`
  },
  spectrogramUrl: (file: string, expected?: number, measured?: number) => {
    const q = new URLSearchParams({ file })
    if (expected) q.set('expected', String(expected))
    if (measured) q.set('measured', String(measured))
    return `/api/spectrogram?${q.toString()}`
  },
  coverUrl: (file: string) => `/api/cover?file=${encodeURIComponent(file)}`,
}

/** Subscribe to a scan's SSE stream. Returns the EventSource so it can be closed. */
export function subscribeScan(
  id: string,
  onResult: (r: TrackResult) => void,
  onDone: (summary: DoneSummary) => void,
): EventSource {
  const es = new EventSource(`/api/scan/${id}/events`)
  es.addEventListener('result', (e) => onResult(JSON.parse((e as MessageEvent).data)))
  es.addEventListener('done', (e) => {
    onDone(JSON.parse((e as MessageEvent).data))
    es.close()
  })
  return es
}
