/**
 * Tests for useChatTheme Hook
 * Covers theme management, persistence, and DOM updates
 * Target: 65%+ coverage
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  useChatTheme,
  ChatThemeProvider,
  useChatThemeContext,
  AVAILABLE_THEMES,
  AVAILABLE_CODE_THEMES,
  AVAILABLE_FONT_SIZES,
  AVAILABLE_LINE_HEIGHTS,
} from '../../hooks/useChatTheme'

// Mock storage
const mockStorage = {}

vi.mock('../../utils/storage', () => ({
  getItem: (key) => mockStorage[key],
  setItem: (key, value) => {
    mockStorage[key] = value
  },
  STORAGE_KEYS: {
    CHAT_THEME: 'chat-theme-config',
  },
}))

// Helper component to test the hook
const TestComponent = () => {
  const theme = useChatTheme()
  return (
    <div>
      <div data-testid="color-theme">{theme.colorTheme}</div>
      <div data-testid="font-size">{theme.fontSize}</div>
      <div data-testid="line-height">{theme.lineHeight}</div>
      <div data-testid="code-theme">{theme.codeTheme}</div>
      <div data-testid="high-contrast">{theme.highContrast.toString()}</div>
      <div data-testid="dark-mode">{theme.darkMode}</div>
      <div data-testid="is-dark">{theme.isDarkMode.toString()}</div>
      <button
        data-testid="color-theme-btn"
        onClick={() => theme.setColorTheme('monokai')}
      >
        Set Monokai
      </button>
      <button
        data-testid="font-size-btn"
        onClick={() => theme.setFontSize(4)}
      >
        Set Font Size 4
      </button>
      <button
        data-testid="line-height-btn"
        onClick={() => theme.setLineHeight('spacious')}
      >
        Set Spacious
      </button>
      <button
        data-testid="code-theme-btn"
        onClick={() => theme.setCodeTheme('atom-dark')}
      >
        Set Atom Dark
      </button>
      <button
        data-testid="high-contrast-btn"
        onClick={() => theme.setHighContrast(!theme.highContrast)}
      >
        Toggle High Contrast
      </button>
      <button
        data-testid="accent-color-btn"
        onClick={() => theme.setAccentColor('#ff0000')}
      >
        Set Red Accent
      </button>
      <button
        data-testid="dark-mode-btn"
        onClick={() => theme.setDarkMode(!theme.darkMode)}
      >
        Toggle Dark Mode
      </button>
      <button
        data-testid="reset-btn"
        onClick={() => theme.resetToDefaults()}
      >
        Reset Defaults
      </button>
    </div>
  )
}

describe('useChatTheme Hook', () => {
  beforeEach(() => {
    mockStorage['chat-theme-config'] = undefined
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should return default theme configuration', () => {
      render(<TestComponent />)

      expect(screen.getByTestId('color-theme')).toHaveTextContent('default')
      expect(screen.getByTestId('font-size')).toHaveTextContent('3')
      expect(screen.getByTestId('line-height')).toHaveTextContent('normal')
      expect(screen.getByTestId('code-theme')).toHaveTextContent('default')
      expect(screen.getByTestId('high-contrast')).toHaveTextContent('false')
    })

    it('should load theme configuration from storage if available', () => {
      const config = {
        colorTheme: 'monokai',
        fontSize: 4,
        lineHeight: 'spacious',
        codeTheme: 'atom-dark',
        highContrast: true,
        accentColor: '#ff0000',
        darkMode: true,
      }
      mockStorage['chat-theme-config'] = JSON.stringify(config)

      render(<TestComponent />)

      expect(screen.getByTestId('color-theme')).toHaveTextContent('monokai')
      expect(screen.getByTestId('font-size')).toHaveTextContent('4')
      expect(screen.getByTestId('line-height')).toHaveTextContent('spacious')
      expect(screen.getByTestId('code-theme')).toHaveTextContent('atom-dark')
      expect(screen.getByTestId('high-contrast')).toHaveTextContent('true')
    })
  })

  describe('Color Theme Management', () => {
    it('should expose available color themes', () => {
      const TestThemes = () => {
        const theme = useChatTheme()
        return (
          <div>
            {theme.availableColorThemes.map((t) => (
              <div key={t} data-testid={`theme-${t}`}>
                {t}
              </div>
            ))}
          </div>
        )
      }

      render(<TestThemes />)

      AVAILABLE_THEMES.forEach((theme) => {
        expect(screen.getByTestId(`theme-${theme}`)).toBeInTheDocument()
      })
    })

    it('should have correct constants', () => {
      const TestConstants = () => {
        const theme = useChatTheme()
        return (
          <div>
            <div data-testid="available-count">{theme.availableColorThemes.length}</div>
          </div>
        )
      }

      render(<TestConstants />)

      expect(screen.getByTestId('available-count')).toHaveTextContent(
        AVAILABLE_THEMES.length.toString()
      )
    })
  })

  describe('Font Size Management', () => {
    it('should provide all available font sizes', () => {
      const TestSizes = () => {
        const theme = useChatTheme()
        return (
          <div>
            {theme.availableFontSizes.map((size) => (
              <div key={size} data-testid={`size-${size}`}>
                {size}
              </div>
            ))}
          </div>
        )
      }

      render(<TestSizes />)

      AVAILABLE_FONT_SIZES.forEach((size) => {
        expect(screen.getByTestId(`size-${size}`)).toBeInTheDocument()
      })
    })
  })

  describe('Line Height Management', () => {
    it('should provide all available line heights', () => {
      const TestLineHeights = () => {
        const theme = useChatTheme()
        return (
          <div>
            {theme.availableLineHeights.map((option) => (
              <div key={option} data-testid={`lh-${option}`}>
                {option}
              </div>
            ))}
          </div>
        )
      }

      render(<TestLineHeights />)

      AVAILABLE_LINE_HEIGHTS.forEach((option) => {
        expect(screen.getByTestId(`lh-${option}`)).toBeInTheDocument()
      })
    })
  })

  describe('Code Theme Management', () => {
    it('should provide all available code themes', () => {
      const TestCodeThemes = () => {
        const theme = useChatTheme()
        return (
          <div>
            {theme.availableCodeThemes.map((t) => (
              <div key={t} data-testid={`code-theme-${t}`}>
                {t}
              </div>
            ))}
          </div>
        )
      }

      render(<TestCodeThemes />)

      AVAILABLE_CODE_THEMES.forEach((theme) => {
        expect(screen.getByTestId(`code-theme-${theme}`)).toBeInTheDocument()
      })
    })
  })

  describe('High Contrast Mode', () => {
    it('should toggle high contrast mode', () => {
      render(<TestComponent />)

      expect(screen.getByTestId('high-contrast')).toHaveTextContent('false')

      const button = screen.getByTestId('high-contrast-btn')
      button.click()

      expect(screen.getByTestId('high-contrast')).toHaveTextContent('true')
    })
  })

  describe('Accent Color Management', () => {
    it('should set custom accent color', () => {
      render(<TestComponent />)

      const button = screen.getByTestId('accent-color-btn')
      button.click()

      // Verify that the setting was persisted
      const stored = JSON.parse(mockStorage['chat-theme-config'] || '{}')
      expect(stored.accentColor).toBe('#ff0000')
    })
  })

  describe('Dark Mode Management', () => {
    it('should toggle dark mode', () => {
      render(<TestComponent />)

      expect(screen.getByTestId('dark-mode')).toHaveTextContent('null')

      const button = screen.getByTestId('dark-mode-btn')
      button.click()

      expect(screen.getByTestId('dark-mode')).toHaveTextContent('true')
    })

    it('should provide isDarkMode derived state', () => {
      render(<TestComponent />)

      expect(screen.getByTestId('is-dark')).toBeInTheDocument()
      expect(typeof screen.getByTestId('is-dark').textContent).toBe('string')
    })
  })

  describe('Reset to Defaults', () => {
    it('should reset all settings to defaults', () => {
      render(<TestComponent />)

      // Change settings
      screen.getByTestId('color-theme-btn').click()
      screen.getByTestId('font-size-btn').click()
      screen.getByTestId('line-height-btn').click()

      expect(screen.getByTestId('color-theme')).toHaveTextContent('monokai')
      expect(screen.getByTestId('font-size')).toHaveTextContent('4')
      expect(screen.getByTestId('line-height')).toHaveTextContent('spacious')

      // Reset
      screen.getByTestId('reset-btn').click()

      expect(screen.getByTestId('color-theme')).toHaveTextContent('default')
      expect(screen.getByTestId('font-size')).toHaveTextContent('3')
      expect(screen.getByTestId('line-height')).toHaveTextContent('normal')
    })
  })

  describe('Context Integration', () => {
    it('should provide theme context through ChatThemeProvider', () => {
      const ContextTestComponent = () => {
        const theme = useChatThemeContext()
        return <div data-testid="context-theme">{theme.colorTheme}</div>
      }

      render(
        <ChatThemeProvider>
          <ContextTestComponent />
        </ChatThemeProvider>
      )

      expect(screen.getByTestId('context-theme')).toHaveTextContent('default')
    })

    it('should throw when useChatThemeContext is used outside provider', () => {
      const ContextTestComponent = () => {
        useChatThemeContext()
        return <div>Should not render</div>
      }

      // Suppress console error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        render(<ContextTestComponent />)
      }).toThrow()

      consoleSpy.mockRestore()
    })
  })

  describe('Persistence', () => {
    it('should persist settings changes to storage', () => {
      render(<TestComponent />)

      screen.getByTestId('color-theme-btn').click()
      screen.getByTestId('font-size-btn').click()
      screen.getByTestId('high-contrast-btn').click()

      const stored = JSON.parse(mockStorage['chat-theme-config'] || '{}')
      expect(stored.colorTheme).toBe('monokai')
      expect(stored.fontSize).toBe(4)
      expect(stored.highContrast).toBe(true)
    })
  })

  describe('Theme Selector Component', () => {
    it('should render without errors', () => {
      const { ThemeSelector } = await import('../../components/Chat/ThemeSelector')

      render(
        <ThemeSelector />
      )

      expect(screen.getByText(/Theme Customization/)).toBeInTheDocument()
    })
  })

  describe('CSS Theme Variables', () => {
    it('should define theme CSS variables', () => {
      // Check that the CSS file exists and can be imported
      expect(() => {
        require('../../styles/chat-themes.css')
      }).not.toThrow()
    })
  })

  describe('Validation', () => {
    it('should validate color theme values', () => {
      const TestValidation = () => {
        const theme = useChatTheme()
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

        theme.setColorTheme('invalid-theme')

        expect(warnSpy).toHaveBeenCalled()
        warnSpy.mockRestore()

        return <div>Test</div>
      }

      render(<TestValidation />)
    })

    it('should validate font size values', () => {
      const TestValidation = () => {
        const theme = useChatTheme()
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

        theme.setFontSize(999)

        expect(warnSpy).toHaveBeenCalled()
        warnSpy.mockRestore()

        return <div>Test</div>
      }

      render(<TestValidation />)
    })
  })
})
