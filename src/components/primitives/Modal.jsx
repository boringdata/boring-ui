import React, { useEffect } from 'react'
import { clsx } from 'clsx'
import { X } from 'lucide-react'

/**
 * Modal - Dialog box component with backdrop
 * @component
 * @param {boolean} isOpen - Modal open state
 * @param {function} onClose - Callback when modal should close
 * @param {string} title - Modal title
 * @param {React.ReactNode} children - Modal content
 * @param {React.ReactNode} footer - Modal footer (buttons, etc)
 * @param {boolean} closeOnBackdropClick - Close when clicking backdrop
 * @param {boolean} closeOnEsc - Close when pressing Escape
 * @param {string} size - Modal size: sm, md, lg, xl
 */
const Modal = React.forwardRef(({
  isOpen = false,
  onClose,
  title,
  children,
  footer,
  closeOnBackdropClick = true,
  closeOnEsc = true,
  size = 'md',
  className,
  ...props
}, ref) => {
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  }

  useEffect(() => {
    const handleEsc = (e) => {
      if (closeOnEsc && e.key === 'Escape') {
        onClose?.()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEsc)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [isOpen, closeOnEsc, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-modal flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 transition-opacity"
        onClick={closeOnBackdropClick ? onClose : undefined}
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={clsx(
          'relative bg-bg-primary rounded-lg shadow-xl max-w-[90vw] w-full',
          sizeClasses[size],
          'animate-in fade-in zoom-in-95 duration-normal',
          className
        )}
        {...props}
      >
        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <h2 id="modal-title" className="text-lg font-semibold text-text-primary">
              {title}
            </h2>
            <button
              onClick={onClose}
              className="p-1 rounded-md hover:bg-bg-hover transition-colors"
              aria-label="Close modal"
            >
              <X size={20} className="text-text-secondary" />
            </button>
          </div>
        )}

        {/* Body */}
        <div className="px-6 py-4">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="px-6 py-4 border-t border-border bg-bg-secondary rounded-b-lg">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
})

Modal.displayName = 'Modal'

export default Modal
