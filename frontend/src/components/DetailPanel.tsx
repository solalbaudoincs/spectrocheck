import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { TrackResult } from '../api'
import { VerdictBadge } from './VerdictBadge'
import { Cover } from './Cover'

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <span className="text-sm text-ink">{value}</span>
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
    <aside className="panel-in flex w-[560px] shrink-0 flex-col border-l border-line bg-surface">
      <div className="flex items-start gap-3 border-b border-line p-4">
        <Cover key={row.file} file={row.file} size={56} radius="rounded-lg" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <VerdictBadge verdict={row.verdict} />
            <span className="tabular-nums text-xs text-muted">
              confidence {row.confidence.toFixed(2)}
            </span>
          </div>
          <h2 className="mt-1.5 truncate text-sm font-medium text-ink" title={row.name}>
            {row.name}
          </h2>
          {row.artist && <p className="truncate text-xs text-muted">{row.artist}</p>}
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 text-muted transition hover:bg-panel hover:text-ink"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <p className="rounded-lg border border-line bg-input p-3 text-sm leading-relaxed text-body">
          {row.reason}
        </p>

        <div className="grid grid-cols-3 gap-x-2 gap-y-3.5">
          <Fact label="Codec" value={row.codec || '·'} />
          <Fact label="Declared" value={row.declaredKbps ? `${row.declaredKbps} kbps` : '·'} />
          <Fact label="Sample rate" value={row.sampleRate ? `${row.sampleRate} Hz` : '·'} />
          <Fact
            label="Measured cutoff"
            value={<span className="text-accent-2">{row.cutoffKhz ? `${row.cutoffKhz.toFixed(1)} kHz` : '·'}</span>}
          />
          <Fact label="Expected ≥" value={`${row.expectedCutoffKhz.toFixed(1)} kHz`} />
          <Fact
            label="Brick-wall shelf"
            value={
              row.shelfDetected ? (
                <span className="text-rose-300">yes ({row.shelfSlopeDb.toFixed(0)} dB)</span>
              ) : (
                <span className="text-muted">no</span>
              )
            }
          />
          <Fact label="True quality" value={row.trueQuality || '·'} />
          <Fact label="Duration" value={row.durationSec ? `${row.durationSec.toFixed(0)} s` : '·'} />
          {row.match && <Fact label="USB match" value={row.match} />}
        </div>

        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-muted">
            Spectrogram · the proof
          </div>
          <div className="relative overflow-hidden rounded-lg border border-line bg-black">
            {canSpec ? (
              <>
                {!loaded && !failed && (
                  <div className="flex h-64 items-center justify-center text-xs text-muted">
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
              <div className="flex h-64 items-center justify-center text-xs text-muted">
                no spectrogram available
              </div>
            )}
          </div>
          <p className="mt-2 text-[11px] leading-snug text-muted">
            Cyan line = cutoff expected for the declared bitrate. Red line = the cutoff actually
            measured. Black space above the red line is signal the encoder threw away.
          </p>
        </div>

        <div className="space-y-2 border-t border-line pt-3">
          <Fact label="Analysed file" value={<span className="mono break-all text-xs text-muted">{row.file}</span>} />
          {row.originalPath && row.originalPath !== row.file && (
            <Fact
              label="Library original"
              value={<span className="mono break-all text-xs text-muted">{row.originalPath}</span>}
            />
          )}
        </div>
      </div>
    </aside>
  )
}
