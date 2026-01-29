import React, { useEffect, useMemo } from 'react'
import { defaultTokens } from './defaults'

/**
 * Map token names to CSS variable names
 * Converts camelCase token names to kebab-case CSS variables
 */
const mapTokensToCSSVariables = (tokens, mode) => {
  const cssVars = {}
  for (const [key, value] of Object.entries(tokens)) {
    if (value === undefined || value === null) continue
    // Convert camelCase to kebab-case: accentHover -> accent-hover
    const cssVarName = `--color-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`
    cssVars[cssVarName] = value
  }
  return cssVars
}

/**
 * Merge partial token overrides with defaults
 * Allows partial customization while falling back to defaults
 */
const mergeTokens = (defaults, overrides) => {
  if (!overrides) return defaults
  return { ...defaults, ...overrides }
}

/**
 * StyleProvider - Injects custom design tokens as CSS variables
 *
 * Accepts optional `light` and `dark` token overrides via config.
 * Merged tokens are applied to :root and [data-theme="dark"] CSS selectors.
 * Falls back to default tokens from tokens.css if no overrides provided.
 *
 * @param {Object} props
 * @param {Object} [props.styles] - Styles configuration { light: {...}, dark: {...} }
 * @param {React.ReactNode} props.children - Child components
 *
 * @example
 * <StyleProvider styles={{ light: { accent: '#8b5cf6' }, dark: { accent: '#a78bfa' } }}>
 *   <App />
 * </StyleProvider>
 */
export function StyleProvider({ styles, children }) {
  // Merge configured styles with defaults
  const mergedTokens = useMemo(() => ({
    light: mergeTokens(defaultTokens.light, styles?.light),
    dark: mergeTokens(defaultTokens.dark, styles?.dark),
  }), [styles])

  // Apply tokens to document on mount and when config changes
  useEffect(() => {
    const root = document.documentElement

    // Create light mode CSS variables
    const lightVars = mapTokensToCSSVariables(mergedTokens.light)

    // Create dark mode CSS variables (apply to data-theme="dark")
    const darkVars = mapTokensToCSSVariables(mergedTokens.dark)

    // Apply light mode variables to :root
    Object.entries(lightVars).forEach(([varName, value]) => {
      root.style.setProperty(varName, value)
    })

    // Create a style element for dark mode overrides
    let darkStyle = document.getElementById('boring-ui-dark-theme-overrides')
    if (!darkStyle) {
      darkStyle = document.createElement('style')
      darkStyle.id = 'boring-ui-dark-theme-overrides'
      document.head.appendChild(darkStyle)
    }

    // Build CSS for dark mode selector
    const darkCSS = Object.entries(darkVars)
      .map(([varName, value]) => `  ${varName}: ${value};`)
      .join('\n')

    darkStyle.textContent = `[data-theme="dark"] {\n${darkCSS}\n}`

    return () => {
      // Cleanup: remove injected style on unmount
      if (darkStyle && darkStyle.parentNode) {
        darkStyle.parentNode.removeChild(darkStyle)
      }
    }
  }, [mergedTokens])

  return <>{children}</>
}

export default StyleProvider
