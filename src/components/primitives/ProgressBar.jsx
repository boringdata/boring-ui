import React from 'react';
import { clsx } from 'clsx';
import '../../../styles/progressbar.css';

/**
 * ProgressBar Component
 * Displays progress with determinate or indeterminate modes
 *
 * @component
 * @example
 * ```jsx
 * <ProgressBar value={65} />
 * <ProgressBar indeterminate />
 * <ProgressBar value={75} size="sm" color="success" showLabel />
 * ```
 */
const ProgressBar = React.forwardRef(({
  value = 0,
  max = 100,
  indeterminate = false,
  size = 'md',
  color = 'primary',
  showLabel = false,
  animated = true,
  className,
  ...props
}, ref) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  const colorClasses = {
    primary: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
    error: 'bg-error',
    info: 'bg-info',
  };

  return (
    <>
      <div
        ref={ref}
        className={clsx(
          'progress-bar-container',
          'w-full bg-foreground/10 rounded-full overflow-hidden',
          sizeClasses[size],
          className
        )}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin="0"
        aria-valuemax={max}
        aria-label={`Progress: ${Math.round(percentage)}%`}
        {...props}
      >
        <div
          className={clsx(
            'progress-bar-fill',
            colorClasses[color],
            'h-full transition-all duration-300 rounded-full',
            indeterminate && animated && 'progress-bar-indeterminate'
          )}
          style={{
            width: indeterminate ? '30%' : `${percentage}%`,
          }}
        />
      </div>
      {showLabel && (
        <div className="mt-1 flex justify-between items-center text-xs">
          <span className="text-foreground/60">{percentage.toFixed(0)}%</span>
          {value} / {max}
        </div>
      )}
    </>
  );
});

ProgressBar.displayName = 'ProgressBar';

export default ProgressBar;
