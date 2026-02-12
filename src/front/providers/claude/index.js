import ClaudeAdapter from './adapter'

export const config = {
  id: 'claude',
  label: 'Claude Code',
  component: ClaudeAdapter,
  requiresCapabilities: ['chat_claude_code'],
}

export default config
