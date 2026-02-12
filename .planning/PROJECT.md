# boring-ui: Sandbox Agent Integration

## What This Is

boring-ui is a web-based IDE interface for coding agents. This project adds sandbox-agent as an alternative chat interface with a generic provider abstraction supporting local subprocess execution (now) and remote Modal/E2B sandboxes (future).

## Core Value

Users can interact with coding agents through a flexible sandbox system that abstracts away the underlying execution environment.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Backend provider abstraction (SandboxProvider interface + LocalProvider)
- [ ] Backend router (proxy requests to sandbox-agent, status + log endpoints)
- [ ] Frontend SandboxChat panel integration with Dockview
- [ ] End-to-end sandbox-agent subprocess lifecycle management

### Out of Scope

- Modal/E2B remote sandbox provider — deferred to v2, foundation laid with interface
- Authentication/token support for sandbox-agent — using `--no-token` for local dev
- Multiple concurrent sandbox instances — single "default" sandbox for now

## Context

**Existing codebase:**
- Python FastAPI backend with modular router architecture (`src/back/boring_ui/api/modules/`)
- React frontend with Dockview panels, Zustand state, capability gating
- Existing Claude Code integration via WebSocket streaming (`/ws/claude-stream`)

**sandbox-agent:**
- Rust binary with TypeScript SDK, exposes REST + SSE API on port 2468
- Wraps Claude Code, Codex, OpenCode, Amp CLIs
- Inspector UI components available for reuse

**Integration approach:**
- Backend proxies requests to sandbox-agent subprocess
- Frontend uses existing panel registration pattern
- Provider abstraction allows swapping local/remote execution

## Constraints

- **Tech stack**: Must integrate with existing FastAPI + React architecture
- **Dependency**: sandbox-agent CLI must be available via `npx @sandbox-agent/cli`
- **Port**: Default sandbox-agent port is 2468, configurable via env

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Provider abstraction | Support both local subprocess and future remote sandboxes | — Pending |
| Proxy architecture | Backend mediates all sandbox-agent requests | — Pending |
| Single default sandbox | Simplify initial implementation | — Pending |

---
*Last updated: 2026-02-09 after project initialization*
