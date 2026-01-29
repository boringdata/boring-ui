/**
 * Custom render utilities for testing React components
 */
import React, { ReactElement, ReactNode } from 'react'
import { render, RenderOptions, RenderResult } from '@testing-library/react'
import { ConfigProvider } from '../../config'

// Default test config with empty sections (mimics legacy behavior)
const defaultTestConfig = {
  fileTree: {
    sections: [],
    configFiles: [],
    gitPollInterval: 5000,
    treePollInterval: 3000,
  },
}

// Wrapper that can provide context providers
interface WrapperProps {
  children: ReactNode
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  wrapper?: React.ComponentType<WrapperProps>
  config?: Record<string, unknown>
}

const DefaultWrapper: React.FC<WrapperProps> = ({ children }) => {
  return <>{children}</>
}

// Create a wrapper with ConfigProvider
const createConfigWrapper = (config: Record<string, unknown> = defaultTestConfig): React.FC<WrapperProps> => {
  return function ConfigWrapper({ children }) {
    return (
      <ConfigProvider config={config}>
        {children}
      </ConfigProvider>
    )
  }
}

// Custom render function that includes any necessary providers
export function renderWithProviders(
  ui: ReactElement,
  options?: RenderWithProvidersOptions
): RenderResult {
  const { config, wrapper, ...restOptions } = options || {}
  // If a custom wrapper is provided, use it; otherwise use ConfigProvider
  const Wrapper = wrapper || createConfigWrapper(config)
  return render(ui, { wrapper: Wrapper, ...restOptions })
}

// Render with config - convenience function for components that need config
export function renderWithConfig(
  ui: ReactElement,
  config: Record<string, unknown> = defaultTestConfig,
  options?: Omit<RenderOptions, 'wrapper'>
): RenderResult {
  return render(ui, { wrapper: createConfigWrapper(config), ...options })
}

// Re-export everything from testing library
export * from '@testing-library/react'
export { renderWithProviders as render, createConfigWrapper, defaultTestConfig }
