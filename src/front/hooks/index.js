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

export { useFileOperations } from './useFileOperations'

export { useLayoutInit, debounce } from './useLayoutInit'

export { usePanelParams } from './usePanelParams'

export { useActivePanel } from './useActivePanel'

export { useApprovalPanels } from './useApprovalPanels'

export { useUrlSync } from './useUrlSync'

export { useDragDrop } from './useDragDrop'

export { useLayoutRestore } from './useLayoutRestore'
