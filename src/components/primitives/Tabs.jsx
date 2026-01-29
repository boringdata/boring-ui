import React, { useState } from 'react'
import { clsx } from 'clsx'

/**
 * Tabs - Tabbed content component with keyboard navigation
 * @component
 * @param {Array} tabs - Array of {label, content} tabs
 * @param {number} defaultTabIndex - Default tab index
 * @param {function} onChange - Callback when tab changes
 * @param {string} variant - Tab style: underline, pills, buttons
 */
const Tabs = React.forwardRef(({
  tabs = [],
  defaultTabIndex = 0,
  onChange,
  variant = 'underline',
  className,
  ...props
}, ref) => {
  const [activeIndex, setActiveIndex] = useState(defaultTabIndex)

  const handleTabClick = (index) => {
    setActiveIndex(index)
    onChange?.(index)
  }

  const handleKeyDown = (e, index) => {
    const isLeftKey = e.key === 'ArrowLeft'
    const isRightKey = e.key === 'ArrowRight'
    const isHomeKey = e.key === 'Home'
    const isEndKey = e.key === 'End'

    if (isLeftKey) {
      const prevIndex = index === 0 ? tabs.length - 1 : index - 1
      handleTabClick(prevIndex)
    } else if (isRightKey) {
      const nextIndex = index === tabs.length - 1 ? 0 : index + 1
      handleTabClick(nextIndex)
    } else if (isHomeKey) {
      handleTabClick(0)
    } else if (isEndKey) {
      handleTabClick(tabs.length - 1)
    }
  }

  const baseStyles = {
    underline: {
      tab: 'pb-2 border-b-2 transition-colors',
      active: 'border-accent text-accent',
      inactive: 'border-transparent text-text-secondary hover:text-text-primary',
    },
    pills: {
      tab: 'px-3 py-1.5 rounded-full transition-colors',
      active: 'bg-accent text-white',
      inactive: 'bg-bg-tertiary text-text-primary hover:bg-bg-hover',
    },
    buttons: {
      tab: 'px-4 py-2 rounded-md transition-colors border',
      active: 'border-accent bg-accent text-white',
      inactive: 'border-border text-text-primary hover:bg-bg-hover',
    },
  }

  const styles = baseStyles[variant]

  return (
    <div ref={ref} {...props}>
      <div
        role="tablist"
        className={clsx(
          'flex gap-2',
          variant === 'underline' && 'border-b border-border',
          className
        )}
      >
        {tabs.map((tab, index) => (
          <button
            key={index}
            role="tab"
            aria-selected={activeIndex === index}
            aria-controls={`tab-panel-${index}`}
            tabIndex={activeIndex === index ? 0 : -1}
            onClick={() => handleTabClick(index)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={clsx(
              'font-medium text-sm',
              styles.tab,
              activeIndex === index ? styles.active : styles.inactive
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab, index) => (
        <div
          key={index}
          id={`tab-panel-${index}`}
          role="tabpanel"
          aria-labelledby={`tab-${index}`}
          hidden={activeIndex !== index}
          className="py-4"
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
})

Tabs.displayName = 'Tabs'

export default Tabs
