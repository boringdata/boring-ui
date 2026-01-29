/**
 * boring-ui Component Library
 *
 * Export barrel for all reusable components.
 * Components are categorized by their primary function.
 */

// =============================================================================
// LAYOUT COMPONENTS
// Core components for building application layouts
// =============================================================================

// [core] Application header with configurable branding
export { default as Header } from './Header.jsx'

// [core] Declarative dock layout wrapper for dockview-react
// Props: panels, components, tabComponents, defaultLayout, onLayoutChange, onReady, storageKey, className, persistLayout
export { default as DockLayout, LayoutPresets } from './DockLayout.jsx'

// [core] Main editor component with Monaco integration
export { default as Editor } from './Editor.jsx'

// [core] Lightweight code editor wrapper
export { default as CodeEditor } from './CodeEditor.jsx'

// =============================================================================
// FILE TREE COMPONENTS
// Components for file system navigation and management
// =============================================================================

// [core] File explorer tree with create/rename/delete support
export { default as FileTree } from './FileTree.jsx'

// =============================================================================
// GIT COMPONENTS
// Version control visualization and interaction
// =============================================================================

// [optional] Git diff viewer with split/unified modes
export { default as GitDiff } from './GitDiff.jsx'

// [optional] Git changes panel showing staged/unstaged files
export { default as GitChangesView } from './GitChangesView.jsx'

// [optional] Git status badge for individual files
export { default as GitStatusBadge, GitStatusIndicator, STATUS_CONFIG as GIT_STATUS_CONFIG } from './GitStatusBadge.jsx'

// =============================================================================
// TERMINAL COMPONENTS
// Terminal emulation and command execution
// =============================================================================

// [core] XTerm.js based terminal emulator with WebSocket support
export { default as Terminal, TERMINAL_THEMES, buildWsUrl } from './Terminal.jsx'

// [core] Shell terminal component - standalone wrapper for shell sessions
// Props: wsUrl (required), shellType?, command?, sessionId?, onData?, onReady?, onExit?
export { default as ShellTerminal, buildShellWsUrl } from './ShellTerminal.jsx'

// =============================================================================
// CHAT COMPONENTS
// AI chat interface and tool rendering
// =============================================================================

// [core] Main Claude streaming chat component - standalone/reusable
// Props: apiUrl, wsUrl, sessionId, onSessionChange, onMessage, className
export { default as ClaudeStreamChat } from './chat/ClaudeStreamChat.jsx'

// [core] Chat panel wrapper with theming
export { default as ChatPanel, chatThemeVars } from './chat/ChatPanel.jsx'

// [core] Message list with auto-scroll behavior
export {
  default as MessageList,
  EmptyState,
  Messages,
  ScrollToBottom,
} from './chat/MessageList.jsx'

// [core] Session header for chat sessions
export { default as SessionHeader } from './chat/SessionHeader.jsx'

// [core] Permission request panel for tool approvals
export { default as PermissionPanel } from './chat/PermissionPanel.jsx'

// [core] Text block renderer with markdown support
export { default as TextBlock } from './chat/TextBlock.jsx'

// [core] Tool use block container with common utilities
export {
  default as ToolUseBlock,
  ToolOutput,
  ToolCommand,
  ToolError,
  InlineCode,
} from './chat/ToolUseBlock.jsx'

// -----------------------------------------------------------------------------
// Tool Renderers - Specialized components for rendering tool outputs
// -----------------------------------------------------------------------------

// [optional] Bash/shell command renderer
export { default as BashToolRenderer } from './chat/BashToolRenderer.jsx'

// [optional] File read operation renderer
export { default as ReadToolRenderer } from './chat/ReadToolRenderer.jsx'

// [optional] File write operation renderer
export { default as WriteToolRenderer } from './chat/WriteToolRenderer.jsx'

// [optional] File edit operation renderer with diff display
export { default as EditToolRenderer } from './chat/EditToolRenderer.jsx'

// [optional] Grep search results renderer
export { default as GrepToolRenderer } from './chat/GrepToolRenderer.jsx'

// [optional] Glob file matching renderer
export { default as GlobToolRenderer } from './chat/GlobToolRenderer.jsx'

// =============================================================================
// COMMON/UI COMPONENTS
// Shared UI elements and utilities
// =============================================================================

// [optional] Theme toggle button (light/dark) - standalone component
export { default as ThemeToggle, ThemeToggle as ThemeToggleComponent } from './ThemeToggle.jsx'

// [optional] User menu dropdown with workspace info
export { default as UserMenu } from './UserMenu.jsx'

// [optional] Approval panel for review workflows
export { default as ApprovalPanel } from './ApprovalPanel.jsx'

// [optional] YAML frontmatter editor with helper functions
export {
  default as FrontmatterEditor,
  parseFrontmatter,
  reconstructContent,
} from './FrontmatterEditor.jsx'

// =============================================================================
// HOOKS
// Reusable React hooks
// =============================================================================

// [core] Theme management hook and provider
export { useTheme, ThemeProvider } from '../hooks/useTheme.jsx'

// [core] API hook for making requests with configurable baseUrl
export { useApi } from '../hooks/useApi.js'

// [optional] Git status hook with polling support
export { useGitStatus, getFileStatus, getStatusConfig, STATUS_CONFIG } from '../hooks/useGitStatus.js'
