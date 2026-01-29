import React from 'react'
import { clsx } from 'clsx'

const inputSizes = {
  sm: 'px-2 py-1 text-sm rounded-sm',
  md: 'px-3 py-2 text-base rounded-md',
  lg: 'px-4 py-2.5 text-lg rounded-md',
}

/**
 * Input - Text input component with focus states and validation
 * @component
 * @param {string} size - Input size: sm, md, lg
 * @param {boolean} disabled - Disable the input
 * @param {string} error - Error message to display
 * @param {string} label - Input label
 * @param {string} hint - Helper text below input
 * @param {string} placeholder - Placeholder text
 * @param {string} type - Input type: text, email, password, number, etc.
 */
const Input = React.forwardRef(({
  size = 'md',
  disabled = false,
  error,
  label,
  hint,
  className,
  type = 'text',
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
      <input
        ref={ref}
        type={type}
        disabled={disabled}
        className={clsx(
          // Base styles
          'w-full bg-bg-primary border border-border rounded transition-colors duration-fast',
          'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'placeholder:text-text-tertiary',
          // Size styles
          inputSizes[size],
          // Error state
          error && 'border-error focus:ring-error',
          className
        )}
        aria-invalid={!!error}
        aria-describedby={error ? `${props.id}-error` : hint ? `${props.id}-hint` : undefined}
        {...props}
      />
      {error && (
        <p id={`${props.id}-error`} className="mt-1 text-sm text-error">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${props.id}-hint`} className="mt-1 text-sm text-text-tertiary">
          {hint}
        </p>
      )}
    </div>
  )
})

Input.displayName = 'Input'

export default Input
