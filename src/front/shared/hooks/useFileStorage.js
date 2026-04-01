import { useCallback, useEffect, useRef } from 'react'

/**
 * useFileStorage - In-memory file storage using Map + URL.createObjectURL.
 *
 * Stores files in memory (NOT IndexedDB) and manages blob URL lifecycle.
 * Revokes all blob URLs on unmount to prevent memory leaks.
 *
 * Returns: { storeFile, getFileUrl, releaseFile, releaseAll }
 */
export function useFileStorage() {
  // Map<id, { file, url, ref }>
  const storeRef = useRef(new Map())
  let counter = useRef(0)

  const storeFile = useCallback((file) => {
    const id = `file-${++counter.current}-${Date.now()}`
    const url = URL.createObjectURL(file)
    const ref = {
      id,
      name: file.name,
      size: file.size,
      type: file.type,
    }
    storeRef.current.set(id, { file, url, ref })
    return ref
  }, [])

  const getFileUrl = useCallback((id) => {
    const entry = storeRef.current.get(id)
    return entry ? entry.url : null
  }, [])

  const releaseFile = useCallback((id) => {
    const entry = storeRef.current.get(id)
    if (entry) {
      URL.revokeObjectURL(entry.url)
      storeRef.current.delete(id)
    }
  }, [])

  const releaseAll = useCallback(() => {
    for (const [, entry] of storeRef.current) {
      URL.revokeObjectURL(entry.url)
    }
    storeRef.current.clear()
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    const store = storeRef.current
    return () => {
      for (const [, entry] of store) {
        URL.revokeObjectURL(entry.url)
      }
      store.clear()
    }
  }, [])

  return { storeFile, getFileUrl, releaseFile, releaseAll }
}
