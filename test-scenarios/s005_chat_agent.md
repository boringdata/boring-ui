# S-005: Chat with Agent

## Preconditions
- User authenticated, workspace selected and in `ready` state.
- Workspace runtime supports agent sessions.
- Anthropic API key configured in workspace runtime.

## Steps
1. User opens chat panel.
2. Frontend creates agent session via `POST /w/{id}/api/v1/agent/sessions`.
3. User types a message and sends.
4. Frontend sends input via `POST /w/{id}/api/v1/agent/sessions/{sid}/input`.
5. Frontend streams response via `GET /w/{id}/api/v1/agent/sessions/{sid}/stream` (SSE/WebSocket).
6. Agent response appears in chat panel.
7. User sends follow-up → repeat steps 4-6.
8. User stops session via `POST /w/{id}/api/v1/agent/sessions/{sid}/stop`.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `POST /w/{id}/api/v1/agent/sessions` | 201 | `session_id` |
| 4 | `POST /w/{id}/api/v1/agent/sessions/{sid}/input` | 200 | Acknowledged |
| 5 | `GET /w/{id}/api/v1/agent/sessions/{sid}/stream` | 200 (SSE) | Streaming tokens |
| 8 | `POST /w/{id}/api/v1/agent/sessions/{sid}/stop` | 200 | Session stopped |

### UI
- Chat panel with message input.
- Streaming response display (tokens appear incrementally).
- Session indicator (active/stopped).
- Message history preserved within session.

## Evidence Artifacts
- Screenshot: Chat panel with user message and agent response.
- API response: Session creation.
- SSE/WS trace: Streaming response tokens.
- Screenshot: Stopped session state.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| API key not configured | 500 or agent error message in chat |
| Session not found | 404 |
| Runtime down during stream | Stream error event, UI shows reconnection |
| CSRF token missing on POST | 403 `csrf_validation_failed` |
