import { useMemo } from 'react'

const normalizeUrl = (value) => {
  let normalized = String(value || '').trim()
  if (normalized.startsWith('/') && typeof window !== 'undefined') {
    normalized = `${window.location.origin}${normalized}`
  }
  return normalized.replace(/\/+$/, '')
}

export default function PiAdapter({ url }) {
  const src = useMemo(() => normalizeUrl(url), [url])

  if (!src) return null

  return (
    <iframe
      title="Pi Agent"
      src={src}
      className="pi-agent-frame"
      style={{ width: '100%', height: '100%', border: 'none', background: 'transparent' }}
      sandbox="allow-scripts allow-forms allow-popups allow-downloads"
      allow="clipboard-read; clipboard-write"
      loading="lazy"
    />
  )
}
