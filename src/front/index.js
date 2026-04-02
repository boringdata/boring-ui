/**
 * boring-ui Public API
 *
 * This is the main entry point for the boring-ui library.
 * It re-exports the public API from registry, layout, config, hooks, and panels.
 *
 * @example
 * // Library usage
 * import { ConfigProvider, useConfig, ThemeProvider, useTheme } from 'boring-ui'
 * import 'boring-ui/style.css'
 *
 * @example
 * // Registry usage
 * import { paneRegistry, registerPane, PaneRegistry } from 'boring-ui'
 *
 * @example
 * // Layout usage
 * import { loadLayout, saveLayout, validateLayoutStructure } from 'boring-ui'
 */

// =============================================================================
// Registry - Pane registration and management
// =============================================================================
export {
  PaneRegistry,
  createDefaultRegistry,
  registerPane,
  getPane,
  listPanes,
  listPaneIds,
  essentialPanes,
  isEssential,
  hasPane,
  getComponents,
  getKnownComponents,
  getPaneForFilePath,
  paneRegistry,
} from './registry'

// =============================================================================
// Layout - Layout persistence and management
// =============================================================================
export {
  LAYOUT_VERSION,
  hashProjectRoot,
  getStorageKey,
  getSharedStorageKey,
  SIDEBAR_COLLAPSED_KEY,
  PANEL_SIZES_KEY,
  validateLayoutStructure,
  loadSavedTabs,
  saveTabs,
  loadLayout,
  saveLayout,
  loadLastKnownGoodLayout,
  clearLastKnownGoodLayout,
  loadCollapsedState,
  saveCollapsedState,
  loadPanelSizes,
  savePanelSizes,
  pruneEmptyGroups,
  checkForSavedLayout,
  getFileName,
  DEFAULT_CONSTRAINTS,
  getDefaultLayoutConfig,
} from './layout'

// =============================================================================
// Config - Application configuration
// =============================================================================
export {
  getConfig,
  getDefaultConfig,
  resetConfig,
  setConfig,
  ConfigProvider,
  useConfig,
  useConfigLoaded,
} from './shared/config'

// =============================================================================
// Hooks - React hooks
// =============================================================================
export { ThemeProvider, useTheme } from './shared/hooks/useTheme'

// =============================================================================
// Panels - Dockview panel components
// =============================================================================
export { default as FileTreePanel } from './shared/panels/FileTreePanel'
export { default as EditorPanel } from './shared/panels/EditorPanel'
export { default as EmptyPanel } from './shared/panels/EmptyPanel'
export { default as ReviewPanel } from './shared/panels/ReviewPanel'

// =============================================================================
// Components - UI components
// =============================================================================
export { default as ThemeToggle } from './shared/components/ThemeToggle'
export {
  setPiAgentConfig,
  addPiAgentTools,
  resetPiAgentConfig,
} from './shared/providers/pi/agentConfig'
export { cn } from './lib/utils'
export { Button, buttonVariants } from './shared/components/ui/button'
export { Badge, badgeVariants } from './shared/components/ui/badge'
export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from './shared/components/ui/dialog'
export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from './shared/components/ui/dropdown-menu'
export { Input } from './shared/components/ui/input'
export { Textarea } from './shared/components/ui/textarea'
export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
  SelectScrollUpButton,
  SelectScrollDownButton,
} from './shared/components/ui/select'
export { Label } from './shared/components/ui/label'
export { Switch } from './shared/components/ui/switch'
export {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from './shared/components/ui/tooltip'
export { Avatar, AvatarImage, AvatarFallback } from './shared/components/ui/avatar'
export { Tabs, TabsList, TabsTrigger, TabsContent } from './shared/components/ui/tabs'
export { Separator } from './shared/components/ui/separator'

// =============================================================================
// Main App
// =============================================================================
export { default as App } from './App'
