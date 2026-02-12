# Phase 3: Frontend Panel - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Create SandboxChatPanel component and integrate with Dockview. This is the frontend UI that talks to the sandbox router from Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Design principle
- **Drop-in replacement** — mirror existing ClaudeStreamChat component
- Same UI patterns, same interaction model, same look and feel
- User shouldn't notice difference except it's talking to sandbox-agent

### Chat UI approach
- Build custom component mirroring ClaudeStreamChat structure
- NOT using sandbox-agent's Inspector UI (keeps consistency with boring-ui)
- Same message rendering, same input handling

### State management
- Follow existing Zustand store patterns
- Same store shape as ClaudeStreamChat uses
- Persistence: Match existing behavior (Claude's discretion on localStorage)

### Connection handling
- Same connection status patterns as existing chat
- Same error handling and retry UI
- Same loading states

### Panel behavior
- Same capability gate as ClaudeStreamChat (likely `claude_stream` or no gate)
- Same Dockview registration pattern
- Available in same panel picker location

### Claude's Discretion
- Exact component file structure
- CSS approach (existing styles vs new)
- Any sandbox-specific UI tweaks needed for different response format

</decisions>

<specifics>
## Specific Ideas

- Study ClaudeStreamChat component structure before implementing
- Reuse as much existing UI code as possible
- Panel should feel like "just another chat option"

</specifics>

<deferred>
## Deferred Ideas

- Rich markdown rendering beyond current capabilities — future enhancement
- Multi-conversation tabs — future enhancement

</deferred>

---

*Phase: 03-frontend-panel*
*Context gathered: 2026-02-09*
