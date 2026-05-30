import { useState } from 'react'
import { api } from '../api'

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
        <span style={{ fontSize: Math.round(size * 0.42) }}>♪</span>
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
