import React, { useEffect } from 'react';
import { clsx } from 'clsx';
import { AlertCircle, CheckCircle, AlertTriangle, Info, X } from 'lucide-react';
import '../styles/toast.css';

/**
 * Toast Component
 * Individual toast notification with auto-dismiss capability
 *
 * @component
 * @example
 * ```jsx
 * <Toast
 *   type="success"
 *   title="Success"
 *   message="Action completed"
 *   onClose={() => {}}
 * />
 * ```
 */
const Toast = React.forwardRef(({
  id,
  type = 'info',
  title,
  message,
  duration = 3000,
  onClose,
  action,
  dismissible = true,
  ...props
}, ref) => {
  // Auto-dismiss effect
  useEffect(() => {
    if (!duration) return;

    const timer = setTimeout(() => {
      onClose?.(id);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, id, onClose]);

  // Keyboard dismiss (Escape key)
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && dismissible) {
        onClose?.(id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dismissible, id, onClose]);

  const typeConfig = {
    success: {
      bg: 'bg-success-bg',
      border: 'border-success/30',
      text: 'text-success',
      icon: CheckCircle,
    },
    error: {
      bg: 'bg-error-bg',
      border: 'border-error/30',
      text: 'text-error',
      icon: AlertCircle,
    },
    warning: {
      bg: 'bg-warning-bg',
      border: 'border-warning/30',
      text: 'text-warning',
      icon: AlertTriangle,
    },
    info: {
      bg: 'bg-info-bg',
      border: 'border-info/30',
      text: 'text-info',
      icon: Info,
    },
  };

  const config = typeConfig[type];
  const Icon = config.icon;

  return (
    <div
      ref={ref}
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      className={clsx(
        'toast',
        'border rounded-lg p-4 shadow-lg',
        'max-w-sm flex gap-3 items-start',
        'animate-slide-in bg-background',
        config.border
      )}
      {...props}
    >
      {/* Icon */}
      <Icon size={20} className={clsx('flex-shrink-0 mt-0.5', config.text)} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        {title && (
          <h3 className={clsx('font-semibold text-sm', config.text)}>
            {title}
          </h3>
        )}
        {message && (
          <p className={clsx('text-sm text-foreground/70 mt-1')}>
            {message}
          </p>
        )}
        {action && (
          <button
            onClick={() => {
              action.onClick?.();
              onClose?.(id);
            }}
            className="text-sm font-medium mt-2 hover:underline text-foreground/70 hover:text-foreground transition-colors"
          >
            {action.label}
          </button>
        )}
      </div>

      {/* Close button */}
      {dismissible && (
        <button
          onClick={() => onClose?.(id)}
          className="flex-shrink-0 rounded hover:bg-black/10 dark:hover:bg-white/10 p-1 transition-colors ml-2"
          aria-label="Dismiss notification"
        >
          <X size={16} className="text-foreground/60" />
        </button>
      )}
    </div>
  );
});

Toast.displayName = 'Toast';

export default Toast;
