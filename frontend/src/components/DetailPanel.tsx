import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { TrackResult } from '../api'
import { VerdictBadge } from './VerdictBadge'

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      <span className="mono text-sm text-slate-200">{value}</span>
    </div>
  )
}

export function DetailPanel({ row, onClose }: { row: TrackResult; onClose: () => void }) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  const canSpec = row.verdict !== 'ERROR' && !!row.file
  const src = canSpec
    ? api.spectrogramUrl(row.file, row.expectedCutoffKhz || undefined, row.cutoffKhz || undefined)
    : ''

  useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [src])

  return (
    <aside className="flex w-[540px] shrink-0 flex-col border-l border-slate-800 bg-[#0d111a]">
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 p-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <VerdictBadge verdict={row.verdict} />
            <span className="tabular-nums text-xs text-slate-500">
              confidence {row.confidence.toFixed(2)}
            </span>
          </div>
          <h2 className="mono mt-2 truncate text-sm text-slate-100" title={row.name}>
            {row.name}
          </h2>
          {row.artist && <p className="truncate text-xs text-slate-400">{row.artist}</p>}
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-200"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <p className="rounded-md border border-slate-800 bg-slate-900/50 p-3 text-sm leading-relaxed text-slate-300">
          {row.reason}
        </p>

        <div className="grid grid-cols-3 gap-y-3 gap-x-2">
          <Fact label="Codec" value={row.codec || '—'} />
          <Fact label="Declared" value={row.declaredKbps ? `${row.declaredKbps} kbps` : '—'} />
          <Fact label="Sample rate" value={row.sampleRate ? `${row.sampleRate} Hz` : '—'} />
          <Fact
            label="Measured cutoff"
            value={<span className="text-sky-300">{row.cutoffKhz ? `${row.cutoffKhz.toFixed(1)} kHz` : '—'}</span>}
          />
          <Fact label="Expected ≥" value={`${row.expectedCutoffKhz.toFixed(1)} kHz`} />
          <Fact
            label="Brick-wall shelf"
            value={
              row.shelfDetected ? (
                <span className="text-rose-300">YES ({row.shelfSlopeDb.toFixed(0)} dB)</span>
              ) : (
                <span className="text-slate-400">no</span>
              )
            }
          />
          <Fact label="True quality" value={row.trueQuality || '—'} />
          <Fact label="Duration" value={row.durationSec ? `${row.durationSec.toFixed(0)} s` : '—'} />
          {row.match && <Fact label="USB match" value={row.match} />}
        </div>

        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">
            Spectrogram — the proof
          </div>
          <div className="relative overflow-hidden rounded-md border border-slate-800 bg-black">
            {canSpec ? (
              <>
                {!loaded && !failed && (
                  <div className="flex h-64 items-center justify-center text-xs text-slate-500">
                    rendering spectrogram…
                  </div>
                )}
                {failed && (
                  <div className="flex h-64 items-center justify-center text-xs text-rose-400">
                    failed to render spectrogram
                  </div>
                )}
                <img
                  key={src}
                  src={src}
                  alt="spectrogram"
                  onLoad={() => setLoaded(true)}
                  onError={() => setFailed(true)}
                  className={`w-full ${loaded ? 'block' : 'hidden'}`}
                />
              </>
            ) : (
              <div className="flex h-64 items-center justify-center text-xs text-slate-600">
                no spectrogram available
              </div>
            )}
          </div>
          <p className="mt-1.5 text-[11px] leading-snug text-slate-500">
            Cyan = cutoff expected for the declared bitrate. Red = the cutoff actually measured.
            Black space above the red line is signal the encoder threw away.
          </p>
        </div>

        <div className="space-y-2 border-t border-slate-800 pt-3">
          <Fact label="Analysed file" value={<span className="break-all text-xs text-slate-400">{row.file}</span>} />
          {row.originalPath && row.originalPath !== row.file && (
            <Fact
              label="Library original"
              value={<span className="break-all text-xs text-slate-500">{row.originalPath}</span>}
            />
          )}
        </div>
      </div>
    </aside>
  )
}
