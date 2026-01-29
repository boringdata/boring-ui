import React from 'react'
import { clsx } from 'clsx'
import { isActivationKey } from '../../utils/a11y'

const buttonVariants = {
  primary: 'bg-accent text-white hover:bg-accent-hover focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring dark:focus:ring-offset-bg-primary hover:shadow-md active:scale-95',
  secondary: 'bg-bg-secondary text-text-primary hover:bg-bg-tertiary border border-border dark:text-text-primary dark:border-border focus:ring-2 focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring hover:shadow-sm active:scale-95',
  ghost: 'text-text-primary hover:bg-bg-hover dark:text-text-primary dark:hover:bg-bg-hover focus:ring-2 focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring active:scale-95',
  outline: 'border-2 border-accent text-accent hover:bg-accent-light dark:border-accent dark:text-accent focus:ring-2 focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring active:scale-95',
  danger: 'bg-error text-white hover:bg-error-hover focus:ring-2 focus:ring-error focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring dark:focus:ring-offset-bg-primary hover:shadow-md active:scale-95',
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
 * @param {string} ariaLabel - Accessibility label
 * @param {boolean} ariaPressed - Toggle button pressed state
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
  ariaLabel,
  ariaPressed,
  ...props
}, ref) => {
  const handleKeyDown = (e) => {
    // Allow Space key to activate button (in addition to Enter which is native)
    if (isActivationKey(e) && !disabled && !loading) {
      e.preventDefault()
      e.currentTarget.click()
    }
  }

  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        // Base styles
        'inline-flex items-center justify-center font-medium',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        // Variant styles
        buttonVariants[variant],
        // Size styles
        buttonSizes[size],
        // Custom classes
        className
      )}
      aria-busy={loading}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      onKeyDown={handleKeyDown}
      {...props}
    >
      {loading && (
        <span
          className="inline-block w-4 h-4 mr-2 border-2 border-current border-r-transparent rounded-full animate-spin"
          aria-hidden="true"
        />
      )}
      {icon && !iconRight && <span className={children ? 'mr-2' : ''} aria-hidden="true">{icon}</span>}
      {children}
      {icon && iconRight && <span className="ml-2" aria-hidden="true">{icon}</span>}
    </button>
  )
})

Button.displayName = 'Button'

export default Button
