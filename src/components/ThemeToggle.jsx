import { useState, useEffect, useCallback } from 'react'
import { Sun, Moon } from 'lucide-react'
import { getItem, setItem, STORAGE_KEYS } from '../utils/storage'

// Default storage key for theme persistence
const DEFAULT_STORAGE_KEY = STORAGE_KEYS.THEME

/**
 * Get the system's preferred color scheme
 */
const getSystemTheme = () => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'light'
}

/**
 * Get initial theme from storage or system preference
 */
const getInitialTheme = (storageKeySuffix, defaultTheme) => {
  // Check storage first
  try {
    const stored = getItem(storageKeySuffix)
    if (stored === 'dark' || stored === 'light') {
      return stored
    }
  } catch {
    // Ignore storage errors
  }

  // If default is 'system', use system preference
  if (defaultTheme === 'system') {
    return getSystemTheme()
  }

  // Use explicit default
  return defaultTheme === 'dark' ? 'dark' : 'light'
}

/**
 * Apply theme to document
 */
const applyTheme = (theme) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

/**
 * Persist theme to storage
 */
const persistTheme = (theme, storageKeySuffix) => {
  try {
    setItem(storageKeySuffix, theme)
  } catch {
    // Ignore storage errors
  }
}

/**
 * ThemeToggle - A standalone theme toggle button component
 *
 * Can work in two modes:
 * 1. Standalone: Manages its own theme state with localStorage persistence
 * 2. Controlled: Accepts theme/onToggle props for external state management
 *
 * @param {Object} props
 * @param {Object} [props.customIcons] - Custom icons for light/dark modes
 * @param {React.ReactNode} [props.customIcons.light] - Icon to show when in dark mode (to switch to light)
 * @param {React.ReactNode} [props.customIcons.dark] - Icon to show when in light mode (to switch to dark)
 * @param {Function} [props.onChange] - Callback when theme changes: (newTheme: 'light' | 'dark') => void
 * @param {'light' | 'dark' | 'system'} [props.defaultTheme='system'] - Default theme if no preference stored
 * @param {string} [props.storageKey] - localStorage key for persisting theme preference
 * @param {'light' | 'dark'} [props.theme] - Controlled theme value (makes component controlled)
 * @param {Function} [props.onToggle] - Toggle handler for controlled mode
 * @param {string} [props.className] - Additional CSS class names
 * @param {number} [props.iconSize=16] - Size of the icons in pixels
 */
export default function ThemeToggle({
  customIcons,
  onChange,
  defaultTheme = 'system',
  storageKey = DEFAULT_STORAGE_KEY,
  theme: controlledTheme,
  onToggle,
  className = '',
  iconSize = 16,
  ...rest
}) {
  // Determine if we're in controlled mode
  const isControlled = controlledTheme !== undefined

  // Internal state for standalone mode
  const [internalTheme, setInternalTheme] = useState(() =>
    isControlled ? controlledTheme : getInitialTheme(storageKey, defaultTheme)
  )

  // Use controlled or internal theme
  const theme = isControlled ? controlledTheme : internalTheme
  const isDark = theme === 'dark'

  // Apply theme to document (standalone mode only)
  useEffect(() => {
    if (!isControlled) {
      applyTheme(theme)
    }
  }, [theme, isControlled])

  // Listen for system preference changes (standalone mode only)
  useEffect(() => {
    if (isControlled) return
    if (typeof window === 'undefined' || !window.matchMedia) return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const handleChange = (e) => {
      // Only auto-switch if user hasn't explicitly set a preference
      try {
        const stored = getItem(storageKey)
        if (!stored) {
          const newTheme = e.matches ? 'dark' : 'light'
          setInternalTheme(newTheme)
          onChange?.(newTheme)
        }
      } catch {
        // Ignore storage errors
      }
    }

    // Modern browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    }

    // Legacy browsers
    mediaQuery.addListener(handleChange)
    return () => mediaQuery.removeListener(handleChange)
  }, [isControlled, storageKey, onChange])

  // Handle theme toggle
  const handleToggle = useCallback(() => {
    if (isControlled) {
      // Controlled mode: call external handler
      onToggle?.()
    } else {
      // Standalone mode: toggle internal state
      setInternalTheme((prev) => {
        const next = prev === 'dark' ? 'light' : 'dark'
        persistTheme(next, storageKey)
        onChange?.(next)
        return next
      })
    }
  }, [isControlled, onToggle, storageKey, onChange])

  // Determine which icons to use
  const LightIcon = customIcons?.light ?? <Sun size={iconSize} />
  const DarkIcon = customIcons?.dark ?? <Moon size={iconSize} />

  // Combine class names
  const combinedClassName = `theme-toggle${className ? ` ${className}` : ''}`

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={combinedClassName}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={isDark}
      {...rest}
    >
      {isDark ? LightIcon : DarkIcon}
    </button>
  )
}

// Named export for those who prefer it
export { ThemeToggle }
