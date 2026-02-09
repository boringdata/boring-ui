# Phase 2: Backend Router - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Create API routes for sandbox status, logs, and proxying requests to sandbox-agent. This is the HTTP layer that sits between frontend and the provider abstraction from Phase 1.

</domain>

<decisions>
## Implementation Decisions

### Design principle
- **Drop-in replacement** for existing claude-stream patterns
- Follow existing router module structure in `src/back/boring_ui/api/modules/`
- Mirror error handling and response formats from existing routers

### Proxy behavior
- Timeout: Match existing patterns (likely 60s for long-running requests)
- SSE: Pass-through streaming (sandbox-agent uses SSE for chat responses)
- Headers: Forward all except Host (standard proxy pattern)

### Error responses
- If sandbox not running: Return 503 with clear message (provider handles auto-start)
- Format: JSON matching existing API error patterns

### Log endpoints
- `/api/sandbox/status` — sandbox info from provider
- `/api/sandbox/logs` — buffered logs with `?limit=` param
- `/api/sandbox/logs/stream` — SSE stream (heartbeat: Claude's discretion)

### Authentication
- No additional auth — reuse boring-ui's existing auth patterns
- Local dev: no auth (matches current setup)

### Claude's Discretion
- SSE heartbeat interval
- Specific header filtering rules
- Request/response logging verbosity

</decisions>

<specifics>
## Specific Ideas

- Mirror the module structure of existing routers (git, files, stream)
- Proxy catch-all route handles all sandbox-agent API paths
- Lifespan integration for startup/shutdown matches existing app.py patterns

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-backend-router*
*Context gathered: 2026-02-09*
