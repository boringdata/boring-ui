/**
 * useChatTheme Hook
 * Comprehensive theme management for chat interface
 * Supports multiple color themes, font sizing, line height, and code themes
 * Persists preferences to localStorage
 */

import { useState, useCallback, useEffect, useContext, createContext } from 'react'
import { getItem, setItem, STORAGE_KEYS } from '../utils/storage'

/**
 * Available color themes
 * @type {Array<string>}
 */
const AVAILABLE_THEMES = ['default', 'monokai', 'solarized', 'dracula', 'nord']

/**
 * Available code themes (10+ schemes)
 * @type {Array<string>}
 */
const AVAILABLE_CODE_THEMES = [
  'default',
  'atom-dark',
  'atom-light',
  'github-dark',
  'github-light',
  'vscode-dark',
  'vscode-light',
  'one-dark-pro',
  'panda',
  'synthwave',
  'material-palenight',
  'dracula-code'
]

/**
 * Available font sizes (6 options)
 * @type {Array<number>}
 */
const AVAILABLE_FONT_SIZES = [1, 2, 3, 4, 5, 6]

/**
 * Available line height options
 * @type {Array<string>}
 */
const AVAILABLE_LINE_HEIGHTS = ['compact', 'normal', 'spacious']

/**
 * Default theme configuration
 */
const DEFAULT_CHAT_THEME_CONFIG = {
  colorTheme: 'default',
  fontSize: 3,
  lineHeight: 'normal',
  codeTheme: 'default',
  highContrast: false,
  accentColor: null,
  systemTheme: true,
  darkMode: null, // null = system, true = dark, false = light
}

/**
 * Storage key for chat theme preferences
 */
const CHAT_THEME_STORAGE_KEY = STORAGE_KEYS.CHAT_THEME || 'chat-theme-config'

/**
 * Chat Theme Context
 */
const ChatThemeContext = createContext(null)

/**
 * Get initial theme configuration from storage
 * @returns {Object} Theme configuration object
 */
const getInitialChatThemeConfig = () => {
  try {
    const stored = getItem(CHAT_THEME_STORAGE_KEY)
    if (stored) {
      const parsed = typeof stored === 'string' ? JSON.parse(stored) : stored
      return {
        ...DEFAULT_CHAT_THEME_CONFIG,
        ...parsed
      }
    }
  } catch {
    // Ignore storage errors, use defaults
  }

  return DEFAULT_CHAT_THEME_CONFIG
}

/**
 * Determine current dark mode setting
 * @param {Object} config Theme configuration
 * @returns {boolean} Whether dark mode is active
 */
const isDarkMode = (config) => {
  if (config.darkMode !== null) {
    return config.darkMode === true
  }

  // System preference
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  return false
}

/**
 * Apply theme configuration to DOM
 * @param {Object} config Theme configuration
 */
const applyThemeConfig = (config) => {
  if (typeof document === 'undefined') return

  const root = document.documentElement

  // Set color theme
  root.setAttribute('data-chat-theme', config.colorTheme)

  // Set dark/light mode
  const mode = isDarkMode(config) ? 'dark' : 'light'
  root.setAttribute('data-theme', mode)

  // Set font size
  root.setAttribute('data-chat-font-size', config.fontSize)

  // Set line height
  root.setAttribute('data-chat-line-height', config.lineHeight)

  // Set code theme
  root.setAttribute('data-code-theme', config.codeTheme)

  // Set high contrast mode
  if (config.highContrast) {
    root.setAttribute('data-chat-high-contrast', 'true')
  } else {
    root.removeAttribute('data-chat-high-contrast')
  }

  // Set custom accent color if provided
  if (config.accentColor) {
    root.style.setProperty('--chat-accent-color', config.accentColor)
  } else {
    root.style.removeProperty('--chat-accent-color')
  }
}

/**
 * Persist theme configuration to storage
 * @param {Object} config Theme configuration
 */
const persistChatThemeConfig = (config) => {
  try {
    setItem(CHAT_THEME_STORAGE_KEY, JSON.stringify(config))
  } catch {
    // Ignore storage errors
    console.warn('Failed to persist chat theme configuration')
  }
}

/**
 * useChatTheme Hook
 * Manages comprehensive theme customization
 *
 * @returns {Object} Theme state and control functions
 *  - colorTheme: Current color theme name
 *  - fontSize: Current font size (1-6)
 *  - lineHeight: Current line height (compact/normal/spacious)
 *  - codeTheme: Current code theme name
 *  - highContrast: Whether high contrast mode is enabled
 *  - accentColor: Custom accent color (hex) or null
 *  - darkMode: Dark mode setting (null=system, true=dark, false=light)
 *  - setColorTheme: Function to change color theme
 *  - setFontSize: Function to change font size (1-6)
 *  - setLineHeight: Function to change line height
 *  - setCodeTheme: Function to change code theme
 *  - setHighContrast: Function to toggle high contrast mode
 *  - setAccentColor: Function to set custom accent color
 *  - setDarkMode: Function to set dark mode (null/true/false)
 *  - toggleDarkMode: Function to toggle dark/light mode
 *  - resetToDefaults: Function to reset all settings
 *  - isDarkMode: Whether dark mode is currently active
 */
export function useChatTheme() {
  const [config, setConfig] = useState(() => getInitialChatThemeConfig())

  // Calculate derived dark mode state
  const isCurrentlyDarkMode = isDarkMode(config)

  /**
   * Change color theme
   * @param {string} theme Color theme name (one of AVAILABLE_THEMES)
   */
  const setColorTheme = useCallback((theme) => {
    if (!AVAILABLE_THEMES.includes(theme)) {
      console.warn(`Invalid color theme: ${theme}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, colorTheme: theme }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Change font size
   * @param {number} size Font size level (1-6)
   */
  const setFontSize = useCallback((size) => {
    if (!AVAILABLE_FONT_SIZES.includes(size)) {
      console.warn(`Invalid font size: ${size}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, fontSize: size }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Change line height
   * @param {string} height Line height option (compact/normal/spacious)
   */
  const setLineHeight = useCallback((height) => {
    if (!AVAILABLE_LINE_HEIGHTS.includes(height)) {
      console.warn(`Invalid line height: ${height}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, lineHeight: height }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Change code theme
   * @param {string} theme Code theme name (one of AVAILABLE_CODE_THEMES)
   */
  const setCodeTheme = useCallback((theme) => {
    if (!AVAILABLE_CODE_THEMES.includes(theme)) {
      console.warn(`Invalid code theme: ${theme}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, codeTheme: theme }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Toggle high contrast mode
   * @param {boolean} enabled Whether to enable high contrast mode
   */
  const setHighContrast = useCallback((enabled) => {
    setConfig((prev) => {
      const updated = { ...prev, highContrast: !!enabled }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Set custom accent color
   * @param {string|null} color Hex color value or null to reset
   */
  const setAccentColor = useCallback((color) => {
    // Validate hex color format (simple validation)
    if (color !== null && !/^#[0-9a-f]{6}$/i.test(color)) {
      console.warn(`Invalid hex color: ${color}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, accentColor: color }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Set dark mode
   * @param {boolean|null} mode Dark mode setting (true=dark, false=light, null=system)
   */
  const setDarkMode = useCallback((mode) => {
    if (mode !== null && mode !== true && mode !== false) {
      console.warn(`Invalid dark mode value: ${mode}`)
      return
    }

    setConfig((prev) => {
      const updated = { ...prev, darkMode: mode }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Toggle between dark and light modes
   */
  const toggleDarkMode = useCallback(() => {
    setConfig((prev) => {
      // If system preference was being used, switch to explicit dark
      // Otherwise toggle the current explicit setting
      let newMode = true
      if (prev.darkMode === true) {
        newMode = false
      } else if (prev.darkMode === false) {
        newMode = null // Back to system
      }

      const updated = { ...prev, darkMode: newMode }
      applyThemeConfig(updated)
      persistChatThemeConfig(updated)
      return updated
    })
  }, [])

  /**
   * Reset all settings to defaults
   */
  const resetToDefaults = useCallback(() => {
    setConfig(DEFAULT_CHAT_THEME_CONFIG)
    applyThemeConfig(DEFAULT_CHAT_THEME_CONFIG)
    persistChatThemeConfig(DEFAULT_CHAT_THEME_CONFIG)
  }, [])

  // Apply theme config on mount
  useEffect(() => {
    applyThemeConfig(config)
  }, [])

  // Listen for system theme preference changes
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia || config.darkMode !== null) {
      return
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const handleChange = (e) => {
      setConfig((prev) => {
        const updated = { ...prev }
        applyThemeConfig(updated)
        return updated
      })
    }

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    }

    mediaQuery.addListener(handleChange)
    return () => mediaQuery.removeListener(handleChange)
  }, [config.darkMode])

  return {
    // State
    colorTheme: config.colorTheme,
    fontSize: config.fontSize,
    lineHeight: config.lineHeight,
    codeTheme: config.codeTheme,
    highContrast: config.highContrast,
    accentColor: config.accentColor,
    darkMode: config.darkMode,
    isDarkMode: isCurrentlyDarkMode,

    // Actions
    setColorTheme,
    setFontSize,
    setLineHeight,
    setCodeTheme,
    setHighContrast,
    setAccentColor,
    setDarkMode,
    toggleDarkMode,
    resetToDefaults,

    // Constants
    availableColorThemes: AVAILABLE_THEMES,
    availableCodeThemes: AVAILABLE_CODE_THEMES,
    availableFontSizes: AVAILABLE_FONT_SIZES,
    availableLineHeights: AVAILABLE_LINE_HEIGHTS,
  }
}

/**
 * Provider component for chat theme context
 */
export function ChatThemeProvider({ children }) {
  const theme = useChatTheme()

  return (
    <ChatThemeContext.Provider value={theme}>
      {children}
    </ChatThemeContext.Provider>
  )
}

/**
 * Hook to use chat theme from context
 * Must be used within ChatThemeProvider
 */
export function useChatThemeContext() {
  const context = useContext(ChatThemeContext)
  if (!context) {
    throw new Error('useChatThemeContext must be used within ChatThemeProvider')
  }
  return context
}

/**
 * Export constants for external use
 */
export {
  AVAILABLE_THEMES,
  AVAILABLE_CODE_THEMES,
  AVAILABLE_FONT_SIZES,
  AVAILABLE_LINE_HEIGHTS,
  DEFAULT_CHAT_THEME_CONFIG,
}
