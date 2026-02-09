# Phase 4: Integration Testing - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end verification of sandbox lifecycle and configuration. Validate that the drop-in replacement works correctly.

</domain>

<decisions>
## Implementation Decisions

### Design principle
- **Follow existing test patterns** in the codebase
- Match test structure and conventions already established

### Test scope
- Both automated and manual verification
- Automated: pytest for backend, existing frontend test patterns
- Manual: Verification checklist for UAT

### Mock vs real
- Mock sandbox-agent for CI (fast, reliable)
- Real binary for local development testing
- Flag or env var to switch modes

### What to verify
- Sandbox starts on app startup (eager start)
- Proxy routes work (health, chat endpoints)
- Log capture and retrieval works
- Crash recovery with auto-restart
- Graceful shutdown
- Frontend panel loads and connects
- Chat interaction works end-to-end

### CI integration
- Add to CI pipeline (match existing CI patterns)
- Mock mode for CI runs

### Claude's Discretion
- Specific test file organization
- Mock implementation details
- Which edge cases to cover in automated tests

</decisions>

<specifics>
## Specific Ideas

- Use existing test fixtures and patterns
- Verification checklist from ROADMAP.md as manual test guide
- Integration tests should run fast with mocks

</specifics>

<deferred>
## Deferred Ideas

- Performance/load testing — future
- Multi-sandbox testing — future (when multi-sandbox supported)

</deferred>

---

*Phase: 04-integration-testing*
*Context gathered: 2026-02-09*
