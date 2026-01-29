import { useState, useEffect, useCallback, createContext, useContext } from 'react'

const DEFAULT_STORAGE_KEY = 'boring-ui-theme'

// Get initial theme from localStorage or system preference
const getInitialTheme = (storageKey = DEFAULT_STORAGE_KEY, defaultTheme = 'system') => {
  // Check localStorage first
  try {
    const stored = localStorage.getItem(storageKey)
    if (stored === 'dark' || stored === 'light') {
      return stored
    }
  } catch {
    // Ignore localStorage errors
  }

  // If default is 'system' or not set, use system preference
  if (defaultTheme === 'system') {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'light'
  }

  // Use explicit default
  return defaultTheme === 'dark' ? 'dark' : 'light'
}

// Apply theme to document
const applyTheme = (theme) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

// Persist theme to localStorage
const persistTheme = (theme, storageKey = DEFAULT_STORAGE_KEY) => {
  try {
    localStorage.setItem(storageKey, theme)
  } catch {
    // Ignore localStorage errors
  }
}

// Theme context for app-wide access
const ThemeContext = createContext(null)

export function ThemeProvider({ children, storageKey = DEFAULT_STORAGE_KEY, defaultTheme = 'system' }) {
  const [theme, setTheme] = useState(() => getInitialTheme(storageKey, defaultTheme))

  // Apply theme on mount and when it changes
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  // Enable smooth theme transitions after initial render
  useEffect(() => {
    // Small delay to ensure initial render is complete without transitions
    const timer = setTimeout(() => {
      document.documentElement.classList.add('theme-transition')
    }, 100)
    return () => clearTimeout(timer)
  }, [])

  // Listen for system preference changes
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const handleChange = (e) => {
      // Only auto-switch if user hasn't explicitly set a preference
      try {
        const stored = localStorage.getItem(storageKey)
        if (!stored) {
          const newTheme = e.matches ? 'dark' : 'light'
          setTheme(newTheme)
        }
      } catch {
        // Ignore localStorage errors
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
  }, [storageKey])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      persistTheme(next, storageKey)
      return next
    })
  }, [storageKey])

  const setThemeExplicit = useCallback((newTheme) => {
    if (newTheme === 'dark' || newTheme === 'light') {
      setTheme(newTheme)
      persistTheme(newTheme, storageKey)
    }
  }, [storageKey])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme: setThemeExplicit }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

// Export utilities for standalone usage
export { getInitialTheme, applyTheme, persistTheme, DEFAULT_STORAGE_KEY }

// Initialize theme immediately to prevent flash
// This runs before React hydration
if (typeof document !== 'undefined') {
  applyTheme(getInitialTheme())
}
