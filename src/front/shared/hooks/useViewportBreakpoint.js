import { useEffect, useState } from 'react'

function readMatches(maxWidth) {
  if (typeof window === 'undefined') return false
  return window.innerWidth <= maxWidth
}

export default function useViewportBreakpoint(maxWidth = 960) {
  const [matches, setMatches] = useState(() => readMatches(maxWidth))

  useEffect(() => {
    const handleResize = () => {
      setMatches(readMatches(maxWidth))
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [maxWidth])

  return matches
}
