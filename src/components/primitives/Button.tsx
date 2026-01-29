import React from 'react';
import { clsx } from 'clsx';
import { isActivationKey } from '../../utils/a11y';
import type { ButtonProps } from '../../types';

const buttonVariants = {
  primary: 'bg-accent text-white hover:bg-accent-hover focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring dark:focus:ring-offset-bg-primary hover:shadow-md active:scale-95',
  secondary: 'bg-bg-secondary text-text-primary hover:bg-bg-tertiary border border-border dark:text-text-primary dark:border-border focus:ring-2 focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring hover:shadow-sm active:scale-95',
  tertiary: 'text-text-primary hover:bg-bg-hover dark:text-text-primary dark:hover:bg-bg-hover focus:ring-2 focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring active:scale-95',
  danger: 'bg-error text-white hover:bg-error-hover focus:ring-2 focus:ring-error focus:ring-offset-2 focus:outline-none focus-visible:ring-2 transition-all duration-150 ease-spring dark:focus:ring-offset-bg-primary hover:shadow-md active:scale-95',
} as const;

const buttonSizes = {
  sm: 'px-3 py-1.5 text-sm rounded-md',
  md: 'px-4 py-2 text-base rounded-md',
  lg: 'px-5 py-2.5 text-lg rounded-lg',
} as const;

export interface ButtonExtendedProps extends ButtonProps {
  icon?: React.ReactNode;
  iconRight?: boolean;
  ariaLabel?: string;
  ariaPressed?: boolean;
}

/**
 * Button Component
 * Reusable button with variants and sizes
 *
 * @component
 * @example
 * ```tsx
 * <Button variant="primary" size="md">
 *   Click me
 * </Button>
 * ```
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonExtendedProps>(
  ({
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
    onClick,
    type = 'button',
    ...props
  }, ref) => {
    const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
      // Allow Space key to activate button (in addition to Enter which is native)
      if (isActivationKey(e) && !disabled && !loading) {
        e.preventDefault();
        (e.currentTarget as HTMLButtonElement).click();
      }
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        type={type}
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
        onClick={onClick}
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
    );
  }
);

Button.displayName = 'Button';

export default Button;
