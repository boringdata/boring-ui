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

export { useAppState } from './useAppState'

export { usePanelToggle, DEFAULT_TOGGLE_CONFIGS } from './usePanelToggle'

export { useCollapsedEffect, DEFAULT_COLLAPSE_PANELS } from './useCollapsedState'

export { useTabManager } from './useTabManager'

export { useBrowserTitle, computeTitle, getFolderName } from './useBrowserTitle'

export { useApprovals } from './useApprovals'
