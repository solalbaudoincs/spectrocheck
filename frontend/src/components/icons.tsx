import type { SVGProps } from 'react'

/** Spectrum bars rising then falling off a cliff: the cutoff motif. */
export function Logo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <rect x="2.5" y="13" width="2.6" height="8" rx="1.3" />
      <rect x="7" y="8.5" width="2.6" height="12.5" rx="1.3" />
      <rect x="11.5" y="5" width="2.6" height="16" rx="1.3" />
      <rect x="16" y="10.5" width="2.6" height="10.5" rx="1.3" opacity="0.45" />
      <rect x="20.5" y="17" width="2.4" height="4" rx="1.2" opacity="0.25" />
    </svg>
  )
}

/** Vinyl disc — cover-art fallback. */
export function DiscIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true" {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="2.2" />
    </svg>
  )
}
