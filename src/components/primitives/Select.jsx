import React from 'react'
import { clsx } from 'clsx'
import { ChevronDown } from 'lucide-react'

const selectSizes = {
  sm: 'px-2 py-1 text-sm',
  md: 'px-3 py-2 text-base',
  lg: 'px-4 py-2.5 text-lg',
}

/**
 * Select - Dropdown select component
 * @component
 * @param {string} size - Select size: sm, md, lg
 * @param {boolean} disabled - Disable the select
 * @param {string} error - Error message
 * @param {string} label - Select label
 * @param {string} placeholder - Placeholder text
 * @param {Array} options - Array of {label, value} options
 */
const Select = React.forwardRef(({
  size = 'md',
  disabled = false,
  error,
  label,
  placeholder = 'Select an option...',
  options = [],
  children,
  className,
  ...props
}, ref) => {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-text-primary mb-1">
          {label}
          {props.required && <span className="text-error ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          disabled={disabled}
          className={clsx(
            // Base styles
            'w-full appearance-none bg-bg-primary border border-border rounded transition-colors duration-fast',
            'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'pr-10', // Space for chevron icon
            // Size styles
            selectSizes[size],
            // Error state
            error && 'border-error focus:ring-error',
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${props.id}-error` : undefined}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
          {children}
        </select>
        <ChevronDown
          size={16}
          className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-text-secondary"
        />
      </div>
      {error && (
        <p id={`${props.id}-error`} className="mt-1 text-sm text-error">
          {error}
        </p>
      )}
    </div>
  )
})

Select.displayName = 'Select'

export default Select
