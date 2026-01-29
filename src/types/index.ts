/**
 * Centralized Type Definitions
 * All type interfaces for the boring-ui application
 */

// ============================================================================
// Component Props
// ============================================================================

/**
 * Common component props
 */
export interface BaseComponentProps {
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

/**
 * Size variants for components
 */
export type SizeVariant = 'sm' | 'md' | 'lg';

/**
 * Color variants for components
 */
export type ColorVariant = 'primary' | 'success' | 'warning' | 'error' | 'info' | 'muted';

/**
 * Button variants
 */
export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'danger';

/**
 * Alert variants
 */
export type AlertVariant = 'success' | 'error' | 'warning' | 'info';

/**
 * Toast types (same as alerts)
 */
export type ToastType = AlertVariant;

/**
 * Common button props
 */
export interface ButtonProps extends BaseComponentProps {
  variant?: ButtonVariant;
  size?: SizeVariant;
  disabled?: boolean;
  loading?: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  type?: 'button' | 'submit' | 'reset';
  children: React.ReactNode;
}

/**
 * Badge props
 */
export interface BadgeProps extends BaseComponentProps {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  label?: string;
  icon?: React.ReactNode;
}

/**
 * Card props
 */
export interface CardProps extends BaseComponentProps {
  variant?: 'default' | 'elevated' | 'outlined';
  header?: React.ReactNode;
  footer?: React.ReactNode;
  interactive?: boolean;
}

/**
 * Alert props
 */
export interface AlertProps extends BaseComponentProps {
  variant?: AlertVariant;
  title?: string;
  description?: string;
  dismissible?: boolean;
  onDismiss?: () => void;
}

/**
 * Input props
 */
export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  hint?: string;
  size?: SizeVariant;
  icon?: React.ReactNode;
}

/**
 * Select props
 */
export interface SelectProps extends BaseComponentProps {
  options: Array<{ value: string | number; label: string }>;
  value?: string | number;
  onChange?: (value: string | number) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
}

/**
 * Modal props
 */
export interface ModalProps extends BaseComponentProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg';
  closeButton?: boolean;
}

/**
 * Tooltip props
 */
export interface TooltipProps extends BaseComponentProps {
  content: React.ReactNode;
  position?: 'top' | 'right' | 'bottom' | 'left';
  delay?: number;
  children: React.ReactNode;
}

/**
 * Dropdown props
 */
export interface DropdownProps extends BaseComponentProps {
  items: Array<{ label: string; value: string; icon?: React.ReactNode }>;
  onSelect?: (value: string) => void;
  trigger?: React.ReactNode;
}

/**
 * Tabs props
 */
export interface TabsProps extends BaseComponentProps {
  tabs: Array<{ id: string; label: string; content: React.ReactNode }>;
  defaultTab?: string;
  onChange?: (tabId: string) => void;
}

/**
 * Skeleton props
 */
export interface SkeletonProps extends BaseComponentProps {
  variant?: 'text' | 'circle' | 'box' | 'line';
  width?: string | number;
  height?: string | number;
  size?: number;
  rounded?: 'sm' | 'md' | 'lg' | 'full';
}

/**
 * Spinner props
 */
export interface SpinnerProps extends BaseComponentProps {
  size?: SizeVariant;
  color?: ColorVariant;
  label?: string;
}

/**
 * ProgressBar props
 */
export interface ProgressBarProps extends BaseComponentProps {
  value?: number;
  max?: number;
  indeterminate?: boolean;
  size?: SizeVariant;
  color?: ColorVariant;
  showLabel?: boolean;
  animated?: boolean;
}

/**
 * Toast props
 */
export interface ToastProps extends BaseComponentProps {
  id: string;
  type?: ToastType;
  title?: string;
  message?: string;
  duration?: number | false;
  onClose?: (id: string) => void;
  action?: {
    label: string;
    onClick?: () => void;
  };
  dismissible?: boolean;
}

/**
 * ErrorBoundary props
 */
export interface ErrorBoundaryProps extends BaseComponentProps {
  dismissible?: boolean;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  onReset?: () => void;
  onContactSupport?: () => void;
  title?: string;
  message?: string;
}

// ============================================================================
// API & Data
// ============================================================================

/**
 * API response structure
 */
export interface ApiResponse<T = unknown> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  response: Response | null;
}

/**
 * Git status
 */
export interface GitStatus {
  branch: string;
  hasChanges: boolean;
  stagedFiles: string[];
  unstagedFiles: string[];
  untrackedFiles: string[];
}

/**
 * Theme configuration
 */
export interface ThemeConfig {
  mode: 'light' | 'dark';
  colors?: Record<string, string>;
  fonts?: Record<string, string>;
}

// ============================================================================
// Hooks & Context
// ============================================================================

/**
 * useToast hook return type
 */
export interface ToastAPI {
  toasts: ToastProps[];
  addToast: (toast: Omit<ToastProps, 'onClose'>) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
  success: (title: string, message?: string, options?: Partial<ToastProps>) => string;
  error: (title: string, message?: string, options?: Partial<ToastProps>) => string;
  warning: (title: string, message?: string, options?: Partial<ToastProps>) => string;
  info: (title: string, message?: string, options?: Partial<ToastProps>) => string;
}

/**
 * useApi hook return type
 */
export interface UseApiReturn {
  get: <T = unknown>(path: string, options?: RequestInit) => Promise<ApiResponse<T>>;
  post: <T = unknown>(path: string, data?: unknown, options?: RequestInit) => Promise<ApiResponse<T>>;
  put: <T = unknown>(path: string, data?: unknown, options?: RequestInit) => Promise<ApiResponse<T>>;
  patch: <T = unknown>(path: string, data?: unknown, options?: RequestInit) => Promise<ApiResponse<T>>;
  delete: <T = unknown>(path: string, options?: RequestInit) => Promise<ApiResponse<T>>;
  request: <T = unknown>(path: string, options?: RequestInit) => Promise<ApiResponse<T>>;
  baseUrl: string;
}

/**
 * useResponsive hook return type
 */
export interface UseResponsiveReturn {
  currentBreakpoint: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isXs: boolean;
  isSm: boolean;
  isMd: boolean;
  isLg: boolean;
  isXl: boolean;
  is2xl: boolean;
  viewportSize: { width: number; height: number };
  width: number;
  height: number;
  hasTouch: boolean;
  darkMode: boolean;
  reducedMotion: boolean;
}

/**
 * useTheme hook return type
 */
export interface UseThemeReturn {
  mode: 'light' | 'dark';
  toggle: () => void;
  setMode: (mode: 'light' | 'dark') => void;
}

/**
 * useKeyboardShortcuts options
 */
export interface KeyboardShortcutConfig {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
  callback: (event: KeyboardEvent) => void;
}

/**
 * useHistory hook return type
 */
export interface UseHistoryReturn<T> {
  history: T[];
  currentIndex: number;
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;
  push: (value: T) => void;
  reset: () => void;
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Error type classification
 */
export type ErrorType = 'network' | 'offline' | 'timeout' | 'client_error' | 'server_error' | 'validation' | 'unknown';

/**
 * Error object with metadata
 */
export interface ErrorObject {
  message: string;
  name: string;
  type: ErrorType;
  title: string;
  userMessage: string;
  suggestions: string[];
  timestamp: string;
  context?: Record<string, unknown>;
  stack?: string;
  isRetryable: boolean;
  canDismiss: boolean;
}

// ============================================================================
// Responsive Utilities
// ============================================================================

/**
 * Breakpoint names
 */
export type BreakpointName = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';

/**
 * Viewport size
 */
export interface ViewportSize {
  width: number;
  height: number;
}

/**
 * Safe area insets
 */
export interface SafeAreaInsets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}
