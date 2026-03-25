/**
 * Custom DockView tab components.
 *
 * Provides UnifiedDockTab (with close button, middle-click close, compact mode)
 * and TabWithoutClose (for locked panels like shell).
 *
 * @module components/DockTab
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Bot, X } from 'lucide-react'

const COMPACT_TAB_COMPONENTS = new Set(['terminal', 'agent', 'shell'])
const COMPACT_TAB_PREFIXES = ['terminal-chat-', 'agent-chat-']

const shouldUseCompactTab = (api, tabLocation) => {
  if (tabLocation === 'headerOverflow') return true

  const panelId = String(api?.id || '')
  const componentId = String(api?.component || '')
  if (COMPACT_TAB_COMPONENTS.has(componentId)) return true
  return COMPACT_TAB_PREFIXES.some((prefix) => panelId.startsWith(prefix))
}

export function UnifiedDockTab({
  api,
  containerApi: _containerApi,
  hideClose = false,
  closeActionOverride,
  onPointerDown,
  onPointerUp,
  onPointerLeave,
  tabLocation,
  className,
  ...rest
}) {
  const [title, setTitle] = useState(api?.title)
  const isMiddleMouseButton = useRef(false)
  const compact = shouldUseCompactTab(api, tabLocation)

  useEffect(() => {
    setTitle(api?.title)
    if (!api?.onDidTitleChange) return undefined

    const disposable = api.onDidTitleChange((event) => {
      setTitle(event.title)
    })

    return () => {
      disposable?.dispose?.()
    }
  }, [api])

  const onClose = useCallback(
    (event) => {
      event.preventDefault()
      event.stopPropagation()
      if (closeActionOverride) {
        closeActionOverride()
      } else {
        api?.close?.()
      }
    },
    [api, closeActionOverride],
  )

  const handlePointerDown = useCallback(
    (event) => {
      isMiddleMouseButton.current = event.button === 1
      onPointerDown?.(event)
    },
    [onPointerDown],
  )

  const handlePointerUp = useCallback(
    (event) => {
      if (isMiddleMouseButton.current && event.button === 1 && !hideClose) {
        isMiddleMouseButton.current = false
        onClose(event)
      }
      onPointerUp?.(event)
    },
    [hideClose, onClose, onPointerUp],
  )

  const handlePointerLeave = useCallback(
    (event) => {
      isMiddleMouseButton.current = false
      onPointerLeave?.(event)
    },
    [onPointerLeave],
  )

  const tabClassName = [
    'dv-default-tab',
    'ui-dv-tab',
    compact ? 'ui-dv-tab-compact' : 'ui-dv-tab-default',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      data-testid="dockview-dv-default-tab"
      {...rest}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerLeave}
      className={tabClassName}
    >
      <span className="dv-default-tab-content">
        {title === 'Agent' && <Bot size={14} className="dv-tab-icon" />}
        {title || ''}
      </span>
      {!hideClose && (
        <button
          type="button"
          className="dv-default-tab-action ui-dv-tab-close"
          onPointerDown={(event) => {
            event.preventDefault()
            event.stopPropagation()
          }}
          onClick={onClose}
          aria-label={title ? `Close ${title}` : 'Close tab'}
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}

// Custom tab component that hides close button (for shell tabs)
export const TabWithoutClose = (props) => <UnifiedDockTab {...props} hideClose />

export const tabComponents = {
  noClose: TabWithoutClose,
}
