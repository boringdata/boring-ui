/**
 * boring-ui - A composition-based web IDE framework
 *
 * This is the main entry point for the library build.
 * Projects import components and compose their own App.jsx.
 */

// Import CSS for Vite to emit as style.css
import './styles/index.css'

// ============================================================================
// Core Components
// ============================================================================

// Layout
export { default as DockLayout } from './components/DockLayout'

// File Management
export { default as FileTree } from './components/FileTree'

// Editor
export { default as Editor } from './components/Editor'
export { default as CodeEditor } from './components/CodeEditor'
export { default as FrontmatterEditor } from './components/FrontmatterEditor'

// Terminal
export { default as Terminal } from './components/Terminal'
export { default as ShellTerminal } from './components/ShellTerminal'

// Git
export { default as GitDiff } from './components/GitDiff'
export { default as GitStatusBadge } from './components/GitStatusBadge'
export { default as GitChangesView } from './components/GitChangesView'

// UI Components
export { default as Header } from './components/Header'
export { default as ThemeToggle } from './components/ThemeToggle'
export { default as UserMenu } from './components/UserMenu'
export { default as Toast } from './components/Toast'
export { default as ErrorBoundary } from './components/ErrorBoundary'
export { default as LoadingPlaceholder } from './components/LoadingPlaceholder'
export { default as CommandPalette } from './components/CommandPalette'

// Approval
export { default as ApprovalPanel } from './components/ApprovalPanel'

// ============================================================================
// Panel Wrappers (for DockLayout composition)
// ============================================================================

export { default as FileTreePanel } from './panels/FileTreePanel'
export { default as EditorPanel } from './panels/EditorPanel'
export { default as TerminalPanel } from './panels/TerminalPanel'
export { default as ShellTerminalPanel } from './panels/ShellTerminalPanel'
export { default as ReviewPanel } from './panels/ReviewPanel'
export { default as EmptyPanel } from './panels/EmptyPanel'

// ============================================================================
// Chat Components
// ============================================================================

export { default as ClaudeStreamChat } from './components/chat/ClaudeStreamChat'
export { default as ChatPanel } from './components/chat/ChatPanel'
export { default as MessageList } from './components/chat/MessageList'
export { default as ToolUseBlock } from './components/chat/ToolUseBlock'
export { default as TextBlock } from './components/chat/TextBlock'
export { default as SessionHeader } from './components/chat/SessionHeader'
export { default as PermissionPanel } from './components/chat/PermissionPanel'

// Tool Renderers
export { default as BashToolRenderer } from './components/chat/BashToolRenderer'
export { default as ReadToolRenderer } from './components/chat/ReadToolRenderer'
export { default as WriteToolRenderer } from './components/chat/WriteToolRenderer'
export { default as EditToolRenderer } from './components/chat/EditToolRenderer'
export { default as GrepToolRenderer } from './components/chat/GrepToolRenderer'
export { default as GlobToolRenderer } from './components/chat/GlobToolRenderer'

// ============================================================================
// Primitives
// ============================================================================

export * from './components/primitives'

// ============================================================================
// Configuration
// ============================================================================

export {
  // Schemas
  brandingSchema,
  fileTreeSectionSchema,
  fileTreeSchema,
  storageSchema,
  panelsSchema,
  apiSchema,
  featuresSchema,
  appConfigSchema,
  parseAppConfig,
  safeParseAppConfig,
  // Provider and hooks
  ConfigProvider,
  useConfig,
  useConfigValue,
  // Storage utilities
  configureStorage,
  migrateAllLegacyKeys,
  STORAGE_KEYS,
  LEGACY_PREFIX,
} from './config'

// ============================================================================
// Hooks
// ============================================================================

export {
  // Theme
  useTheme,
  ThemeProvider,
  getInitialTheme,
  applyTheme,
  persistTheme,
  DEFAULT_STORAGE_KEY,
  // API
  useApi,
  // Git
  useGitStatus,
  getFileStatus,
  getStatusConfig,
  STATUS_CONFIG,
} from './hooks'

// Additional hooks
export { useResponsive } from './hooks/useResponsive'
export { useChatTheme } from './hooks/useChatTheme'
export { useMessageActions } from './hooks/useMessageActions'
export { useVoiceRecognition } from './hooks/useVoiceRecognition'
export { useTextToSpeech } from './hooks/useTextToSpeech'
export { useToast } from './hooks/useToast'

// ============================================================================
// Context Providers
// ============================================================================

export { ToastProvider, useToastContext } from './context/ToastContext'

// ============================================================================
// Styles (for advanced customization)
// ============================================================================

export { default as StyleProvider } from './styles/StyleProvider'
export { lightTokens, darkTokens } from './styles/defaults'

// ============================================================================
// Utilities
// ============================================================================

export * from './utils/storage'
export * from './utils/errorHandling'
