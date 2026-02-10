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
  useServiceConnection,
} from './useServiceConnection'

export {
  useProjectRoot,
} from './useProjectRoot'

export {
  useBrowserTitle,
} from './useBrowserTitle'

export {
  useApprovals,
} from './useApprovals'

export {
  useApprovalPanels,
} from './useApprovalPanels'

export {
  useAppState,
} from './useAppState'

export {
  usePanelToggle,
} from './usePanelToggle'

export {
  usePanelParams,
} from './usePanelParams'

export {
  useCollapsedState,
} from './useCollapsedState'

export {
  useActivePanel,
} from './useActivePanel'

export {
  useDragDrop,
} from './useDragDrop'

export {
  useUrlSync,
} from './useUrlSync'

export {
  useTabManager,
} from './useTabManager'

export {
  useFileOperations,
} from './useFileOperations'
