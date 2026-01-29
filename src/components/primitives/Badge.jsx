import React from 'react'
import { clsx } from 'clsx'
import { X } from 'lucide-react'

const badgeVariants = {
  success: 'bg-success-bg text-success border border-success/30',
  warning: 'bg-warning-bg text-warning border border-warning/30',
  error: 'bg-error-bg text-error border border-error/30',
  info: 'bg-info-bg text-info border border-info/30',
  neutral: 'bg-neutral-bg text-text-secondary border border-border',
  violet: 'bg-violet-bg text-violet border border-violet/30',
}

const badgeSizes = {
  sm: 'px-2 py-0.5 text-xs rounded-sm',
  md: 'px-2.5 py-1 text-sm rounded-md',
  lg: 'px-3 py-1.5 text-base rounded-md',
}

/**
 * Badge - Compact label/tag component
 * @component
 * @param {string} variant - Color variant: success, warning, error, info, neutral, violet
 * @param {string} size - Badge size: sm, md, lg
 * @param {boolean} dismissible - Show close button
 * @param {function} onDismiss - Callback when dismissed
 * @param {React.ReactNode} children - Badge content
 */
const Badge = React.forwardRef(({
  variant = 'neutral',
  size = 'md',
  dismissible = false,
  onDismiss,
  children,
  className,
  ...props
}, ref) => {
  return (
    <span
      ref={ref}
      className={clsx(
        'inline-flex items-center gap-1 font-medium transition-colors',
        badgeVariants[variant],
        badgeSizes[size],
        className
      )}
      {...props}
    >
      {children}
      {dismissible && (
        <button
          onClick={onDismiss}
          className="ml-1 p-0 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
          aria-label="Dismiss badge"
        >
          <X size={size === 'sm' ? 12 : size === 'md' ? 14 : 16} />
        </button>
      )}
    </span>
  )
})

Badge.displayName = 'Badge'

export default Badge
