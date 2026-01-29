/**
 * Default design tokens matching tokens.css
 * These values can be overridden via configuration
 */

export const defaultTokens = {
  light: {
    // Typography (not customizable, kept for reference)
    fontSans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontMono: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",

    // Spacing
    spaceXs: '0.25rem',   // 4px
    spaceSm: '0.5rem',    // 8px
    spaceMd: '0.75rem',   // 12px
    spaceLg: '1rem',      // 16px
    spaceXl: '1.25rem',   // 20px
    space2xl: '1.5rem',   // 24px
    space3xl: '2rem',     // 32px
    space4xl: '2.5rem',   // 40px
    space5xl: '3rem',     // 48px
    space6xl: '4rem',     // 64px

    // Backgrounds
    bgPrimary: '#ffffff',
    bgSecondary: '#f9fafb',
    bgTertiary: '#f3f4f6',
    bgHover: '#f3f4f6',
    bgActive: '#e5e7eb',

    // Text
    textPrimary: '#111827',
    textSecondary: '#6b7280',
    textTertiary: '#9ca3af',
    textInverse: '#ffffff',

    // Borders
    border: '#e5e7eb',
    borderStrong: '#d1d5db',

    // Accent (Claude orange - primary customizable)
    accent: '#ea580c',
    accentHover: '#c2410c',
    accentLight: '#fff7ed',

    // Semantic colors
    success: '#22c55e',
    successHover: '#16a34a',
    successLight: '#f0fdf4',
    successBg: 'rgba(22, 163, 74, 0.15)',

    warning: '#f59e0b',
    warningLight: '#fef3c7',
    warningBg: 'rgba(245, 158, 11, 0.15)',

    error: '#ef4444',
    errorHover: '#dc2626',
    errorLight: '#fef2f2',
    errorBg: 'rgba(239, 68, 68, 0.15)',

    info: '#3b82f6',
    infoHover: '#2563eb',
    infoLight: '#dbeafe',
    infoBg: 'rgba(59, 130, 246, 0.15)',

    // Highlight/Selection
    highlight: '#fef08a',
    selected: '#e0e7ff',
    selectedHover: '#c7d2fe',

    // Scrollbar
    scrollbar: '#cbd5e1',
    scrollbarHover: '#94a3b8',

    // Code blocks
    codeBg: '#f3f4f6',
    preBg: '#1f2937',
    preText: '#f9fafb',

    // Tool output
    toolBg: '#f8fafc',
    commandBg: '#f1f5f9',

    // Overlay
    overlay: 'rgba(0, 0, 0, 0.5)',
    insetShadow: 'rgba(0, 0, 0, 0.15)',

    // Diff colors
    diffDivider: '#374151',
    diffAddBg: '#dcfce7',
    diffAddText: '#166534',
    diffRemoveBg: '#fee2e2',
    diffRemoveText: '#991b1b',
  },

  dark: {
    // Typography (not customizable, kept for reference)
    fontSans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontMono: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",

    // Spacing (same as light)
    spaceXs: '0.25rem',
    spaceSm: '0.5rem',
    spaceMd: '0.75rem',
    spaceLg: '1rem',
    spaceXl: '1.25rem',
    space2xl: '1.5rem',
    space3xl: '2rem',
    space4xl: '2.5rem',
    space5xl: '3rem',
    space6xl: '4rem',

    // Backgrounds
    bgPrimary: '#0f0f0f',
    bgSecondary: '#1a1a1a',
    bgTertiary: '#262626',
    bgHover: '#2a2a2a',
    bgActive: '#333333',

    // Text
    textPrimary: '#fafafa',
    textSecondary: '#a1a1aa',
    textTertiary: '#71717a',
    textInverse: '#0f0f0f',

    // Borders
    border: '#2e2e2e',
    borderStrong: '#404040',

    // Accent (vibrant orange for dark - primary customizable)
    accent: '#fb923c',
    accentHover: '#fdba74',
    accentLight: '#431407',

    // Semantic colors
    success: '#22c55e',
    successHover: '#22c55e',
    successLight: '#14532d',
    successBg: 'rgba(34, 197, 94, 0.2)',

    warning: '#f59e0b',
    warningLight: '#422006',
    warningBg: 'rgba(245, 158, 11, 0.2)',

    error: '#ef4444',
    errorHover: '#f87171',
    errorLight: '#450a0a',
    errorBg: 'rgba(239, 68, 68, 0.2)',

    info: '#3b82f6',
    infoHover: '#60a5fa',
    infoLight: '#1e3a5f',
    infoBg: 'rgba(59, 130, 246, 0.2)',

    // Highlight/Selection
    highlight: '#854d0e',
    selected: '#312e81',
    selectedHover: '#3730a3',

    // Scrollbar
    scrollbar: '#4b5563',
    scrollbarHover: '#6b7280',

    // Code blocks
    codeBg: '#1e1e2e',
    preBg: '#11111b',
    preText: '#cdd6f4',

    // Tool output
    toolBg: '#16161e',
    commandBg: '#1a1b26',

    // Overlay
    overlay: 'rgba(0, 0, 0, 0.7)',
    insetShadow: 'rgba(0, 0, 0, 0.3)',

    // Diff colors
    diffDivider: '#4b5563',
    diffAddBg: '#14532d',
    diffAddText: '#86efac',
    diffRemoveBg: '#450a0a',
    diffRemoveText: '#fca5a5',
  },
}
