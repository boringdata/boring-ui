import React from 'react';
import { clsx } from 'clsx';
import '../../../styles/spinner.css';

/**
 * Spinner Component
 * Animated loading spinner with multiple size and color variants
 *
 * @component
 * @example
 * ```jsx
 * <Spinner />
 * <Spinner size="lg" color="primary" />
 * <Spinner size="sm" color="success" />
 * ```
 */
const Spinner = React.forwardRef(({
  size = 'md',
  color = 'primary',
  className,
  label = 'Loading',
  ...props
}, ref) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  const colorClasses = {
    primary: 'text-primary',
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-error',
    info: 'text-info',
    muted: 'text-foreground/50',
  };

  return (
    <div
      ref={ref}
      className={clsx(
        'spinner',
        sizeClasses[size],
        colorClasses[color],
        className
      )}
      role="status"
      aria-label={label}
      {...props}
    >
      <svg
        className="animate-spin w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </div>
  );
});

Spinner.displayName = 'Spinner';

export default Spinner;
