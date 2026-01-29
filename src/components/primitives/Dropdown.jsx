import React, { useState, useRef, useEffect } from 'react'
import { clsx } from 'clsx'
import { ChevronDown } from 'lucide-react'

/**
 * Dropdown - Dropdown menu component
 * @component
 * @param {React.ReactNode} trigger - Trigger element or button
 * @param {Array} items - Array of {label, onClick, icon, divider} menu items
 * @param {string} align - Menu alignment: left, right, center
 * @param {boolean} closeOnClick - Close menu after item click
 * @param {React.ReactNode} children - Menu items as children
 */
const Dropdown = React.forwardRef(({
  trigger,
  items = [],
  align = 'left',
  closeOnClick = true,
  children,
  className,
  ...props
}, ref) => {
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        menuRef.current &&
        triggerRef.current &&
        !menuRef.current.contains(e.target) &&
        !triggerRef.current.contains(e.target)
      ) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleItemClick = (onClick) => {
    onClick?.()
    if (closeOnClick) setIsOpen(false)
  }

  const alignClasses = {
    left: 'left-0',
    right: 'right-0',
    center: 'left-1/2 -translate-x-1/2',
  }

  return (
    <div ref={ref} className="relative inline-block" {...props}>
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'inline-flex items-center justify-center gap-2',
          isOpen && 'opacity-70'
        )}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        {trigger}
        {!trigger && <ChevronDown size={16} />}
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          role="menu"
          className={clsx(
            'absolute z-dropdown mt-1 bg-bg-primary border border-border rounded-md shadow-md py-1 min-w-max',
            alignClasses[align],
            className
          )}
        >
          {children || items.map((item, index) => {
            if (item.divider) {
              return <div key={index} className="border-t border-border my-1" />
            }

            return (
              <button
                key={index}
                role="menuitem"
                onClick={() => handleItemClick(item.onClick)}
                className="w-full text-left px-4 py-2 hover:bg-bg-hover transition-colors text-sm text-text-primary flex items-center gap-2"
              >
                {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                <span>{item.label}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
})

Dropdown.displayName = 'Dropdown'

export default Dropdown
