import { useCallback, useEffect, useRef } from 'react'

export default function useResponsiveSidebarCollapse({
  isNarrowViewport,
  storagePrefix,
  collapsedFiletree,
  setCollapsed,
}) {
  const collapsedFiletreeRef = useRef(collapsedFiletree)
  const autoCollapsedRef = useRef(false)
  const previousNarrowRef = useRef(null)
  const previousStoragePrefixRef = useRef(storagePrefix)

  useEffect(() => {
    collapsedFiletreeRef.current = collapsedFiletree
  }, [collapsedFiletree])

  useEffect(() => {
    const previousNarrow = previousNarrowRef.current
    const previousStoragePrefix = previousStoragePrefixRef.current
    const enteringNarrow = previousNarrow !== true && isNarrowViewport
    const leavingNarrow = previousNarrow === true && !isNarrowViewport
    const storageChanged = previousStoragePrefix !== storagePrefix

    previousNarrowRef.current = isNarrowViewport
    previousStoragePrefixRef.current = storagePrefix

    if (isNarrowViewport && (enteringNarrow || storageChanged) && !collapsedFiletreeRef.current) {
      autoCollapsedRef.current = true
      setCollapsed((prev) => (
        prev.filetree
          ? prev
          : { ...prev, filetree: true }
      ))
      return
    }

    if (leavingNarrow && autoCollapsedRef.current) {
      autoCollapsedRef.current = false
      setCollapsed((prev) => (
        prev.filetree
          ? { ...prev, filetree: false }
          : prev
      ))
    }
  }, [isNarrowViewport, setCollapsed, storagePrefix])

  return useCallback(() => {
    autoCollapsedRef.current = false
  }, [])
}
