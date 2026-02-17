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
} from './useCapabilities'

export {
  useKeyboardShortcuts,
  formatShortcut,
  DEFAULT_SHORTCUTS,
} from './useKeyboardShortcuts'

export {
  useOnboardingState,
} from './useOnboardingState'
