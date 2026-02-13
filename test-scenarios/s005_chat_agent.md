# S-005: Chat with Agent

## Preconditions
- User authenticated and inside a `ready` workspace.
- Chat panel open or available to open.
- Agent (Claude) API key configured for the workspace runtime.
- MCP tools registered and available.

## Steps
1. User opens chat panel (or it is already visible in default layout).
2. Chat panel shows empty conversation or previous session.
3. User types a message and sends it.
4. App calls `POST /w/{workspace_id}/api/v1/sessions` to create or resume session.
5. App initiates streaming via SSE or WebSocket to `/w/{workspace_id}/api/v1/stream`.
6. Agent response streams in, token by token.
7. If agent uses MCP tool (e.g., file read), tool call is visible in chat.
8. Agent response completes.
9. User sends follow-up message.
10. Conversation context maintained across turns.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 4 | `POST /w/{id}/api/v1/sessions` | 200/201 | `session_id` |
| 5 | `POST /w/{id}/api/v1/stream` | 200 (SSE) | Streaming chunks with `session_id` |
| 7 | Tool call event | — | `tool_name`, `tool_input`, `tool_result` in stream |
| 8 | Stream end event | — | `stop_reason: end_turn` |

### UI
- Chat panel displays user message immediately.
- Agent response streams in progressively.
- Tool calls shown as expandable blocks (tool name + result).
- Typing/streaming indicator while response is in progress.
- Conversation history scrollable.

## Evidence Artifacts
- Screenshot: chat panel with user message and streamed agent response.
- Screenshot: tool call expansion showing MCP tool usage.
- API response: session creation response.
- SSE/WS stream capture showing chunk-by-chunk response.
- `X-Request-ID` header present and consistent across stream.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| No session_id on stream call | 400 `session_id_required` |
| Non-member access to session | 403 `forbidden` |
| Agent API key missing/invalid | Error message in chat, not unhandled crash |
| Stream connection drops mid-response | Reconnection attempt or error shown |
| Duplicate stop calls | Idempotent (no error) |
| MCP tool denied by sandbox policy | Tool error returned in stream, agent adapts |
