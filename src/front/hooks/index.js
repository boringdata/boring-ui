/**
 * Hooks module exports.
 * @module hooks
 */

export {
  ThemeProvider,
  useTheme,
} from './useTheme'

export {
  useCapabilities,
  isFeatureEnabled,
  areAllFeaturesEnabled,
  UNKNOWN_CAPABILITIES,
} from './useCapabilities'

export {
  useKeyboardShortcuts,
  formatShortcut,
  DEFAULT_SHORTCUTS,
} from './useKeyboardShortcuts'
