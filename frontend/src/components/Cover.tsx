import { useState } from 'react'
import { api } from '../api'
import { DiscIcon } from './icons'

/** Album art (embedded, extracted by the backend). Falls back to a note glyph. */
export function Cover({
  file,
  size = 32,
  radius = 'rounded',
}: {
  file: string
  size?: number
  radius?: string
}) {
  const [failed, setFailed] = useState(false)
  const box = { width: size, height: size, minWidth: size }

  if (!file || failed) {
    return (
      <div
        style={box}
        className={`grid place-items-center bg-panel text-muted ring-1 ring-line ${radius}`}
      >
        <DiscIcon style={{ width: Math.round(size * 0.5), height: Math.round(size * 0.5) }} />
      </div>
    )
  }
  return (
    <img
      src={api.coverUrl(file)}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      style={box}
      className={`bg-panel object-cover ring-1 ring-line ${radius}`}
    />
  )
}
