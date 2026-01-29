import { z } from 'zod'

/**
 * Zod schema for design token customization
 * Allows apps to override specific colors while maintaining type safety
 */

// Individual color schemas - all optional to allow partial overrides
const colorSchema = z.object({
  // Backgrounds
  bgPrimary: z.string().optional(),
  bgSecondary: z.string().optional(),
  bgTertiary: z.string().optional(),
  bgHover: z.string().optional(),
  bgActive: z.string().optional(),

  // Text
  textPrimary: z.string().optional(),
  textSecondary: z.string().optional(),
  textTertiary: z.string().optional(),
  textInverse: z.string().optional(),

  // Borders
  border: z.string().optional(),
  borderStrong: z.string().optional(),

  // Accent (primary color - most commonly customized)
  accent: z.string().optional(),
  accentHover: z.string().optional(),
  accentLight: z.string().optional(),

  // Semantic colors
  success: z.string().optional(),
  successHover: z.string().optional(),
  successLight: z.string().optional(),
  successBg: z.string().optional(),

  warning: z.string().optional(),
  warningLight: z.string().optional(),
  warningBg: z.string().optional(),

  error: z.string().optional(),
  errorHover: z.string().optional(),
  errorLight: z.string().optional(),
  errorBg: z.string().optional(),

  info: z.string().optional(),
  infoHover: z.string().optional(),
  infoLight: z.string().optional(),
  infoBg: z.string().optional(),

  // Highlight/Selection
  highlight: z.string().optional(),
  selected: z.string().optional(),
  selectedHover: z.string().optional(),

  // Scrollbar
  scrollbar: z.string().optional(),
  scrollbarHover: z.string().optional(),

  // Code blocks
  codeBg: z.string().optional(),
  preBg: z.string().optional(),
  preText: z.string().optional(),

  // Tool output
  toolBg: z.string().optional(),
  commandBg: z.string().optional(),

  // Overlay
  overlay: z.string().optional(),
  insetShadow: z.string().optional(),

  // Diff colors
  diffDivider: z.string().optional(),
  diffAddBg: z.string().optional(),
  diffAddText: z.string().optional(),
  diffRemoveBg: z.string().optional(),
  diffRemoveText: z.string().optional(),
})

// Complete styles configuration schema
export const stylesSchema = z.object({
  // Light mode token overrides
  light: colorSchema.optional(),
  // Dark mode token overrides
  dark: colorSchema.optional(),
})

/**
 * Validate and parse styles configuration
 * @param {unknown} config - Raw styles configuration object
 * @returns {Object} Validated styles configuration with defaults applied
 */
export function parseStylesConfig(config) {
  return stylesSchema.parse(config)
}

/**
 * Safely validate styles configuration (returns success/error result)
 * @param {unknown} config - Raw styles configuration object
 * @returns {z.SafeParseReturnType<unknown, Object>} Parse result
 */
export function safeParseStylesConfig(config) {
  return stylesSchema.safeParse(config)
}
