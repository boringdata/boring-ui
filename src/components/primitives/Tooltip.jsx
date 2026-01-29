import React, { useState } from 'react'
import { clsx } from 'clsx'

/**
 * Tooltip - Floating tooltip component
 * @component
 * @param {string} content - Tooltip content
 * @param {string} side - Tooltip position: top, right, bottom, left
 * @param {React.ReactNode} children - Tooltip trigger element
 * @param {number} delay - Delay before showing tooltip (ms)
 */
const Tooltip = React.forwardRef(({
  content,
  side = 'top',
  delay = 200,
  children,
  className,
  ...props
}, ref) => {
  const [isOpen, setIsOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const timeoutRef = React.useRef(null)
  const triggerRef = React.useRef(null)

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect()
        const positions = {
          top: { top: rect.top - 40, left: rect.left + rect.width / 2 },
          bottom: { top: rect.bottom + 8, left: rect.left + rect.width / 2 },
          left: { top: rect.top + rect.height / 2, left: rect.left - 8 },
          right: { top: rect.top + rect.height / 2, left: rect.right + 8 },
        }
        setPosition(positions[side])
        setIsOpen(true)
      }
    }, delay)
  }

  const handleMouseLeave = () => {
    clearTimeout(timeoutRef.current)
    setIsOpen(false)
  }

  React.useEffect(() => {
    return () => clearTimeout(timeoutRef.current)
  }, [])

  const sideClasses = {
    top: '-translate-x-1/2 -translate-y-full',
    bottom: '-translate-x-1/2',
    left: '-translate-y-1/2 translate-x-0',
    right: '-translate-y-1/2 -translate-x-0',
  }

  return (
    <div
      ref={ref}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      <div ref={triggerRef}>
        {children}
      </div>
      {isOpen && (
        <div
          className={clsx(
            'fixed z-tooltip bg-text-primary text-bg-primary text-sm px-2 py-1 rounded-md shadow-lg whitespace-nowrap pointer-events-none',
            sideClasses[side]
          )}
          style={{
            top: `${position.top}px`,
            left: `${position.left}px`,
          }}
        >
          {content}
        </div>
      )}
    </div>
  )
})

Tooltip.displayName = 'Tooltip'

export default Tooltip
