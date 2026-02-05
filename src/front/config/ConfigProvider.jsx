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
    if (!config.styles) return

    const root = document.documentElement

    // Apply light theme styles
    const lightStyles = config.styles.light || {}
    for (const [key, value] of Object.entries(lightStyles)) {
      const cssVar = `--config-${key}`
      root.style.setProperty(cssVar, value)
    }

    // Dark theme styles are handled via data-theme attribute in CSS
    // We'll set them as custom properties that can be used in [data-theme="dark"]
    const darkStyles = config.styles.dark || {}
    for (const [key, value] of Object.entries(darkStyles)) {
      const cssVar = `--config-dark-${key}`
      root.style.setProperty(cssVar, value)
    }
  }, [config.styles])

  return (
    <ConfigContext.Provider value={{ config, loaded: true }}>
      {children}
    </ConfigContext.Provider>
  )
}

export default ConfigProvider
