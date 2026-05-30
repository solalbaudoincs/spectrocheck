// Pioneer / AlphaTheta rekordbox-hardware format support, from published specs.
// The practical gates are: (1) FLAC/ALAC is only on newer gear, (2) Pioneer
// players don't play OGG/Opus/WMA, (3) hi-res (>48 kHz) PCM/lossless needs newer
// gear. MP3/AAC/WAV/AIFF at <=48 kHz play on essentially everything.

export type Family = 'mp3' | 'aac' | 'alac' | 'flac' | 'pcm' | 'other'

interface PlayerSpec {
  name: string
  families: Family[]
  maxSr: number // max sample rate (Hz) for PCM/lossless
}

const FULL: Family[] = ['mp3', 'aac', 'pcm', 'flac', 'alac']
const LEGACY: Family[] = ['mp3', 'aac', 'pcm']

// Ordered newest/most-capable first. All-in-ones included (AZ, XZ, RX3, RX2,
// RR, OMNIS-DUO, OPUS-QUAD). maxSr caps hi-res: RR does lossless only up to
// 48 kHz in standalone USB playback.
const PLAYERS: PlayerSpec[] = [
  { name: 'CDJ-3000', families: FULL, maxSr: 96000 },
  { name: 'OPUS-QUAD', families: FULL, maxSr: 96000 },
  { name: 'OMNIS-DUO', families: FULL, maxSr: 96000 },
  { name: 'XDJ-AZ', families: FULL, maxSr: 96000 },
  { name: 'CDJ-2000NXS2', families: FULL, maxSr: 96000 },
  { name: 'CDJ-TOUR1', families: FULL, maxSr: 96000 },
  { name: 'XDJ-XZ', families: FULL, maxSr: 96000 },
  { name: 'XDJ-RX3', families: FULL, maxSr: 96000 },
  { name: 'XDJ-RX2', families: FULL, maxSr: 96000 },
  { name: 'XDJ-1000MK2', families: FULL, maxSr: 96000 },
  { name: 'XDJ-RR', families: FULL, maxSr: 48000 },
  { name: 'CDJ-2000NXS', families: LEGACY, maxSr: 48000 },
  { name: 'CDJ-2000', families: LEGACY, maxSr: 48000 },
  { name: 'CDJ-900NXS', families: LEGACY, maxSr: 48000 },
  { name: 'CDJ-900', families: LEGACY, maxSr: 48000 },
  { name: 'CDJ-850', families: LEGACY, maxSr: 48000 },
  { name: 'XDJ-1000', families: LEGACY, maxSr: 48000 },
  { name: 'XDJ-700', families: LEGACY, maxSr: 48000 },
  { name: 'XDJ-RX', families: LEGACY, maxSr: 48000 },
]

export function codecFamily(codec: string): Family {
  const c = (codec || '').toLowerCase()
  if (c === 'mp3') return 'mp3'
  if (c === 'aac') return 'aac'
  if (c === 'alac') return 'alac'
  if (c === 'flac') return 'flac'
  if (c.startsWith('pcm')) return 'pcm'
  return 'other'
}

export interface PlayerCompat {
  name: string
  ok: boolean
  reason: string
}

export function playerCompatibility(codec: string, sampleRate: number): PlayerCompat[] {
  const fam = codecFamily(codec)
  return PLAYERS.map((p) => {
    if (fam === 'other')
      return { name: p.name, ok: false, reason: 'format not supported by Pioneer players' }
    if (!p.families.includes(fam))
      return {
        name: p.name,
        ok: false,
        reason: fam === 'flac' || fam === 'alac' ? 'no FLAC / ALAC support' : 'format unsupported',
      }
    if ((fam === 'pcm' || fam === 'flac' || fam === 'alac') && sampleRate && sampleRate > p.maxSr)
      return {
        name: p.name,
        ok: false,
        reason: `${(sampleRate / 1000).toFixed(1)} kHz over ${(p.maxSr / 1000).toFixed(0)} kHz limit`,
      }
    return { name: p.name, ok: true, reason: '' }
  })
}
