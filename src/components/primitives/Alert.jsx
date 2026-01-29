import React from 'react'
import { clsx } from 'clsx'
import { AlertCircle, CheckCircle, AlertTriangle, Info, X } from 'lucide-react'

const variantConfig = {
  success: {
    bg: 'bg-success-bg',
    border: 'border-success/30',
    text: 'text-success',
    icon: CheckCircle,
  },
  warning: {
    bg: 'bg-warning-bg',
    border: 'border-warning/30',
    text: 'text-warning',
    icon: AlertTriangle,
  },
  error: {
    bg: 'bg-error-bg',
    border: 'border-error/30',
    text: 'text-error',
    icon: AlertCircle,
  },
  info: {
    bg: 'bg-info-bg',
    border: 'border-info/30',
    text: 'text-info',
    icon: Info,
  },
}

/**
 * Alert - Alert/notification box component
 * @component
 * @param {string} variant - Alert type: success, warning, error, info
 * @param {string} title - Alert title
 * @param {string} description - Alert message
 * @param {boolean} dismissible - Show close button
 * @param {function} onDismiss - Callback when dismissed
 * @param {React.ReactNode} children - Custom alert content
 */
const Alert = React.forwardRef(({
  variant = 'info',
  title,
  description,
  dismissible = true,
  onDismiss,
  children,
  className,
  ...props
}, ref) => {
  const config = variantConfig[variant]
  const Icon = config.icon

  return (
    <div
      ref={ref}
      role="alert"
      className={clsx(
        'relative border rounded-lg p-4 flex gap-3',
        config.bg,
        config.border,
        className
      )}
      {...props}
    >
      <Icon size={20} className={clsx('flex-shrink-0 mt-0.5', config.text)} />
      <div className="flex-1">
        {title && (
          <h3 className={clsx('font-semibold', config.text)}>
            {title}
          </h3>
        )}
        {(description || children) && (
          <p className={clsx('text-sm', !title && config.text)}>
            {description || children}
          </p>
        )}
      </div>
      {dismissible && (
        <button
          onClick={onDismiss}
          className={clsx('flex-shrink-0 rounded hover:bg-black/10 dark:hover:bg-white/10 p-1 transition-colors')}
          aria-label="Dismiss alert"
        >
          <X size={16} />
        </button>
      )}
    </div>
  )
})

Alert.displayName = 'Alert'

export default Alert
