# bd-1adh: Non-Goals & Anti-Scope-Creep Review Checklist

**Status**: Ready for implementation gate
**Scope**: bd-1adh.1.3 (Non-goals definition)
**Blocks**: bd-1adh.2+ (All implementation phases)

---

## Overview

This document defines **what bd-1adh is NOT** to prevent scope creep and maintain focus on the core objective: **refactor boring-ui into two modules (api + local-api) with filesystem as a runtime parameter.**

The review checklist helps reviewers reject feature requests, architectural changes, and new dependencies that don't directly support this objective.

---

## Core Objective (For Reference)

> Deliver a fully self-contained implementation and verification workstream with explicit dependencies, rationale, and acceptance gates so future maintainers understand both what changed and why.

**In scope**: Two-module separation, runtime parameter for filesystem, reuse of existing components
**Out of scope**: Major architectural changes, new authentication systems, new frameworks

---

## Non-Goals

### 1. Authentication System Redesign

❌ **OUT OF SCOPE**:
- Replacing OIDC with a custom authentication system
- Building new token issuance mechanisms (JWT alternative)
- Implementing role-based access control (RBAC) beyond existing permission model
- Adding multi-factor authentication (MFA) support
- Building a user directory service (LDAP, OAuth2)

✅ **IN SCOPE**:
- Using existing `ServiceTokenIssuer` for service-to-service auth (no replacement)
- Using existing `OIDCVerifier` for hosted-mode JWT validation (no modification)
- Extending permission types (e.g., adding 'observability:read') within existing `AuthContext` model
- Using existing `require_permission()` decorator for new routes

📋 **Review Checklist**:
- [ ] No new JWT/token libraries introduced?
- [ ] No custom role/permission database proposed?
- [ ] Existing `ServiceTokenIssuer` and `OIDCVerifier` reused as-is?
- [ ] Permission checks use existing `AuthContext.has_permission()` method?

---

### 2. Configuration System Redesign

❌ **OUT OF SCOPE**:
- Replacing environment-variable-based config with file-based config (TOML, YAML)
- Building a secrets management system (Vault, HashiCorp)
- Creating a hierarchical config override system
- Implementing dynamic configuration reloading without restart

✅ **IN SCOPE**:
- Adding new config fields to `APIConfig` (e.g., for Sprites parameters)
- Reading new env vars via `os.environ.get()`
- Extending `APIConfig.validate_startup()` to validate new required fields
- Reusing existing `RunMode` enum for mode selection

📋 **Review Checklist**:
- [ ] Config loading still uses `os.environ.get()` (no new parsing library)?
- [ ] `RunMode` enum unchanged?
- [ ] All config passed through `APIConfig` (no global state)?
- [ ] Startup validation uses `APIConfig.validate_startup()` (no new validation pattern)?

---

### 3. Logging & Observability Overhaul

❌ **OUT OF SCOPE**:
- Replacing Python `logging` module with a new logging library
- Building a centralized log aggregation system
- Implementing trace collection (Jaeger, Datadog)
- Creating operational dashboards
- Building a custom metrics system (replacing Prometheus)

✅ **IN SCOPE**:
- Using existing `RequestIDMiddleware` for request correlation
- Using existing `AuditLogger` and `AuditStore` for audit trails
- Extending `AuditLogger` methods for new event types (e.g., audit_logger.log_observability_event)
- Ensuring structured JSON logs include request_id, user_id, workspace_id

📋 **Review Checklist**:
- [ ] No new logging library introduced?
- [ ] `RequestIDMiddleware` reused for request IDs?
- [ ] `AuditLogger` extended (not replaced)?
- [ ] All logs include structured fields (request_id, etc.)?

---

### 4. Storage Backend Abstraction

❌ **OUT OF SCOPE**:
- Adding support for remote filesystems (S3, GCS, Azure Blob)
- Building a distributed filesystem abstraction
- Implementing file sync/replication logic
- Creating a cache layer for file operations

✅ **IN SCOPE**:
- Supporting local, sandbox, and sprites filesystem sources (via existing `filesystem_source` config)
- Reusing existing `Storage` interface for pluggable backends
- Extending path validation via existing `APIConfig.validate_path()` method

📋 **Review Checklist**:
- [ ] No new storage backends beyond local/sandbox/sprites?
- [ ] `Storage` interface unchanged?
- [ ] `APIConfig.validate_path()` used consistently?

---

### 5. Frontend Architecture Changes

❌ **OUT OF SCOPE**:
- Replacing React with a new framework (Vue, Svelte)
- Building a new state management system (replacing Zustand)
- Redesigning panel system (replacing DockView)
- Building a new component library

✅ **IN SCOPE**:
- Adding new adapters in `src/front/providers/` for new chat services
- Extending `PaneRegistry` to register new panels
- Using existing `useCapabilities` hook to detect mode (LOCAL vs HOSTED)
- Reusing direct-connect pattern for service authentication

📋 **Review Checklist**:
- [ ] React still used (no framework replacement)?
- [ ] Zustand still used for state management?
- [ ] DockView still used for layouts?
- [ ] New services connect via direct-connect pattern (not proxy)?

---

### 6. Dependency Management & Packaging

❌ **OUT OF SCOPE**:
- Replacing pip with a new Python package manager (Poetry, uv)
- Building a monorepo structure (changing project layout significantly)
- Adding C/C++ extension dependencies
- Building Docker containerization

✅ **IN SCOPE**:
- Adding Python packages for existing functionality (e.g., `cryptography` for RSA keys if needed)
- Extending `setup.py` or `pyproject.toml` to include local-api package
- Using existing pip/venv workflow unchanged

📋 **Review Checklist**:
- [ ] No package manager replaced?
- [ ] No new compiled dependencies added?
- [ ] Project structure remains two modules (api + local-api)?
- [ ] pip/venv workflow unchanged?

---

### 7. Runtime & Deployment Topology

❌ **OUT OF SCOPE**:
- Building a Kubernetes operator or Helm charts
- Implementing high-availability clustering
- Building a service mesh (Istio, Linkerd)
- Creating a multi-region deployment strategy

✅ **IN SCOPE**:
- Sprites transport for hosted mode (proxy relay, not clustering)
- Two-module topology (api + local-api on same machine or proxy-connected)
- Using existing subprocess management for services (Companion, sandbox-agent)

📋 **Review Checklist**:
- [ ] No Kubernetes/container orchestration added?
- [ ] No clustering or HA strategy proposed?
- [ ] Topology remains api + local-api (two modules)?
- [ ] Sprites transport follows existing proxy pattern?

---

### 8. Security & Compliance

❌ **OUT OF SCOPE**:
- Building SOC 2 compliance framework
- Implementing data encryption at rest (beyond existing TLS in flight)
- Building penetration testing framework
- Creating formal security assessment process

✅ **IN SCOPE**:
- Using existing `AuthContext` and permission model for access control
- Using existing `AuditLogger` for audit trails
- Path traversal prevention via existing `APIConfig.validate_path()`
- Fail-closed auth semantics (invalid tokens return None, not exceptions)

📋 **Review Checklist**:
- [ ] No new compliance framework added?
- [ ] Existing auth model used for access control?
- [ ] `AuditLogger` used for audit trails?
- [ ] Path validation prevents traversal attacks?

---

### 9. Testing Strategy & Quality Gates

❌ **OUT OF SCOPE**:
- Building a code coverage enforcement system
- Implementing performance benchmarking framework
- Creating a formal QA process
- Building integration testing infrastructure

✅ **IN SCOPE**:
- Unit tests for components (existing pattern)
- Integration tests for api ↔ local-api interactions
- E2E tests for LOCAL and HOSTED modes
- Reusing existing test utilities and patterns

📋 **Review Checklist**:
- [ ] Tests use existing pytest/unittest patterns?
- [ ] No new testing framework added?
- [ ] Integration tests added (not just unit tests)?
- [ ] E2E tests cover LOCAL and HOSTED modes?

---

### 10. Documentation & Knowledge Base

❌ **OUT OF SCOPE**:
- Building a wiki or knowledge management system
- Creating video tutorials
- Generating automatic API documentation
- Building a developer portal

✅ **IN SCOPE**:
- Updating README.md with two-module architecture
- ADRs (Architecture Decision Records) in `.planning/` for major decisions
- Inline code comments for non-obvious logic
- Commit messages that explain "why" changes

📋 **Review Checklist**:
- [ ] No new documentation system added?
- [ ] README updated with new architecture?
- [ ] ADRs written for major decisions?
- [ ] Commit messages explain rationale?

---

## Anti-Scope-Creep Review Checklist

**Use this checklist when reviewing PRs or design proposals for bd-1adh phases:**

### For Every PR/Design Proposal:

- [ ] **Purpose is clear**: PR/proposal directly supports two-module refactor or reuse-enforcement?
- [ ] **Scope is bounded**: Changes are scoped to specific phase (bd-1adh.2, bd-1adh.3, etc.)?
- [ ] **No new frameworks**: No new libraries or frameworks introduced unnecessarily?
- [ ] **Existing components reused**: All auth, config, audit, logging uses existing components?
- [ ] **No duplicated code**: No reimplementation of existing functionality?
- [ ] **Path validation used**: File operations call `config.validate_path()`?
- [ ] **Request IDs propagated**: Logging includes `request_id` from middleware?
- [ ] **Audit events logged**: Sensitive operations logged via `audit_logger`?
- [ ] **Error semantics correct**: Auth returns 401 (invalid) or 403 (insufficient), not 500?

### Questions to Ask on PR Review:

1. **Why is this needed?**
   - Should have explicit link to bd-1adh phase or REUSE_INVENTORY component

2. **Could we reuse existing code?**
   - Check REUSE_INVENTORY and EXECUTION_CHECKLIST
   - If similar component exists, why not use it?

3. **Is this a new framework/dependency?**
   - Red flag: new library that provides similar functionality to existing code
   - Example: ❌ "Let's use pydantic for config" (but APIConfig exists)
   - Example: ✅ "Let's extend APIConfig with new fields"

4. **Does this change the two-module boundary?**
   - Should not move responsibilities between modules
   - Both modules should have parallel implementations (e.g., file router in both)

5. **Is this testable?**
   - Can we test this in isolation (unit test)?
   - Can we test api ↔ local-api interaction (integration test)?

### Red Flags 🚩

- [ ] PR introduces a new authentication library
- [ ] PR creates a new config/settings system
- [ ] PR proposes a new logging or tracing system
- [ ] PR adds a new ORM or database layer
- [ ] PR introduces a new web framework or routing system
- [ ] PR proposes microservices or additional modules beyond api + local-api
- [ ] PR doesn't include tests or audit logging
- [ ] PR doesn't propagate request_id for correlation
- [ ] PR bypasses `APIConfig.validate_path()` for file operations
- [ ] PR returns 500 instead of 401/403 for auth errors

### Green Flags ✅

- [ ] PR extends existing component (e.g., adds new permission type)
- [ ] PR reuses pattern from EXECUTION_CHECKLIST
- [ ] PR includes unit + integration tests
- [ ] PR includes audit logging for sensitive operations
- [ ] PR propagates request_id in all logs
- [ ] PR validates all paths via `config.validate_path()`
- [ ] PR clear on which phase it supports (bd-1adh.2, etc.)
- [ ] Commit messages explain "why" not just "what"

---

## Examples

### ❌ BAD: Prohibited Changes

**Example 1: Custom service token system**
```python
# ❌ REJECT: Reimplementation
class CustomServiceToken:
    def issue_token(self): ...

# ✅ ACCEPT: Use existing
from boring_ui.api.auth import ServiceTokenIssuer
```

**Example 2: New config system**
```python
# ❌ REJECT: New framework
config = load_yaml_config('app.yaml')

# ✅ ACCEPT: Extend existing
config = APIConfig(workspace_root=Path(...))
config.new_field = os.environ.get('NEW_PARAM')
```

**Example 3: Bypassing auth**
```python
# ❌ REJECT: Direct file access without validation
def read_file(path):
    with open(path) as f:
        return f.read()

# ✅ ACCEPT: Use validated path
def read_file(path, config):
    validated = config.validate_path(path)
    with open(validated) as f:
        return f.read()
```

**Example 4: Error semantics**
```python
# ❌ REJECT: Wrong status code for auth
if not authenticated:
    raise HTTPException(status_code=500, detail="Access denied")

# ✅ ACCEPT: Correct semantics
if not authenticated:
    return error_emitter.invalid_token(path, request_id=request_id)  # 401
```

### ✅ GOOD: Allowed Extensions

**Example 1: New permission type**
```python
# ✅ ACCEPT: Extend permission model
@require_permission('observability:read')
async def get_metrics(request: Request):
    ...
```

**Example 2: New audit event type**
```python
# ✅ ACCEPT: Extend AuditLogger
audit_logger.log_custom_event(
    event_type='OBSERVABILITY_QUERY',
    user_id=user_id,
    request_id=request_id
)
```

**Example 3: New API route using existing patterns**
```python
# ✅ ACCEPT: Use existing router factory pattern
@router.get('/api/custom')
@require_permission('custom:read')
async def custom_route(request: Request):
    auth_context = get_auth_context(request)
    request_id = get_request_id(request)
    audit_logger.log_operation(...)
    # ...
```

---

## Escalation Path

**If a reviewer is unsure whether something is in-scope:**

1. Check EXECUTION_CHECKLIST — Is this phase in the checklist?
2. Check REUSE_INVENTORY — Does a similar component exist?
3. Check this document — Is this explicitly non-goal or allowed extension?
4. If still unsure: **Escalate to bd-1adh epic owner** for clarification

**Do NOT** assume new features, dependencies, or architectural changes are in-scope without explicit approval.

---

## Summary

**bd-1adh focuses on**:
- ✅ Two-module separation (api + local-api)
- ✅ Reusing existing auth, config, audit, logging components
- ✅ Runtime parameter for filesystem source
- ✅ Clear phase dependencies and execution checklist
- ✅ Integration between modules

**bd-1adh explicitly avoids**:
- ❌ Authentication system redesign
- ❌ Configuration system redesign
- ❌ Logging & observability overhaul
- ❌ Storage backend changes
- ❌ Frontend framework changes
- ❌ Dependency/packaging restructure
- ❌ Deployment topology changes
- ❌ Compliance framework building
- ❌ Testing infrastructure overhaul
- ❌ Documentation system creation

---

## Related Documents

- `.planning/bd-1adh/EXECUTION_CHECKLIST.md` — What to do (detailed phases)
- `.planning/bd-1adh/REUSE_INVENTORY.md` — What components to reuse
- `bd-1adh` epic description — Core objective

---

## Approval

- [ ] Code Owners reviewed and approved this checklist
- [ ] Team consensus on non-goals
- [ ] Ready for phase implementation (bd-1adh.2+)
