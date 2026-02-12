# Phase 1: Backend Provider Abstraction - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Create the SandboxProvider abstract interface and LocalProvider implementation that manages sandbox-agent subprocess lifecycle. This phase focuses on the provider abstraction layer — API routing and frontend integration are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Process spawning
- Invoke sandbox-agent via **direct binary path**, not npx
- Binary path from **SANDBOX_AGENT_BIN** environment variable (with sensible default like `sandbox-agent`)
- If binary not found at startup: **fail fast with clear error** — app won't start
- Working directory from **SANDBOX_WORKSPACE** env var, default to cwd

### Lifecycle management
- Startup timeout: **30 seconds** to become healthy
- Crash recovery: **auto-restart with exponential backoff** (1s, 2s, 4s, max 3 attempts)
- Startup timing: **eager at app startup** — sandbox-agent starts when boring-ui starts
- Shutdown: **SIGTERM then SIGKILL after 5 seconds** — standard graceful pattern

### Log handling
- Ring buffer size: **1000 lines**
- Capture: **stdout + stderr merged** into single stream
- Timestamps: **add ISO timestamp prefix** on capture
- Persistence: Claude's discretion (likely in-memory only for v1)

### Health checking
- Startup polling: **500ms interval** until healthy or timeout
- Ongoing monitoring: **yes, periodic checks** every 10 seconds
- Failure threshold: **3 consecutive failures** before marking unhealthy and triggering restart

### Claude's Discretion
- Log persistence (in-memory vs file) — lean toward in-memory for simplicity
- Exact backoff timing implementation
- Health check HTTP client configuration (timeouts, retries)
- Internal state machine for sandbox lifecycle states

</decisions>

<specifics>
## Specific Ideas

- Direct binary invocation aligns with production deployment patterns (not relying on npx/npm)
- Eager startup ensures sandbox-agent is ready when first request arrives
- Exponential backoff for crash recovery prevents restart storms

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-backend-provider*
*Context gathered: 2026-02-09*
