import React from 'react'
import {
  Loader2,
  Check,
  X,
  FileCode,
  Terminal,
  Search,
  FolderTree,
  GitBranch,
  Pencil,
  Eye,
  Wrench,
} from 'lucide-react'

/**
 * Icon registry mapping tool names to appropriate icons.
 * Falls back to Wrench for unknown tools.
 */
const TOOL_ICONS = {
  read_file: Eye,
  write_file: FileCode,
  edit_file: Pencil,
  bash: Terminal,
  grep: Search,
  find: Search,
  ls: FolderTree,
  git_diff: GitBranch,
  git_status: GitBranch,
  git_commit: GitBranch,
}

function getToolIcon(toolName) {
  // Try exact match, then prefix match
  if (TOOL_ICONS[toolName]) return toolName
  for (const [key] of Object.entries(TOOL_ICONS)) {
    if (toolName.startsWith(key)) return key
  }
  return 'default'
}

function ToolGlyph({ toolName }) {
  switch (getToolIcon(toolName)) {
    case 'read_file':
      return <Eye size={14} />
    case 'write_file':
      return <FileCode size={14} />
    case 'edit_file':
      return <Pencil size={14} />
    case 'bash':
      return <Terminal size={14} />
    case 'grep':
    case 'find':
      return <Search size={14} />
    case 'ls':
      return <FolderTree size={14} />
    case 'git_diff':
    case 'git_status':
    case 'git_commit':
      return <GitBranch size={14} />
    default:
      return <Wrench size={14} />
  }
}

/**
 * Extract a displayable file path from tool args.
 */
function getFilePath(args) {
  if (!args) return null
  return args.path || args.file_path || args.filepath || null
}

function summarizeResult(result) {
  if (result == null) return ''
  if (typeof result === 'string') return result
  if (typeof result?.content === 'string') return result.content
  if (typeof result?.text === 'string') return result.text
  try {
    return JSON.stringify(result)
  } catch {
    return String(result)
  }
}

/**
 * ToolCallCard - Inline card showing a tool execution in the chat timeline.
 *
 * Props:
 *   toolName   - string, name of the tool being called
 *   args       - object, tool arguments (may contain path/file_path)
 *   result     - string|object, tool result (optional)
 *   status     - 'running' | 'complete' | 'error'
 */
export default function ToolCallCard({ toolName, args, result, status }) {
  const filePath = getFilePath(args)
  const resultSummary = summarizeResult(result).trim()

  return (
    <div className="vc-tool-card" data-status={status}>
      <div className="vc-tool-card-icon">
        <ToolGlyph toolName={toolName} />
      </div>
      <div className="vc-tool-card-info">
        <span className="vc-tool-card-name">{toolName}</span>
        {filePath && (
          <span className="vc-tool-card-path">{filePath}</span>
        )}
      </div>
      <div className="vc-tool-card-status">
        {status === 'running' && (
          <span data-testid="tool-status-running">
            <Loader2 size={14} className="vc-tool-spinner" />
          </span>
        )}
        {status === 'complete' && (
          <span data-testid="tool-status-complete">
            <Check size={14} className="vc-tool-check" />
          </span>
        )}
        {status === 'error' && (
          <span data-testid="tool-status-error">
            <X size={14} className="vc-tool-error" />
          </span>
        )}
      </div>
      {status !== 'running' && resultSummary && (
        <div className="vc-tool-card-result">
          {resultSummary.length > 180 ? `${resultSummary.slice(0, 177)}...` : resultSummary}
        </div>
      )}
    </div>
  )
}
