/**
 * React context provider for app configuration.
 *
 * Provides access to the merged app config throughout the component tree.
 */
import { createContext, useContext, useEffect, useMemo } from 'react'
import { setConfig, getDefaultConfig } from './appConfig'

const ConfigContext = createContext(null)

/**
 * Hook to access the app configuration.
 *
 * @returns {object} The app configuration
 * @throws If used outside ConfigProvider
 */
export function useConfig() {
  const context = useContext(ConfigContext)
  if (!context) {
    throw new Error('useConfig must be used within a ConfigProvider')
  }
  return context.config
}

/**
 * Hook to check if config is loaded.
 *
 * @returns {boolean} True if config is loaded
 */
export function useConfigLoaded() {
  const context = useContext(ConfigContext)
  return context?.loaded ?? false
}

/**
 * Provider component for app configuration.
 *
 * Merges provided config with defaults and provides it to children.
 *
 * @param {object} props
 * @param {React.ReactNode} props.children
 * @param {object} [props.config] - Optional config to merge with defaults
 */
export function ConfigProvider({ children, config: providedConfig }) {
  // Merge provided config with defaults
  const config = useMemo(() => {
    if (providedConfig) {
      return setConfig(providedConfig)
    }
    return getDefaultConfig()
  }, [providedConfig])

  // Apply style tokens to CSS variables when config loads
  useEffect(() => {
    const root = document.documentElement

    // Map config token keys to CSS variable names
    const tokenToVar = {
      // Accent colors
      accent: '--color-accent',
      accentHover: '--color-accent-hover',
      accentLight: '--color-accent-light',
      // Typography
      fontSans: '--font-sans',
      fontMono: '--font-mono',
    }

    // Apply light theme styles (directly to :root)
    const lightStyles = config.styles?.light || {}
    for (const [key, value] of Object.entries(lightStyles)) {
      const cssVar = tokenToVar[key]
      if (cssVar && value) {
        root.style.setProperty(cssVar, value)
      }
    }

    // For dark theme, we need to apply styles conditionally
    // Store dark values as data attributes for CSS to pick up
    const darkStyles = config.styles?.dark || {}
    for (const [key, value] of Object.entries(darkStyles)) {
      const cssVar = tokenToVar[key]
      if (cssVar && value) {
        // Store dark mode value as a data attribute
        root.dataset[`dark${key.charAt(0).toUpperCase() + key.slice(1)}`] = value
      }
    }

    // Apply dark styles when theme changes
    const applyDarkStyles = () => {
      const isDark = root.getAttribute('data-theme') === 'dark'
      for (const [key, value] of Object.entries(darkStyles)) {
        const cssVar = tokenToVar[key]
        if (cssVar && value && isDark) {
          root.style.setProperty(cssVar, value)
        } else if (cssVar && lightStyles[key]) {
          root.style.setProperty(cssVar, lightStyles[key])
        }
      }
    }

    // Apply on initial load and observe theme changes
    applyDarkStyles()
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.attributeName === 'data-theme') {
          applyDarkStyles()
        }
      }
    })
    observer.observe(root, { attributes: true })

    return () => observer.disconnect()
  }, [config.styles])

  return (
    <ConfigContext.Provider value={{ config, loaded: true }}>
      {children}
    </ConfigContext.Provider>
  )
}

export default ConfigProvider
