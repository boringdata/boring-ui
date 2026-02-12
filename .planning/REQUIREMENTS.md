# Requirements: boring-ui Sandbox Agent Integration

**Defined:** 2026-02-09
**Core Value:** Flexible sandbox system abstracting execution environment

## v1 Requirements

### Backend Provider

- [ ] **PROV-01**: SandboxProvider abstract interface with create/destroy/get_info/get_logs/stream_logs/health_check
- [ ] **PROV-02**: LocalProvider implements subprocess lifecycle (spawn, terminate, wait)
- [ ] **PROV-03**: LocalProvider captures and buffers stdout logs (ring buffer, 1000 lines)
- [ ] **PROV-04**: LocalProvider health check polls /v1/health endpoint
- [ ] **PROV-05**: SandboxManager orchestrates provider with ensure_running pattern

### Backend Router

- [ ] **ROUT-01**: GET /api/sandbox/status returns sandbox info or not_running
- [ ] **ROUT-02**: GET /api/sandbox/logs returns buffered logs with limit param
- [ ] **ROUT-03**: GET /api/sandbox/logs/stream returns SSE log stream
- [ ] **ROUT-04**: Proxy endpoint forwards all requests to sandbox-agent base URL
- [ ] **ROUT-05**: Router integrates with app lifespan for startup/shutdown

### Frontend Panel

- [ ] **FRNT-01**: SandboxChatPanel component wraps sandbox-agent Inspector UI
- [ ] **FRNT-02**: Panel registers with Dockview panel factory
- [ ] **FRNT-03**: Panel fetches status on mount, shows connection state
- [ ] **FRNT-04**: CSS overrides match boring-ui theme

### Integration

- [ ] **INTG-01**: Sandbox starts automatically when panel opens (lazy init)
- [ ] **INTG-02**: Sandbox shuts down cleanly on app shutdown
- [ ] **INTG-03**: Environment variables configure provider/port/workspace

## v2 Requirements

### Remote Providers

- **MODAL-01**: ModalProvider creates Modal sandbox with sandbox-agent image
- **MODAL-02**: ModalProvider returns public URL for proxying
- **MODAL-03**: ModalProvider handles auto-cleanup on timeout
- **E2B-01**: E2BProvider alternative for E2B sandbox service

### Multi-Sandbox

- **MULTI-01**: SandboxManager supports multiple named sandboxes
- **MULTI-02**: Frontend sandbox picker for switching between instances

## Out of Scope

| Feature | Reason |
|---------|--------|
| Token authentication | Local dev simplicity, `--no-token` flag |
| Multi-workspace | Single workspace sufficient for v1 |
| Custom sandbox-agent builds | Use official npm package |
| Real-time log rendering in panel | Separate log viewer panel exists |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROV-01 | Phase 1 | Pending |
| PROV-02 | Phase 1 | Pending |
| PROV-03 | Phase 1 | Pending |
| PROV-04 | Phase 1 | Pending |
| PROV-05 | Phase 1 | Pending |
| ROUT-01 | Phase 2 | Pending |
| ROUT-02 | Phase 2 | Pending |
| ROUT-03 | Phase 2 | Pending |
| ROUT-04 | Phase 2 | Pending |
| ROUT-05 | Phase 2 | Pending |
| FRNT-01 | Phase 3 | Pending |
| FRNT-02 | Phase 3 | Pending |
| FRNT-03 | Phase 3 | Pending |
| FRNT-04 | Phase 3 | Pending |
| INTG-01 | Phase 4 | Pending |
| INTG-02 | Phase 4 | Pending |
| INTG-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-02-09*
*Last updated: 2026-02-09 after initial definition*
