# WebSocket Contracts Catalog

**Version:** 1.0
**Date:** 2026-02-12
**Purpose:** Canonical contract baseline for PTY and Claude stream WebSocket endpoints used by frontend components.

---

## Overview

This document catalogs the WebSocket message envelopes, control frames, close semantics, and error behaviors expected by frontend components for the two WebSocket endpoints:

1. **PTY WebSocket** (`/ws/pty`) - Shell terminal sessions
2. **Claude Stream WebSocket** (`/ws/claude-stream`) - Claude AI chat sessions

These contracts define the stable interface between frontend and backend. Any changes to message structure, control frames, or session semantics must maintain backward compatibility or follow a versioned migration path.

---

## 1. PTY WebSocket Contract

### 1.1 Endpoint

```
WebSocket: /ws/pty
```

### 1.2 Connection Parameters

Query parameters sent by frontend:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | No | Session ID to reconnect to existing session |
| `provider` | string | Yes | Provider name (e.g., 'shell', 'claude') |
| `session_name` | string | No | Human-readable session name |
| `resume` | string | No | "1" or "true" to resume session |
| `force_new` | string | No | "1" or "true" to force new session |

**Provider Validation:**
- Provider must exist in `config.pty_providers`
- Invalid provider → close with code `4003`

### 1.3 Client → Server Messages

Frontend sends these message types:

#### 1.3.1 Input Message
```json
{
  "type": "input",
  "data": "ls\n"
}
```

**Behavior:** Write raw input to PTY process stdin.

**Fallback:** Raw text (non-JSON) is treated as `{ "type": "input", "data": "<raw-text>" }`

#### 1.3.2 Resize Message
```json
{
  "type": "resize",
  "rows": 24,
  "cols": 80
}
```

**Behavior:** Resize PTY terminal dimensions.

**Defaults:** `rows=24`, `cols=80` if missing.

#### 1.3.3 Ping Message
```json
{
  "type": "ping"
}
```

**Response:** Server immediately sends `{ "type": "pong" }`

### 1.4 Server → Client Messages

Backend sends these message types:

#### 1.4.1 Output Message
```json
{
  "type": "output",
  "data": "file1.txt\nfile2.txt\n"
}
```

**Behavior:** Terminal output from PTY process. Frontend writes to xterm.js display and appends to history buffer.

**Frequency:** Continuous stream during PTY output.

#### 1.4.2 Pong Message
```json
{
  "type": "pong"
}
```

**Trigger:** Response to `{ "type": "ping" }` from client.

#### 1.4.3 History Message
```json
{
  "type": "history",
  "data": "Welcome to bash...\n$ ls\nfile1.txt\n"
}
```

**Behavior:** Sent on session resume to restore scrollback history. Frontend applies this to xterm.js and replaces local history.

**Timing:** Sent immediately after WebSocket open if session has stored history.

**Priority:** Server history takes precedence over client localStorage history.

#### 1.4.4 Error Message
```json
{
  "type": "error",
  "data": "Failed to spawn process: command not found"
}
```

**Behavior:** Error notification. Frontend displays in terminal with `[bridge]` prefix.

#### 1.4.5 Exit Message
```json
{
  "type": "exit",
  "code": 0
}
```

**Behavior:** PTY process exited. Frontend displays exit code.

**Code:** Exit code from process (0 = success, non-zero = error, "unknown" if unavailable).


### 1.5 WebSocket Close Codes

| Code | Reason | Meaning |
|------|--------|---------|
| `4003` | `Unknown provider: {name}. Available: [...]` | Invalid provider in query params |
| `4004` | `{error message}` | Session creation/validation error |
| `1000` | Normal closure | Client or server closed connection normally |
| `1006` | Abnormal closure | Connection lost (network error, server crash) |

### 1.6 Reconnection Semantics

**Frontend Behavior (from Terminal.jsx):**

1. **Initial Connection:**
   - Connect to `/ws/pty?session_id={id}&provider={provider}`
   - If `session_id` provided and session exists → resume
   - If `session_id` provided but not found → new session with that ID
   - If no `session_id` → backend generates new UUID

2. **History Loading:**
   - Frontend has localStorage history (200KB limit, keyed by session_id)
   - Backend sends `{ "type": "history" }` if session has server history
   - **Priority:** Server history > Local history (server history clears local)
   - **Fallback:** If no server history after 200ms, apply local history

3. **Reconnection on Disconnect:**
   - Max retries: 10
   - Initial retry delay: 500ms
   - On retry count >= 3, show "Unable to connect. Retrying..." message
   - On max retries exceeded, show "Max retries reached. Click 'New session' to try again."

4. **Session Persistence:**
   - Session remains alive on server while at least one client is connected
   - Idle TTL: 30 seconds (backend `PTY_IDLE_TTL`, configurable via env var)
   - Multiple clients can connect to same session (shared view)

### 1.7 Session Management Invariants

**Backend Guarantees (from pty/service.py):**

1. **Session Registry:**
   - Global singleton `PTYService` maintains session registry
   - Sessions keyed by UUID
   - Session reuse: `get_or_create_session(session_id)` returns existing if alive

2. **History Persistence:**
   - Rolling buffer: Last 200KB of output (`PTY_HISTORY_BYTES`, configurable via env var)
   - Sent as `{ "type": "history" }` on first client connect

3. **Multi-Client Support:**
   - Multiple WebSocket clients can attach to same session
   - Output broadcast to all connected clients
   - Input from any client goes to shared PTY

4. **Cleanup:**
   - Idle sessions (no clients) cleaned up after TTL
   - Process terminated when session destroyed

---

## 2. Claude Stream WebSocket Contract

### 2.1 Endpoint

```
WebSocket: /ws/claude-stream
```

### 2.2 Connection Parameters

Query parameters sent by frontend:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string (UUID) | No | auto-generated | Session ID for conversation |
| `resume` | string | No | "0" | "1" or "true" to resume existing session |
| `force_new` | string | No | "0" | "1" or "true" to terminate existing and start fresh |
| `mode` | string | No | "ask" | UI permission mode: "ask", "act", or "plan" |
| `model` | string | No | - | Claude model: "sonnet", "opus", "haiku" |
| `allowed_tools` | string (CSV) | No | - | Comma-separated allowed tool names |
| `disallowed_tools` | string (CSV) | No | - | Comma-separated disallowed tool names |
| `max_thinking_tokens` | integer | No | - | Maximum extended thinking tokens |
| `max_turns` | integer | No | - | Maximum conversation turns |
| `max_budget_usd` | float | No | - | Maximum spend budget in USD |
| `file` | string[] | No | - | File specs in format `{id}:{path}` (multi-value) |
| `files` | string (CSV) | No | - | Alternative CSV format for file specs |
| `test_events` | string | No | "0" | "1" or "true" to enable test event triggers |

**Session ID Validation:**
- Must be valid UUID format
- Invalid UUID → backend generates new UUID and logs warning

**Mode Mapping:**
- Frontend modes → backend `--permission-mode`
- "ask" → ask (default)
- "act" → act
- "plan" → plan

### 2.3 Client → Server Messages

#### 2.3.1 User Message
```json
{
  "type": "user",
  "message": "What files are in this directory?",
  "context_files": ["src/App.jsx", "package.json"],
  "images": [
    {
      "data": "data:image/png;base64,...",
      "mimeType": "image/png"
    }
  ]
}
```

**Message Formats:**
- `message` can be string, object with `content`, or array of content blocks
- `content` blocks: `{ "type": "text", "text": "..." }` or `{ "type": "image", "data": "...", "mimeType": "..." }`
- `context_files` prepended as `@file` references
- `images` appended as image content blocks

**Fallback:** Raw text (non-JSON) → `{ "type": "user", "message": "<raw-text>" }`

#### 2.3.2 Command Message
```json
{
  "type": "command",
  "command": "/help"
}
```

**Behavior:** Send CLI command directly to Claude process stdin.

#### 2.3.3 Control Message
```json
{
  "type": "control",
  "subtype": "initialize",
  "capabilities": {
    "supports_images": true,
    "supports_files": true
  }
}
```

**Subtypes:**

- **initialize:** Client sends capabilities on connect. Server echoes back.
- **set_permission_mode:** Change permission mode mid-session
  ```json
  {
    "type": "control",
    "subtype": "set_permission_mode",
    "mode": "acceptEdits"
  }
  ```
  Mode mapping: `default → ask`, `acceptEdits/bypassPermissions/dontAsk → act`, `plan → plan`

- **set_model:** Change Claude model
  ```json
  {
    "type": "control",
    "subtype": "set_model",
    "model": "opus"
  }
  ```

- **set_max_thinking_tokens:** Update thinking token limit
  ```json
  {
    "type": "control",
    "subtype": "set_max_thinking_tokens",
    "max_thinking_tokens": 10000
  }
  ```

#### 2.3.4 Control Response Message
```json
{
  "type": "control_response",
  "request_id": "toolu_write_1",
  "response": {
    "behavior": "allow",
    "updatedInput": {
      "file_path": "README.md",
      "content": "# Updated content"
    }
  }
}
```

**Alternative Fields:**
- `decision` (alias for `behavior`)
- `allow` (boolean) → maps to "allow"/"deny"
- `updated_input` / `updatedInput` (backend accepts both)
- `permission_suggestions` / `permissionSuggestions`

**Behavior Values:**
- "allow" / "grant" / "always" → allow action
- "deny" / "reject" / "block" → deny action
- Default: "allow"

**Permission Suggestions:**
Backend splits suggestions into session-scoped and persistent:
- Session: `{ "type": "setMode", "mode": "acceptEdits", "destination": "session" }`
- Persistent: `{ "type": "setMode", "mode": "acceptEdits", "destination": "persisted" }`

#### 2.3.5 Approval Response (Legacy)
```json
{
  "type": "approval_response",
  "request_id": "toolu_write_1",
  "decision": "allow",
  "tool_input": {
    "file_path": "README.md",
    "content": "Hello"
  }
}
```

**Status:** Legacy format, mapped to `control_response` internally.

#### 2.3.6 Ping Message
```json
{
  "type": "ping"
}
```

**Response:** `{ "type": "pong" }`

#### 2.3.7 Interrupt Message
```json
{
  "type": "interrupt"
}
```

**Behavior:** Send SIGINT to Claude process. Backend responds:
```json
{
  "type": "system",
  "subtype": "interrupted",
  "session_id": "..."
}
```

#### 2.3.8 Restart Message
```json
{
  "type": "restart"
}
```

**Behavior:** Terminate current session, spawn new Claude process with same args. Backend responds:
```json
{
  "type": "system",
  "subtype": "restarted",
  "session_id": "..."
}
```

### 2.4 Server → Client Messages

#### 2.4.1 System Messages

**Connected:**
```json
{
  "type": "system",
  "subtype": "connected",
  "session_id": "a1b2c3d4-...",
  "resumed": false,
  "settings": {
    "model": "sonnet",
    "max_thinking_tokens": null
  }
}
```

**Sent:** Immediately after WebSocket open, before any user messages.

**Error:**
```json
{
  "type": "system",
  "subtype": "error",
  "message": "Failed to start session: Claude process exited unexpectedly."
}
```

**Interrupted:**
```json
{
  "type": "system",
  "subtype": "interrupted",
  "session_id": "..."
}
```

**Restarted:**
```json
{
  "type": "system",
  "subtype": "restarted",
  "session_id": "..."
}
```

**Echo:**
```json
{
  "type": "system",
  "subtype": "echo",
  "payload": { /* original control message */ }
}
```

#### 2.4.2 Assistant Message
```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "id": "msg-abc123",
    "content": [
      {
        "type": "text",
        "text": "I'll list the files for you."
      },
      {
        "type": "tool_use",
        "id": "toolu-xyz",
        "name": "Bash",
        "input": {
          "command": "ls -la",
          "description": "List directory contents"
        }
      }
    ]
  }
}
```

**Content Blocks:**
- `type: "text"` - Plain text response
- `type: "tool_use"` - Tool invocation with `name` and `input`

#### 2.4.3 User Message (Tool Results)
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu-xyz",
        "content": "total 24\ndrwxr-xr-x  5 user  staff  160 Feb 12 10:00 .\n..."
      }
    ]
  }
}
```

**Behavior:** Claude CLI forwards tool results back to model as user messages.

#### 2.4.4 Control Request
```json
{
  "type": "control_request",
  "request_id": "toolu_write_1",
  "request": {
    "subtype": "can_use_tool",
    "tool_name": "Write",
    "tool_use_id": "toolu_write_1",
    "input": {
      "file_path": "README.md",
      "content": "# Hello"
    },
    "permission_suggestions": [
      {
        "type": "setMode",
        "mode": "acceptEdits",
        "destination": "session"
      }
    ]
  }
}
```

**Trigger:** Claude wants to use a tool but needs permission (permission mode is "ask").

**Frontend Action:** Display permission panel, user approves/denies → send `control_response`.

**Other Control Subtypes:**
- `user_question_request` - Claude asking user a question

```json
{
  "type": "control",
  "subtype": "user_question_request",
  "request_id": "quest-1",
  "questions": [
    {
      "question": "Pick a color",
      "header": "Color",
      "multiSelect": false,
      "options": [
        { "label": "Red", "description": "Warm" },
        { "label": "Blue", "description": "Cool" }
      ]
    }
  ]
}
```

#### 2.4.5 Pong Message
```json
{
  "type": "pong"
}
```

### 2.5 Session Management

**Backend Session Registry:**
- Max sessions: Configurable (`MAX_SESSIONS` in service.py)
- Eviction: Idle sessions (no connected clients) evicted when at max
- Session reuse: Same `session_id` → returns existing session if alive
- Option changes: If mode or CLI options change → terminate old, spawn new

**Session States:**
- **New:** No `session_id` or session doesn't exist → create fresh
- **Resume:** `session_id` exists and alive → reconnect to existing
- **Force New:** `force_new=1` → terminate existing (if any), create fresh

**Stored State:**
- Last init message (connected response)
- CLI options (model, max_thinking_tokens, etc.)
- Permission mode
- Capabilities

**Multi-Client Support:**
- Multiple WebSocket clients can connect to same session
- Broadcast: All clients receive same messages
- Control responses from any client → forwarded to Claude process

### 2.6 Close Semantics

**Normal Close:**
- Client closes → remove from session client list
- Last client closes → session remains alive (idle)
- Idle session cleaned up after TTL

**Error Close:**
- Claude process exits unexpectedly → send error, close WebSocket
- Session spawn failure → send error, close WebSocket
- Connection errors → WebSocket close (frontend retries if `shouldReconnect`)

**No Custom Close Codes:** Backend doesn't send custom close codes (relies on standard 1000, 1001, etc.)

### 2.7 Reconnection Behavior (Frontend)

**From ClaudeStreamChat.jsx:**

Frontend implements automatic reconnection for abnormal close events:
- On abnormal close (code 1006 = connection lost) → auto-reconnect after 1 second delay
- On normal close (code 1000/1001 = intentional) → no auto-reconnect
- Session persists on backend (idle) during reconnection
- History stored in localStorage (200 messages max)

**Session Recovery:**
- Next connect with same `session_id` → backend resumes if session alive
- Backend sends last init message to re-sync settings

---

## 3. Contract Invariants

### 3.1 Message Envelope Guarantees

**JSON Structure:**
- All structured messages are valid JSON
- All messages have `type` field (string)
- Subtypes (if present) in `subtype` field

**Fallback Behavior:**
- Invalid JSON → treated as raw text input (PTY: input data, Chat: user message)
- Missing required fields → use defaults or ignore

### 3.2 Session ID Semantics

**Both Endpoints:**
- Session IDs are UUIDs (version 4)
- Empty/invalid session_id → backend generates new UUID
- Same session_id → reconnect to existing session (if alive)
- Sessions persist across WebSocket reconnects

**TTL:**
- PTY: 1 hour idle TTL
- Chat: Configurable idle TTL (eviction when at max sessions)

### 3.3 Error Handling

**Guaranteed Behaviors:**
1. **Invalid provider (PTY):** Close with code 4003
2. **Session not found (PTY):** Send `{ "type": "session_not_found" }`
3. **Process spawn failure (Chat):** Send system error + close
4. **Process exit (PTY):** Send `{ "type": "exit", "code": ... }`
5. **Connection errors:** Standard WebSocket close (1006 abnormal)

**Frontend Expectations:**
- Show user-friendly error messages (not raw errors)
- Prefix system messages with `[bridge]`
- Provide retry/restart options

### 3.4 History and State Persistence

**PTY:**
- Server: 100KB rolling buffer per session
- Client: 200KB localStorage per session
- Server history takes precedence

**Chat:**
- Client: 200 messages in localStorage per session
- Server: Conversation state in Claude session directory
- Last init message cached for resume

### 3.5 Control Frame Consistency

**Ping/Pong:**
- Both endpoints support `{ "type": "ping" }` → `{ "type": "pong" }`
- Used for keepalive and connection health checks

**Resize (PTY only):**
- `{ "type": "resize", "rows": N, "cols": M }`
- Sent on initial connect and container resize events
- Debounced to avoid spam (handled by xterm.js FitAddon)

---

## 4. Known Tolerance and Edge Cases

### 4.1 PTY Edge Cases

**Multiple Clients on Same Session:**
- All clients see same output
- Any client can send input
- Race condition possible if clients send conflicting commands (no locking)

**History Timing:**
- Server history may arrive before or after client renders local history
- Frontend clears local on server history arrival
- 200ms fallback timeout if no server history

**Resize Race:**
- Resize sent before terminal fully open → ignored
- Multiple rapid resizes → backend applies all sequentially

**Process Exit Handling:**
- Exit message sent, but WebSocket stays open briefly
- Frontend shows exit code, connection retries (up to max)

### 4.2 Chat Edge Cases

**Session Option Changes:**
- Changing model/mode/CLI options mid-session → backend spawns new process
- Old process terminated (force=True)
- New process may have different conversation state

**Permission Suggestions:**
- Session-scoped: Applied immediately to current session
- Persisted: Written to CLAUDE.md (backend handles file write)
- Frontend receives mode change as control message

**Approval Response Formats:**
- Backend accepts both `control_response` and `approval_response` (legacy)
- Behavior aliases: "allow"/"grant"/"always" → allow, others → deny

**Test Events (Debug Mode):**
- `test_events=1` enables synthetic events for testing:
  - `__emit_permission__` → trigger fake permission request
  - `__emit_question__` → trigger fake user question
  - `__emit_tool__` → trigger fake tool use

**Init Message Replay:**
- On resume, backend sends stored init message to new client
- Ensures frontend knows session settings without re-querying

### 4.3 Shared Edge Cases

**WebSocket vs HTTP:**
- Capabilities endpoint (`/api/capabilities`) tells frontend if WS endpoints available
- Missing capability → frontend shows error state, doesn't attempt connection

**Session Eviction:**
- Chat: Idle sessions evicted when at MAX_SESSIONS
- PTY: Idle sessions cleaned up after 1 hour
- Frontend detects via close event → shows "session expired" message

---

## 5. Failure Mode Catalog

### 5.1 PTY Failures

| Failure | Close Code | Message | Frontend Action |
|---------|-----------|---------|-----------------|
| Unknown provider | 4003 | "Unknown provider: X" | Show error banner with available providers |
| Session validation error | 4004 | Error message | Show error banner |
| Process spawn failure | - | `{ "type": "error", "data": "..." }` | Display in terminal with [bridge] prefix |
| Process exit (normal) | - | `{ "type": "exit", "code": 0 }` | Display exit code, allow reconnect |
| Process exit (error) | - | `{ "type": "exit", "code": N }` | Display exit code, allow reconnect |
| Network disconnect | 1006 | - | Retry (max 10 times, 500ms delay) |
| Max retries exceeded | - | - | Show "Max retries reached. Click 'New session' to try again." |

### 5.2 Chat Failures

| Failure | Server Message | Frontend Action |
|---------|---------------|-----------------|
| Invalid session_id | Log warning, use new UUID | Continue with new UUID |
| Process spawn failure | `{ "type": "system", "subtype": "error", "message": "..." }` + close | Show error dialog, allow restart |
| Process exit immediately | `{ "type": "system", "subtype": "error", "message": "Session may be in use" }` + close | Show error dialog |
| Backend unreachable | WebSocket error event | Show connection error, allow retry |
| Session evicted | Close event | Show "Session expired", create new session |

---

## 6. Contract Testing Requirements

### 6.1 PTY Contract Tests

**Essential Tests:**
1. Connect with valid provider → open, receive pong on ping
2. Connect with invalid provider → close 4003
3. Send input → receive output echo
4. Send resize → verify terminal dimensions updated
5. Resume session → receive history message
6. Resume non-existent session → receive session_not_found
7. Process exit → receive exit message with code
8. Multiple clients on same session → all receive same output
9. Disconnect and reconnect → session persists

### 6.2 Chat Contract Tests

**Essential Tests:**
1. Connect without session_id → receive connected with new UUID
2. Connect with resume=1 → receive connected with resumed=true
3. Send user message → receive assistant response
4. Tool use workflow → receive control_request, send control_response, receive result
5. Send control (initialize) → receive echo
6. Send interrupt → receive interrupted
7. Send restart → process respawns, receive restarted
8. Change mode mid-session → mode updated, receive confirmation
9. Session eviction → idle session cleaned up

### 6.3 Contract Drift Detection

**Automated Checks:**
- Message schema validation (all fields present and correct types)
- Round-trip tests (send message, verify response structure)
- Close code catalog (ensure no new codes without documentation update)
- History timing tests (server vs local priority)

**Documentation Sync:**
- Contract changes → update this document before merging
- Version bump if breaking change
- Migration guide if schema evolves

---

## 7. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-12 | DustyEagle | Initial baseline catalog |

---

## Appendix A: Message Type Reference

### PTY Client → Server
- `input` - Send input to PTY
- `resize` - Resize terminal
- `ping` - Keepalive

### PTY Server → Client
- `output` - Terminal output
- `pong` - Ping response
- `history` - Session history (on resume)
- `error` - Error message
- `exit` - Process exited
- `session_not_found` - Resume failed

### Chat Client → Server
- `user` - User message
- `command` - CLI command
- `control` - Control message (initialize, set_permission_mode, set_model, etc.)
- `control_response` - Response to control_request
- `approval_response` - Legacy approval response
- `ping` - Keepalive
- `interrupt` - Send SIGINT
- `restart` - Restart session

### Chat Server → Client
- `system` - System messages (connected, error, interrupted, restarted, echo)
- `assistant` - Assistant response
- `user` - Tool results
- `control_request` - Permission request
- `control` - Control messages (user_question_request, set_permission_mode)
- `pong` - Ping response

---

**End of WebSocket Contracts Catalog v1.0**
