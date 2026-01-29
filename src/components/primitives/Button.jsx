import React from 'react'
import { clsx } from 'clsx'

const buttonVariants = {
  primary: 'bg-accent text-white hover:bg-accent-hover focus:ring-2 focus:ring-accent focus:ring-offset-2 dark:focus:ring-offset-bg-primary',
  secondary: 'bg-bg-secondary text-text-primary hover:bg-bg-tertiary border border-border dark:text-text-primary dark:border-border',
  ghost: 'text-text-primary hover:bg-bg-hover dark:text-text-primary dark:hover:bg-bg-hover',
  outline: 'border-2 border-accent text-accent hover:bg-accent-light dark:border-accent dark:text-accent',
  danger: 'bg-error text-white hover:bg-error-hover focus:ring-2 focus:ring-error focus:ring-offset-2 dark:focus:ring-offset-bg-primary',
}

const buttonSizes = {
  xs: 'px-2 py-1 text-xs rounded-sm',
  sm: 'px-3 py-1.5 text-sm rounded-md',
  md: 'px-4 py-2 text-base rounded-md',
  lg: 'px-5 py-2.5 text-lg rounded-lg',
  xl: 'px-6 py-3 text-xl rounded-lg',
}

/**
 * Button - Reusable button component with variants and sizes
 * @component
 * @param {string} variant - Style variant: primary, secondary, ghost, outline, danger
 * @param {string} size - Button size: xs, sm, md, lg, xl
 * @param {boolean} disabled - Disable the button
 * @param {boolean} loading - Show loading state
 * @param {React.ReactNode} children - Button content
 * @param {string} className - Additional CSS classes
 * @param {React.ReactNode} icon - Icon element to display
 * @param {boolean} iconRight - Place icon on right side
 */
const Button = React.forwardRef(({
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  children,
  className,
  icon,
  iconRight = false,
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        // Base styles
        'inline-flex items-center justify-center font-medium transition-colors duration-fast',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        // Variant styles
        buttonVariants[variant],
        // Size styles
        buttonSizes[size],
        // Custom classes
        className
      )}
      aria-busy={loading}
      {...props}
    >
      {loading && (
        <span className="inline-block w-4 h-4 mr-2 border-2 border-current border-r-transparent rounded-full animate-spin" />
      )}
      {icon && !iconRight && <span className={children ? 'mr-2' : ''}>{icon}</span>}
      {children}
      {icon && iconRight && <span className="ml-2">{icon}</span>}
    </button>
  )
})

Button.displayName = 'Button'

export default Button
