/**
 * ThemeSelector Component
 * UI for comprehensive theme customization
 * Allows selection of color themes, font sizes, code themes, and more
 */

import React, { useState } from 'react'
import { useChatTheme } from '../../hooks/useChatTheme'
import { ChevronDown, Palette, Type, Eye, Code2, Contrast, RotateCcw, Moon, Sun, Monitor } from 'lucide-react'
import clsx from 'clsx'

/**
 * Theme color preview badge
 */
function ThemePreview({ theme, isSelected, onClick }) {
  const themeColors = {
    default: { light: '#0a66c2', dark: '#3b82f6' },
    monokai: { light: '#66d9ef', dark: '#66d9ef' },
    solarized: { light: '#268bd2', dark: '#268bd2' },
    dracula: { light: '#bd93f9', dark: '#bd93f9' },
    nord: { light: '#88c0d0', dark: '#88c0d0' },
  }

  const colors = themeColors[theme] || themeColors.default

  return (
    <button
      onClick={onClick}
      className={clsx(
        'relative flex items-center gap-2 px-3 py-2 rounded-md transition-all duration-200',
        isSelected ? 'ring-2 ring-offset-2 ring-blue-500' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
      )}
      aria-pressed={isSelected}
      title={`${theme.charAt(0).toUpperCase() + theme.slice(1)} theme`}
    >
      <div className="flex gap-1">
        <div
          className="w-4 h-4 rounded border border-gray-300 dark:border-gray-600"
          style={{ backgroundColor: colors.light }}
          aria-label={`${theme} light mode`}
        />
        <div
          className="w-4 h-4 rounded border border-gray-300 dark:border-gray-600"
          style={{ backgroundColor: colors.dark }}
          aria-label={`${theme} dark mode`}
        />
      </div>
      <span className="text-sm capitalize hidden sm:inline">{theme}</span>
    </button>
  )
}

/**
 * Font size preview with visual representation
 */
function FontSizePreview({ size, isSelected, onClick }) {
  const sizeMap = {
    1: { label: 'XS', px: 12 },
    2: { label: 'S', px: 13 },
    3: { label: 'M', px: 14 },
    4: { label: 'L', px: 16 },
    5: { label: 'XL', px: 18 },
    6: { label: 'XXL', px: 20 },
  }

  const info = sizeMap[size]

  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex flex-col items-center justify-center w-12 h-12 rounded-md transition-all duration-200',
        isSelected
          ? 'ring-2 ring-offset-2 ring-blue-500 bg-blue-50 dark:bg-blue-900'
          : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
      )}
      aria-pressed={isSelected}
      title={`Font size: ${info.label} (${info.px}px)`}
    >
      <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">{info.label}</span>
      <span className="text-[10px] text-gray-500 dark:text-gray-400">{info.px}px</span>
    </button>
  )
}

/**
 * Line height option selector
 */
function LineHeightOption({ option, label, isSelected, onClick }) {
  const lineHeightMap = {
    compact: 1.4,
    normal: 1.6,
    spacious: 1.8,
  }

  const lineHeight = lineHeightMap[option]

  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex flex-col items-center justify-center gap-2 px-4 py-3 rounded-md transition-all duration-200',
        isSelected
          ? 'ring-2 ring-offset-2 ring-blue-500 bg-blue-50 dark:bg-blue-900'
          : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
      )}
      aria-pressed={isSelected}
      title={`Line height: ${lineHeight}`}
    >
      <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">{label}</span>
      <div className="flex flex-col gap-1 text-[10px] leading-relaxed text-gray-600 dark:text-gray-400">
        <span>Text</span>
        <span>line</span>
      </div>
    </button>
  )
}

/**
 * Code theme selector
 */
function CodeThemeOption({ theme, isSelected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-3 py-2 rounded-md text-sm transition-all duration-200 whitespace-nowrap',
        isSelected
          ? 'ring-2 ring-offset-2 ring-blue-500 bg-blue-50 dark:bg-blue-900'
          : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
      )}
      aria-pressed={isSelected}
      title={`Code theme: ${theme}`}
    >
      {theme.split('-').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
    </button>
  )
}

/**
 * Color picker input
 */
function AccentColorPicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="color"
        value={value || '#0a66c2'}
        onChange={(e) => onChange(e.target.value)}
        className="w-12 h-10 rounded cursor-pointer border border-gray-300 dark:border-gray-600"
        title="Custom accent color"
        aria-label="Custom accent color picker"
      />
      <div className="flex-1">
        <input
          type="text"
          value={value || ''}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder="#0a66c2"
          className="w-full px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100"
          title="Enter hex color code"
          aria-label="Hex color code input"
        />
      </div>
      {value && (
        <button
          onClick={() => onChange(null)}
          className="px-2 py-1 text-sm bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded transition-colors"
          title="Reset to default accent color"
        >
          Reset
        </button>
      )}
    </div>
  )
}

/**
 * ThemeSelector Component
 * Comprehensive theme customization UI
 */
export function ThemeSelector({ className = '' }) {
  const {
    colorTheme,
    fontSize,
    lineHeight,
    codeTheme,
    highContrast,
    accentColor,
    darkMode,
    isDarkMode,
    availableColorThemes,
    availableCodeThemes,
    availableFontSizes,
    availableLineHeights,
    setColorTheme,
    setFontSize,
    setLineHeight,
    setCodeTheme,
    setHighContrast,
    setAccentColor,
    setDarkMode,
    toggleDarkMode,
    resetToDefaults,
  } = useChatTheme()

  const [expandedSection, setExpandedSection] = useState(null)

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  return (
    <div className={clsx('space-y-4 p-4 bg-white dark:bg-gray-900 rounded-lg', className)}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Palette size={20} />
          Theme Customization
        </h2>
        <button
          onClick={resetToDefaults}
          className="p-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
          title="Reset all settings to defaults"
          aria-label="Reset theme settings"
        >
          <RotateCcw size={18} />
        </button>
      </div>

      {/* Dark Mode Toggle */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('darkMode')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'darkMode'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Sun size={18} className="text-yellow-500" />
            <Moon size={18} className="text-blue-500" />
            Dark Mode
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'darkMode' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'darkMode' && (
          <div className="mt-3 space-y-2 pl-4">
            <button
              onClick={() => setDarkMode(null)}
              className={clsx(
                'w-full text-left px-3 py-2 rounded transition-colors text-sm flex items-center gap-2',
                darkMode === null
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800'
              )}
              aria-pressed={darkMode === null}
            >
              <Monitor size={16} />
              System Preference
            </button>
            <button
              onClick={() => setDarkMode(false)}
              className={clsx(
                'w-full text-left px-3 py-2 rounded transition-colors text-sm flex items-center gap-2',
                darkMode === false
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800'
              )}
              aria-pressed={darkMode === false}
            >
              <Sun size={16} />
              Light Mode
            </button>
            <button
              onClick={() => setDarkMode(true)}
              className={clsx(
                'w-full text-left px-3 py-2 rounded transition-colors text-sm flex items-center gap-2',
                darkMode === true
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800'
              )}
              aria-pressed={darkMode === true}
            >
              <Moon size={16} />
              Dark Mode
            </button>
          </div>
        )}
      </section>

      {/* Color Theme Selection */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('colorTheme')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'colorTheme'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Palette size={18} />
            Color Theme
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'colorTheme' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'colorTheme' && (
          <div className="mt-3 grid grid-cols-2 gap-2 pl-4">
            {availableColorThemes.map((theme) => (
              <ThemePreview
                key={theme}
                theme={theme}
                isSelected={colorTheme === theme}
                onClick={() => setColorTheme(theme)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Font Size Selection */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('fontSize')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'fontSize'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Type size={18} />
            Font Size
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'fontSize' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'fontSize' && (
          <div className="mt-3 grid grid-cols-6 gap-2 pl-4">
            {availableFontSizes.map((size) => (
              <FontSizePreview
                key={size}
                size={size}
                isSelected={fontSize === size}
                onClick={() => setFontSize(size)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Line Height Selection */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('lineHeight')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'lineHeight'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Eye size={18} />
            Line Height
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'lineHeight' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'lineHeight' && (
          <div className="mt-3 grid grid-cols-3 gap-2 pl-4">
            {availableLineHeights.map((option) => (
              <LineHeightOption
                key={option}
                option={option}
                label={option.charAt(0).toUpperCase() + option.slice(1)}
                isSelected={lineHeight === option}
                onClick={() => setLineHeight(option)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Code Theme Selection */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('codeTheme')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'codeTheme'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Code2 size={18} />
            Code Theme
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'codeTheme' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'codeTheme' && (
          <div className="mt-3 grid grid-cols-2 gap-2 pl-4 max-h-64 overflow-y-auto">
            {availableCodeThemes.map((theme) => (
              <CodeThemeOption
                key={theme}
                theme={theme}
                isSelected={codeTheme === theme}
                onClick={() => setCodeTheme(theme)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Accent Color */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => toggleSection('accent')}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-expanded={expandedSection === 'accent'}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Palette size={18} />
            Accent Color
          </span>
          <ChevronDown
            size={18}
            className={clsx('transition-transform', expandedSection === 'accent' && 'rotate-180')}
          />
        </button>

        {expandedSection === 'accent' && (
          <div className="mt-3 pl-4">
            <AccentColorPicker value={accentColor} onChange={setAccentColor} />
          </div>
        )}
      </section>

      {/* High Contrast Mode */}
      <section className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <button
          onClick={() => setHighContrast(!highContrast)}
          className="w-full flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-800 px-2 rounded transition-colors"
          aria-pressed={highContrast}
        >
          <span className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
            <Contrast size={18} />
            High Contrast (WCAG AAA)
          </span>
          <div
            className={clsx(
              'relative w-12 h-6 rounded-full transition-colors',
              highContrast ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
            )}
          >
            <div
              className={clsx(
                'absolute top-1 w-4 h-4 bg-white rounded-full transition-transform',
                highContrast ? 'left-6' : 'left-1'
              )}
            />
          </div>
        </button>
      </section>

      {/* Reset Button */}
      <button
        onClick={resetToDefaults}
        className="w-full mt-4 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-md font-medium transition-colors flex items-center justify-center gap-2"
        title="Reset all settings to defaults"
      >
        <RotateCcw size={16} />
        Reset to Defaults
      </button>
    </div>
  )
}

export default ThemeSelector
