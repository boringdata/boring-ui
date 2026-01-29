import React, { createContext, useCallback, useState } from 'react';
import Toast from '../components/Toast';

/**
 * ToastContext
 * Manages toast notifications with queue management
 */
export const ToastContext = createContext(null);

/**
 * ToastProvider Component
 * Wraps application to provide toast functionality
 *
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @param {number} props.maxToasts - Maximum visible toasts (default: 3)
 * @param {Object} props.position - Position on screen (default: { top: '1rem', right: '1rem' })
 *
 * @example
 * ```jsx
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 * ```
 */
export function ToastProvider({
  children,
  maxToasts = 3,
  position = { top: '1rem', right: '1rem' },
}) {
  const [toasts, setToasts] = useState([]);

  // Add a new toast
  const addToast = useCallback(({
    id = Date.now().toString(),
    type = 'info',
    title,
    message,
    duration = 3000,
    action,
    dismissible = true,
  }) => {
    const newToast = {
      id,
      type,
      title,
      message,
      duration,
      action,
      dismissible,
    };

    setToasts(prev => {
      const updated = [newToast, ...prev];
      // Keep only maxToasts
      return updated.slice(0, maxToasts);
    });

    return id;
  }, [maxToasts]);

  // Remove a toast
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  // Clear all toasts
  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  // Convenience methods
  const success = useCallback((title, message, options = {}) => {
    return addToast({
      ...options,
      type: 'success',
      title,
      message,
    });
  }, [addToast]);

  const error = useCallback((title, message, options = {}) => {
    return addToast({
      ...options,
      type: 'error',
      title,
      message,
      duration: options.duration || 5000, // Errors stay longer
    });
  }, [addToast]);

  const warning = useCallback((title, message, options = {}) => {
    return addToast({
      ...options,
      type: 'warning',
      title,
      message,
    });
  }, [addToast]);

  const info = useCallback((title, message, options = {}) => {
    return addToast({
      ...options,
      type: 'info',
      title,
      message,
    });
  }, [addToast]);

  const value = {
    toasts,
    addToast,
    removeToast,
    clearToasts,
    success,
    error,
    warning,
    info,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="fixed z-50 pointer-events-none"
        style={{
          top: position.top,
          right: position.right,
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
      >
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            {...toast}
            onClose={removeToast}
            className="pointer-events-auto"
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export default ToastContext;
