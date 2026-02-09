# Roadmap: boring-ui Sandbox Agent Integration

**Created:** 2026-02-09
**Core Value:** Flexible sandbox system abstracting execution environment

## Milestone: v1.0 — Local Sandbox Integration

### Phase 1: Backend Provider Abstraction
**Requirements:** PROV-01, PROV-02, PROV-03, PROV-04, PROV-05
**Plans:** 3 plans in 3 waves

**Goal:** Create SandboxProvider abstract interface and LocalProvider implementation that manages sandbox-agent subprocess lifecycle with health checking, log capture, and crash recovery.

**Files to create:**
- `src/back/boring_ui/api/modules/sandbox/__init__.py`
- `src/back/boring_ui/api/modules/sandbox/provider.py`
- `src/back/boring_ui/api/modules/sandbox/providers/__init__.py`
- `src/back/boring_ui/api/modules/sandbox/providers/local.py`
- `src/back/boring_ui/api/modules/sandbox/providers/modal.py` (stub)
- `src/back/boring_ui/api/modules/sandbox/manager.py`

**Plans:**
- [ ] 01-01-PLAN.md — SandboxProvider ABC and types (wave 1)
- [ ] 01-02-PLAN.md — LocalProvider implementation (wave 2)
- [ ] 01-03-PLAN.md — SandboxManager orchestration (wave 3)

**Deliverables:**
- SandboxProvider ABC with full interface
- LocalProvider spawns sandbox-agent subprocess
- Log capture with ring buffer
- Health check polling
- SandboxManager orchestrator

---

### Phase 2: Backend Router
**Requirements:** ROUT-01, ROUT-02, ROUT-03, ROUT-04, ROUT-05

Create API routes for status, logs, and proxying to sandbox-agent.

**Files to create:**
- `src/back/boring_ui/api/modules/sandbox/router.py`

**Files to modify:**
- `src/back/boring_ui/api/app.py` — add lifespan + router
- `pyproject.toml` — add httpx dependency

**Deliverables:**
- Status endpoint
- Logs endpoint with limit
- SSE log stream
- Proxy catch-all route
- Lifespan integration

---

### Phase 3: Frontend Panel
**Requirements:** FRNT-01, FRNT-02, FRNT-03, FRNT-04

Create SandboxChat panel component and integrate with Dockview.

**Files to create:**
- `src/front/components/sandbox-chat/index.jsx`
- `src/front/components/sandbox-chat/api.js`
- `src/front/components/sandbox-chat/overrides/theme.css`

**Files to modify:**
- `src/front/vite.config.js` — add vendor path if using submodule
- Panel registration (Dockview factory)

**Deliverables:**
- SandboxChatPanel component
- Panel factory registration
- Status display on mount
- Theme CSS overrides

---

### Phase 4: Integration Testing
**Requirements:** INTG-01, INTG-02, INTG-03

End-to-end verification of sandbox lifecycle and configuration.

**Deliverables:**
- Verify lazy sandbox initialization
- Verify clean shutdown
- Test environment variable configuration
- Manual UAT with sandbox-agent

---

## Verification Checklist

1. `npm run dev` → sandbox-agent starts when panel opens
2. `curl http://localhost:8000/api/sandbox/status` → returns provider info
3. `curl http://localhost:8000/api/sandbox/v1/health` → proxy works
4. `curl http://localhost:8000/api/sandbox/logs` → subprocess logs
5. Open SandboxChat panel, send message with mock agent

---
*Roadmap created: 2026-02-09*
