# Plan: Post-Signup UX Chaos + PI Agent Path Mismatch + Tool Usage Display

**Status**: DRAFT
**Created**: 2025-03-20

---

## Problem Statement

After signup + workspace creation in edge/hosted mode, three distinct issues degrade the experience:

1. **Chaotic post-signup UX**: Oscillation between loading state, workspace with missing capabilities, loading state again, then a "workspace is being created" page that never resolves. User must manually refresh to enter workspace.
2. **PI agent filesystem mismatch**: The PI agent operates on a different root path than the file API endpoints — files created via one are invisible to the other.
3. **No tool usage visibility**: When the PI agent uses tools (exec_bash), the chat only shows the final text response. Tool calls, commands, and outputs are invisible.

---

## Issue 1: Chaotic Post-Signup State Machine

### Root Cause Analysis

There are **two independent async processes** that race against each other after signup, plus a capabilities-loading gate that can get stuck.

#### Race 1: Duplicate Workspace Creation

**Backend** (`auth_router_neon.py:2168`): After token-exchange, `_eager_workspace_provision()` is **awaited** (not fire-and-forget). It calls `create_workspace_for_user()` with `name="My Workspace"` and `is_default=True`, which uses `ON CONFLICT (created_by, app_id) WHERE is_default = true DO NOTHING` for idempotency. Then it kicks off Fly Machine provisioning as a background `asyncio.create_task()`. The token-exchange response is returned **after** the workspace row exists in the DB but **before** provisioning completes.

**Frontend** (`App.jsx:4616-4632`): After redirect to `/`, the `needsWorkspaceRedirect` effect checks `workspaceOptions.length`. If the workspace list fetch hasn't completed yet, `autoCreateAttempted` fires `handleCreateWorkspaceSubmit('My Workspace')`, which POSTs to `/api/v1/workspaces`.

**The dedup gap**: The POST endpoint (`workspace_router_hosted.py:290`) calls `create_workspace_for_user()` with `is_default=False` (default). The eager provision uses `is_default=True`. The `ON CONFLICT` idempotency clause only fires when `is_default=True`, so the frontend call **creates a second workspace**.

**Timeline**:
```
t=0    Token exchange starts → awaits _eager_workspace_provision()
t=100  Workspace row created in DB (is_default=True), Fly provisioning kicked off as background task
t=100  Token exchange response returned with redirect_uri="/"
t=100  Frontend navigates to "/"
t=150  App.jsx mounts, fires capabilities fetch + workspace list fetch
t=200  needsWorkspaceRedirect effect runs
         → workspaceOptions is still [] (list fetch in flight)
         → autoCreateAttempted fires → POST /workspaces (is_default=False) → DUPLICATE
t=300  Workspace list fetch completes → finds 2 workspaces
```

Note: Because eager provision is awaited, the workspace DOES exist in DB before redirect. The race is between the **workspace list fetch completing** and the **auto-create effect firing**. If the list fetch is fast enough, it finds the workspace and redirects — no duplicate. But if it's slow (cold DB connection, network latency), the auto-create fires first.

#### Stuck Gate: Capabilities Never Load on Setup Page

`handleCreateWorkspaceSubmit()` (`App.jsx:1546-1547`) navigates to `/w/{id}/setup` via `window.location.assign()`. This triggers a full page reload. The WorkspaceSetupPage has **three sequential gates**:

1. `setupLoading && !setupPayload` → "Creating your backend workspace" spinner
2. `!runtimeReady` → "Preparing your workspace" (polls `/setup` every 2s)
3. `!capabilitiesLoaded` → "Loading workspace capabilities..."

Gate 3 depends on `capabilitiesPending` from `App.jsx:623-630`:
```js
const capabilitiesPending = staticCapabilities
  ? false
  : (capabilitiesLoading || !capabilities || (
      capabilities?.version === 'unknown' && capabilitiesFeatureCount === 0
    ))
```

**Key finding**: `/api/capabilities` is served by the **control plane directly** — it has NO health gate and does NOT depend on workspace machine health. It returns `version: '0.1.0'` with all configured features unconditionally. The health gate (`app.py:415-433`) only affects `/health` and only during active PI sidecar startup.

The `version: 'unknown'` with no features is a **frontend fallback** (`UNKNOWN_CAPABILITIES` in `useCapabilities.js`) returned when the fetch itself fails — NOT a degraded backend response. This means the setup page gets stuck because the **capabilities fetch is failing at the network/auth layer**, not because the backend is returning bad data.

**Likely causes of the fetch failure** (needs investigation):
- Session cookie not yet set or not included in the request after the `window.location.assign()` redirect
- The setup page loads before the auth cookie propagates (timing issue after full page reload)
- CORS mismatch if the capabilities endpoint URL differs from the setup page origin
- The capabilities fetch fires before the app has resolved the current workspace scope, causing a scoping issue

**A page refresh works** because by then the auth cookie is firmly established and the fetch succeeds on the first try.

### Proposed Fix

#### Fix 1A: Deduplicate Workspace Creation

**File**: `App.jsx` ~line 4616

Before auto-creating, **wait for the workspace list fetch to complete** instead of racing against it.

```js
// Add a "workspaceListLoaded" state that starts false and becomes true
// after the first successful fetch of /workspaces
const [workspaceListLoaded, setWorkspaceListLoaded] = useState(false)

useEffect(() => {
  if (!needsWorkspaceRedirect) return
  if (!workspaceListLoaded) return  // <-- wait for list before deciding
  if (workspaceOptions.length > 0) {
    // Navigate to first workspace
    ...
  } else if (!autoCreateAttempted.current) {
    autoCreateAttempted.current = true
    handleCreateWorkspaceSubmit('My Workspace')...
  }
}, [needsWorkspaceRedirect, workspaceListLoaded, workspaceOptions, ...])
```

The workspace list fetch already exists — just need to track its completion.

**Alternative**: Make the frontend auto-create call also use `is_default=True`, matching the backend's idempotency path.

#### Fix 1B: Unified Post-Signup Navigation

Instead of redirecting to `/` (which triggers the multi-step redirect dance), the token-exchange endpoint should return the workspace ID (from eager provisioning) so the frontend can navigate directly to `/w/{id}/setup`.

**Backend** (`auth_router_neon.py:2168`): The `_eager_workspace_provision()` call is already awaited and returns `workspace_id`. Include it in the token-exchange response.

**Frontend** (`AuthCallbackPage`): If `payload.workspace_id` exists, navigate to `/w/{id}/setup` directly instead of `/`.

This eliminates the redirect-to-`/` → list-fetch → auto-create dance entirely.

#### Fix 1C: Investigate and Fix Capabilities Fetch Failure

**Action**: Add logging/error tracking to the capabilities fetch to understand WHY it fails after the setup page redirect.

**File**: `useCapabilities.js`

The retry logic already exists (retries every 2s when `featureCount === 0`). The issue is that retries keep failing. Investigate:

1. Is the session cookie present in the request? Add `credentials: 'include'` if missing.
2. Is there a timing issue where the capabilities fetch fires before the auth redirect completes?
3. Does the `window.location.assign()` to the setup page cause a cookie propagation delay?

**Interim mitigation**: When the setup page detects `runtimeReady && !capabilitiesLoaded`, expose a manual "Continue to workspace" button after a timeout (e.g., 5s), bypassing the capabilities gate. The capabilities will load once the user is in the workspace and the app re-fetches.

#### ~~Fix 1D: Setup Page Self-Sufficient Capabilities Check~~ (REMOVED)

~~Previously proposed adding a second capabilities polling loop inside WorkspaceSetupPage.~~ This would duplicate the existing `useCapabilities` hook polling, doubling request volume. If the fetch is failing due to an auth/network issue, polling twice doesn't help. Removed in favor of Fix 1C (investigate root cause).

---

## Issue 2: PI Agent Filesystem Path Mismatch

### Root Cause Analysis

The PI agent and file API use **different workspace root paths**.

#### File API Path Resolution

`files/router.py` → `resolve_workspace_context(request)` → `workspace/paths.py:resolve_workspace_root()`:
- Reads `x-workspace-id` header → resolves to `base_root / workspace_id`
- `base_root` comes from `BORING_UI_WORKSPACE_ROOT` env var or `cwd()`

In hosted mode with Fly, `BORING_UI_WORKSPACE_ROOT` is set to `/workspace` on the provisioned machine (`fly.workspaces.toml:19`). The file API correctly operates on `/workspace`.

#### PI Agent Path Resolution

`pi_harness.py:316`: Spawns Node.js process with `cwd=str(self._repo_root())` — the **boring-ui repo root**, not the workspace root.

`tools.mjs:7`: `WORKSPACE_ROOT = process.env.BORING_UI_WORKSPACE_ROOT || process.cwd()`

`pi_harness.py:357-368` (`_process_env()`): Uses `os.environ.copy()`, which **will** propagate `BORING_UI_WORKSPACE_ROOT` if it's set in the parent process environment.

**In Fly workspace machines**: `fly.workspaces.toml` sets `BORING_UI_WORKSPACE_ROOT = "/workspace"` at the container level. Since `_process_env()` copies `os.environ`, the PI service **should** inherit it. The header-based path (`x-boring-workspace-root` sent in `_proxy_headers()` at line 376) is ignored by `resolveSessionContext()`, but the env var propagation should work.

**In local development**: `BORING_UI_WORKSPACE_ROOT` is typically not set. Both the file API and PI service fall back to `cwd()`, which is the same directory — so the paths should match.

#### Where the Bug Manifests

The mismatch is most likely to occur when:
1. **The PI harness runs in a different process context** than the main backend (e.g., if the env var is set after the PI process starts, or cleared by `_process_env()` overrides)
2. **Multi-workspace mode**: Different workspaces need different roots, but `WORKSPACE_ROOT` in `tools.mjs` is a module-level constant, set once at import time. Even if the env var is correct at startup, it can't vary per session.
3. **The `x-boring-workspace-root` header IS sent** (`pi_harness.py:376`) with the correct per-request workspace root, but `resolveSessionContext()` **never reads it** — this is the definitive bug for the per-session case.

**TODO**: Verify whether the bug actually manifests in Fly production (where env var propagation should work) or only in specific scenarios. The user reported it in "backend mode" — confirm which deployment mode.

### Proposed Fix

#### Fix 2A: Pass Workspace Root to PI Service via Session Context (Primary Fix)

This enables **per-session** workspace root, which is necessary for multi-workspace support.

**File**: `tools.mjs`

1. Add `workspaceRoot` to `resolveSessionContext()`:
```js
export function resolveSessionContext(payload = {}, headers = {}, env = process.env) {
  // ... existing fields ...
  const workspaceRoot = String(
    payload.workspace_root
    || payload.workspaceRoot
    || headers['x-boring-workspace-root']
    || headers['X-Boring-Workspace-Root']
    || env.BORING_UI_WORKSPACE_ROOT
    || process.cwd()
  ).trim()

  return { workspaceId, internalApiToken, backendUrl, workspaceRoot }
}
```

2. Pass `workspaceRoot` into `createWorkspaceTools()` and use it instead of the module-level constant:
```js
export function createWorkspaceTools(context) {
  const root = context.workspaceRoot || WORKSPACE_ROOT
  return [{
    name: 'exec_bash',
    // ...
    execute: async (_toolCallId, params) => {
      const cwd = params?.cwd ? ... : '.'
      const fullCwd = cwd === '.' ? root : `${root}/${cwd}`
      // ...
      const { stdout, stderr } = await execAsync(command, {
        cwd: fullCwd,
        env: { ...process.env, HOME: root },
      })
    },
  }]
}
```

3. Update `buildSessionSystemPrompt()` to use the context's workspace root:
```js
export function buildSessionSystemPrompt(basePrompt, context = {}) {
  const root = context.workspaceRoot || WORKSPACE_ROOT
  return [basePrompt, `Workspace root: ${root}.`, ...].join(' ')
}
```

**File**: `server.mjs`

4. Store `workspaceRoot` on session (alongside `workspaceId`, `backendUrl`):
```js
function applySessionContext(session, nextContext = {}) {
  if (nextContext.workspaceRoot) session.workspaceRoot = nextContext.workspaceRoot
  // ... existing fields ...
  const toolContext = {
    workspaceRoot: session.workspaceRoot,
    workspaceId: session.workspaceId,
    // ...
  }
  session.agent.setTools(createWorkspaceTools(toolContext))
}
```

#### Fix 2B: Verify Env Var Propagation in Fly (Investigation, Not Code Change)

`_process_env()` already does `os.environ.copy()`. In Fly workspace machines, `BORING_UI_WORKSPACE_ROOT=/workspace` is set at the container level. This should propagate automatically.

**Action**: Verify this works in production by checking:
1. `fly ssh console -a boring-ui-edge -C "env | grep BORING_UI_WORKSPACE_ROOT"`
2. Inside a running workspace, check the PI service's actual working directory

If env var propagation works, Fix 2A is still needed for multi-workspace correctness but the single-workspace production bug may already be non-existent.

---

## Issue 3: Tool Usage Not Visible in Chat

### Root Cause Analysis

The PI service SSE stream **filters out all tool usage**, sending only final text.

#### Server-side filtering

`server.mjs:76-85` — `textFromMessage()` explicitly drops non-text content blocks:
```js
function textFromMessage(message) {
  return content
    .filter((item) => item?.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text)
    .join(' ')
}
```

`server.mjs:221-231` — The subscriber only emits `delta` with `{ text }`:
```js
const unsubscribe = session.agent.subscribe((event) => {
  if (event.type === 'message_update' && event.message?.role === 'assistant') {
    assistantText = textFromMessage(event.message)  // text only
    sendSse(res, 'delta', { text: assistantText })
  }
})
```

Tool call content blocks (pi-agent-core uses `type: 'toolCall'`, not `'tool_use'`) and tool results are completely invisible.

#### pi-agent-core Event Model

The `@mariozechner/pi-agent-core` Agent emits these event types via `subscribe()`:
- `agent_start`, `agent_end`
- `turn_start`, `turn_end` (turn_end includes `toolResults: ToolResultMessage[]`)
- `message_start`, `message_update`, `message_end`
- `tool_execution_start`, `tool_execution_update`, `tool_execution_end`

**There is NO `'tool_result'` event type.** Tool results arrive via:
- `turn_end` event with `event.toolResults` array
- `message_start`/`message_end` where `event.message.role === 'toolResult'`

Assistant message content blocks use `type: 'toolCall'` (not `'tool_use'`):
```typescript
interface ToolCall {
  type: "toolCall";
  id: string;
  name: string;
  arguments: Record<string, any>;
}
```

#### Frontend-side

`backendAdapter.jsx:10-18` — Messages have only `role` and `text`. No rendering for tool blocks. The bubble just renders `message.text`.

**Meanwhile**, the codebase already has rich, portable tool renderers used by ClaudeStreamChat:
- `ToolUseBlock.jsx` — collapsible wrapper (props: `toolName`, `description`, `status`, `children`)
- `BashToolRenderer.jsx` — command + output display (props: `command`, `output`, `exitCode`, `status`)
- `ReadToolRenderer.jsx`, `WriteToolRenderer.jsx`, `EditToolRenderer.jsx`, etc.

These renderers are **fully portable** — they use local state only, have no coupling to ClaudeStreamChat, and accept simple scalar props. They can be dropped directly into the PI backend adapter.

### Proposed Fix

#### Fix 3A: Stream Full Content Blocks from PI Service

**File**: `server.mjs`

Replace the text-only subscriber with one that streams full content blocks:

```js
const unsubscribe = session.agent.subscribe((event) => {
  if (closed) return

  // Stream full message content (text + toolCall blocks)
  if (event.type === 'message_update' && event.message?.role === 'assistant') {
    const content = event.message.content
    assistantText = textFromMessage(event.message)
    if (Array.isArray(content)) {
      sendSse(res, 'content', { content })
    } else {
      sendSse(res, 'delta', { text: assistantText })
    }
    return
  }

  // Stream tool execution progress
  if (event.type === 'tool_execution_start') {
    sendSse(res, 'tool_start', {
      tool_call_id: event.toolCallId,
      name: event.toolName,
    })
    return
  }
  if (event.type === 'tool_execution_end') {
    sendSse(res, 'tool_end', {
      tool_call_id: event.toolCallId,
      result: event.result,
    })
    return
  }

  // Stream tool result messages
  if (event.type === 'message_end' && event.message?.role === 'toolResult') {
    sendSse(res, 'tool_result_message', {
      content: event.message.content,
    })
    return
  }

  if (event.type === 'message_end' && event.message?.role === 'assistant') {
    assistantText = textFromMessage(event.message)
  }
})
```

**Note**: The exact event field names (`event.toolCallId`, `event.toolName`, `event.result`) need to be verified against the pi-agent-core source. The types.d.ts shows the event structure but field names may differ.

The `done` event should also include full content:
```js
sendSse(res, 'done', {
  text: assistantText,
  content: session.agent.state.messages.at(-1)?.content || [],
  session: toSessionSummary(session),
})
```

#### Fix 3B: Render Tool Blocks in backendAdapter.jsx

**File**: `backendAdapter.jsx`

1. Store structured content instead of flat text:
```js
const [messages, setMessages] = useState([])  // now includes content blocks
```

2. Handle `content` and tool events from SSE.

3. Render tool blocks using existing components, mapping pi-agent-core's `type: 'toolCall'` to the renderer props:
```jsx
{message.content.map((part, i) => {
  if (part.type === 'text') {
    return <div key={i} className="pi-backend-bubble">{part.text}</div>
  }
  if (part.type === 'toolCall' && part.name === 'exec_bash') {
    return (
      <BashToolRenderer
        key={part.id}
        command={part.arguments?.command || ''}
        output={toolResults[part.id]?.stdout || ''}
        exitCode={toolResults[part.id]?.exitCode}
        status={toolResults[part.id] ? 'complete' : 'running'}
      />
    )
  }
  if (part.type === 'toolCall') {
    return (
      <ToolUseBlock key={part.id} toolName={part.name} status={toolResults[part.id] ? 'complete' : 'running'}>
        <pre>{JSON.stringify(part.arguments, null, 2)}</pre>
      </ToolUseBlock>
    )
  }
  return null
})}
```

**CSS requirement**: The tool renderers use CSS custom properties from `chatThemeVars`. The PI backend adapter's container must include these CSS variables (or import the shared styles).

#### Fix 3C: History Endpoint — Return Full Content

**File**: `server.mjs:95-104`

`toUiMessages()` currently strips tool blocks. Update to include full content and include `toolResult` messages:

```js
function toUiMessages(messages) {
  return messages
    .filter(m => m.role === 'user' || m.role === 'assistant' || m.role === 'toolResult')
    .map((message, index) => ({
      id: message.id || `msg-${index}`,
      role: message.role === 'assistant' ? 'assistant' : message.role === 'toolResult' ? 'toolResult' : 'user',
      text: textFromMessage(message),
      content: Array.isArray(message.content) ? message.content : undefined,
      timestamp: message.timestamp || Date.now(),
    }))
}
```

---

## Implementation Priority

| Fix | Impact | Effort | Priority |
|-----|--------|--------|----------|
| **1A** Deduplicate workspace creation | High (prevents double-create) | Low | P0 |
| **1B** Direct post-signup navigation | High (eliminates redirect dance) | Medium | P0 |
| **1C** Investigate capabilities fetch failure | High (unblocks stuck setup page) | Medium | P0 |
| **2A** Dynamic workspace root per session | Critical (files visible to agent) | Medium | P0 |
| **2B** Verify env var propagation in Fly | Low (investigation only) | Low | P0 |
| **3A** Stream full content blocks | High (tool visibility) | Medium | P1 |
| **3B** Render tool blocks in adapter | High (tool visibility) | Medium | P1 |
| **3C** Full content in history | Low (consistency) | Low | P2 |

## Execution Order

1. **Fix 2A + 2B** — PI agent path mismatch (most critical functional bug; 2B is investigation to scope the issue)
2. **Fix 1A + 1C** — Stop duplicate creation + investigate stuck setup page root cause
3. **Fix 1B** — Direct navigation (eliminates root cause of redirect dance)
4. **Fix 3A + 3B** — Tool usage display (new feature, can be iterated on)
5. **Fix 3C** — History consistency

## Open Questions

1. **Which deployment mode did the user observe the path mismatch in?** If it's Fly workspace machines, the env var propagation may already work and the bug is elsewhere.
2. **Why does the capabilities fetch fail on the setup page?** Need to add instrumentation (console.log the fetch response status, headers, cookie presence) to the capabilities hook during the setup page flow.
3. **Are there other consumers of the PI SSE stream** that would break if we change the event format? The `done` event format change (adding `content`) should be backward-compatible but needs verification.
