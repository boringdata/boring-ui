# Reviewer Scope Checklist: bd-1adh Refactor (Contract Freeze Phase)

**Status**: Phase bd-1adh.1.3 - Scope Creep Prevention
**Purpose**: Guide reviewers to reject unnecessary new frameworks, modules, and reinvention during two-module refactor
**Scope**: All PRs implementing bd-1adh (Filesystem-as-Parameter Program)

---

## Executive Summary

The bd-1adh refactor is **architectural restructuring**, not a feature development phase.

**Goal**: Move filesystem location from an architecture fork to a runtime parameter by separating concerns into two explicit modules (`api` + `local-api`).

**Non-Goal**: Add new features, frameworks, or improve existing systems beyond what's necessary for the two-module split.

Reviewers: Use this checklist to **reject** changes that introduce unnecessary scope.

---

## Part 1: Non-Goals (Explicitly OUT of Scope)

### 1.1 New Frameworks and Major Dependencies

❌ **DO NOT ACCEPT** pull requests that:
- Add new web frameworks (e.g., "switch to FastAPI with async improvements")
- Add new validation libraries (e.g., "replace manual validation with Pydantic v3")
- Add new async/concurrency patterns (e.g., "add celery for background jobs")
- Add new authentication systems (e.g., "implement full RBAC or JWT library upgrade")
- Add new storage backends (e.g., "add Redis caching" or "database migrations")

**Rationale**: The existing architecture (FastAPI, manual validation, direct execution, service token auth) is already paid-for infrastructure. Swapping it requires separate justification and test strategy. This refactor doesn't include that payload.

**Exception**: If an existing dependency has a critical security fix or is a hard blocker for the refactor, document it in the PR and get explicit approval from the maintainer.

### 1.2 Multi-Module Expansion

❌ **DO NOT ACCEPT** pull requests that:
- Split control-plane into 3+ sub-modules (e.g., `api/control`, `api/proxy`, `api/routes`)
- Create new service modules (e.g., `modules/auth`, `modules/logging`, `modules/audit`)
- Extract shared utilities into new packages (e.g., `utils/`, `commons/`, `lib/`)
- Build new interfaces that aren't in the plan (e.g., new `Provider` ABC, new `Router` base class)

**Rationale**: The plan is explicit: exactly TWO modules (`api` + `local-api`). Extra modules blur ownership and complicate the hard cut. New abstractions add cognitive load without corresponding benefit during architectural restructuring.

**Exception**: If a new interface is required by the plan (e.g., `TargetResolver`, `WorkspaceTransport`), include it because it's documented. But new abstractions beyond the plan must be rejected.

### 1.3 Refactoring Beyond the Boundaries

❌ **DO NOT ACCEPT** pull requests that:
- Rewrite existing endpoints not touched by the refactor (e.g., "clean up file tree endpoint")
- Refactor test structure beyond what's needed for the new modules
- Rename/reorganize files not involved in the module split
- Add comprehensive logging to unrelated code paths
- Expand error handling philosophy across the codebase

**Rationale**: Every line of code outside the refactor scope is a source of bugs and drift. The refactor is laser-focused: move code to achieve two-module ownership. Unrelated cleanups dilute focus and increase merge conflict risk.

**Exception**: If a code change is a hard prerequisite for correct module operation (e.g., you must fix a path traversal bug in file ops to move to local-api), document it explicitly and scope it narrowly.

### 1.4 Optimization and Performance Work

❌ **DO NOT ACCEPT** pull requests that:
- Optimize query performance (e.g., "cache file tree results")
- Add performance instrumentation beyond what's in the audit/logging plan
- Refactor synchronous code to async without architectural justification
- Add batch operations (e.g., "batch file delete")

**Rationale**: Performance is a separate phase. This refactor focuses on correctness and architectural boundaries. Performance wins may invalidate with different module distribution.

### 1.5 Documentation Beyond the Plan

❌ **DO NOT ACCEPT** pull requests that:
- Add extensive API documentation or OpenAPI specs (deferred, see TWO_MODULE_API_LOCAL_API_PLAN.md section 15.2)
- Create user guides or deployment tutorials (belongs in later phases)
- Add architecture diagrams and sequence diagrams (deferred)
- Write new runbooks (deferred, phase bd-1adh.9)

**Rationale**: Documentation in this phase is minimal: embed reuse references, define non-goals, validate acceptance criteria. Comprehensive docs come in bd-1adh.9 after the refactor is proven.

**Exception**: Docstrings directly in code for the two modules are acceptable. Comments on complex logic (e.g., Sprites proxy transport) are required for maintainability.

---

## Part 2: Acceptable Extensions (IN Scope - if documented in the plan)

### 2.1 Scheduled Framework Extensions

✅ **DO ACCEPT** pull requests that:

#### New Interfaces (if in the plan)
- `TargetResolver` (workspace_id -> WorkspaceTarget)
- `WorkspaceTransport` (unified request/response abstraction for local-api access)
- `ErrorCode` enum (structured error codes for control-plane responses)

#### Config Expansion (if it extends APIConfig safely)
- Add new fields to `APIConfig` (e.g., `sprites_local_api_port`)
- Add new validation rules to `APIConfig.validate_startup()` (must maintain fail-fast semantics)
- Add new env var parsing (must follow existing pattern)

#### Module-Specific Handlers
- New handlers in `local_api/files.py`, `local_api/git.py`, `local_api/exec.py` (workspace-scoped operations)
- New handlers in `api/modules/sandbox/` (proxy and provider logic)
- New test fixtures for transport layer (Sprites proxy, retries, error mapping)

#### Component Reuse (encourage it!)
- Use existing `ServiceTokenIssuer`, `OIDCVerifier`, `AuthMiddleware` as-is (see REUSE_INVENTORY.md)
- Use existing `LoggingMiddleware` and `AuditLogger`
- Use existing `RunMode` and `APIConfig`

**Rationale**: These are documented in TWO_MODULE_API_LOCAL_API_PLAN.md and REUSE_INVENTORY.md. They are necessary for the refactor to function.

### 2.2 Type Safety and Test Coverage (always acceptable)

✅ **DO ACCEPT** pull requests that:
- Add type hints to existing functions (especially in interfaces)
- Add unit tests for new interfaces (TargetResolver, WorkspaceTransport)
- Add integration tests for transport layer (Sprites proxy, retries, timeouts)
- Add contract tests for local-api endpoints
- Improve test coverage without modifying production code

**Rationale**: Type safety and tests are quality multipliers, not scope creep. They reduce bugs and maintenance burden.

### 2.3 Security-Critical Fixes (with justification)

✅ **DO ACCEPT** pull requests that:
- Fix path traversal vulnerabilities in local-api file handlers
- Add workspace isolation validation
- Add auth boundary enforcement (e.g., verify local-api never accepts end-user auth)
- Harden Sprites transport against malformed responses

**Rationale**: Security bugs found during the refactor must be fixed. But the fix must be narrowly scoped to the vulnerability, not used as a pretext to rebuild surrounding code.

---

## Part 3: Review Checklist

### Reviewers: Use this checklist for every PR in bd-1adh

**Before approving, verify:**

#### Scope Alignment
- [ ] PR description clearly states which workstream (WS-A, WS-B, WS-C, WS-D) it implements
- [ ] PR does NOT introduce new frameworks, dependencies, or major abstractions not in the plan
- [ ] PR does NOT split the two modules into 3+ sub-modules
- [ ] PR does NOT refactor code outside the module split boundary
- [ ] PR does NOT add performance optimizations unrelated to the refactor

#### Component Reuse
- [ ] If touching auth, PR imports `ServiceTokenIssuer`, `OIDCVerifier`, `AuthMiddleware` (does NOT rebuild them)
- [ ] If touching config, PR imports/extends `RunMode`, `APIConfig` (does NOT create custom config)
- [ ] If touching logging, PR uses `LoggingMiddleware`, `get_request_id`, `propagate_request_context` (does NOT add custom logging)
- [ ] If touching audit, PR uses `AuditLogger` (does NOT create custom audit system)
- [ ] Cross-check against REUSE_INVENTORY.md: no duplicate implementations

#### Two-Module Ownership
- [ ] Code in `api/` is control-plane only (auth, proxy, provider lifecycle)
- [ ] Code in `local-api/` is workspace-plane only (file/git/exec operations, health checks)
- [ ] No cross-module logic (e.g., local-api does NOT import from api/modules/sandbox/)
- [ ] Shared logic lives in `src/back/boring_ui/api/modules/sandbox/policy.py` (reusable policy, not local-api internal logic)

#### Hard-Cut Compliance
- [ ] PR removes old `internal_app.py` references in same stack (do not create compat layers)
- [ ] PR removes old `internal_api.py` references in same stack
- [ ] PR does NOT create new internal APIs during the refactor (add after hard cut)

#### Error Handling and Observability
- [ ] PR uses existing `RequestIDMiddleware` and structured logging (does NOT add custom logging middleware)
- [ ] PR includes trace_id propagation to local-api (via `propagate_request_context`)
- [ ] PR uses error codes from `error_codes.py` (if new errors, add to that file)
- [ ] PR includes audit logging for sensitive ops (auth, file ops, exec)

#### Testing
- [ ] PR includes tests for new logic (transport layer, local-api handlers, etc.)
- [ ] Tests for local-api handlers verify workspace isolation (path validation)
- [ ] Tests for transport layer cover error cases (timeout, invalid response, retry)
- [ ] No tests added for pre-existing code not modified (don't expand test scope)

#### Documentation
- [ ] PR updates TWO_MODULE_API_LOCAL_API_PLAN.md if new decisions are made (rare!)
- [ ] PR includes docstrings for new functions/classes (especially interfaces)
- [ ] PR includes comments on complex logic (e.g., Sprites proxy handshake)
- [ ] PR does NOT add extensive runbooks or tutorials (defer to bd-1adh.9)

---

## Part 4: Example Scenarios

### Scenario 1: Safe PR - Adding Sprites Transport

**PR description**: "Implement SpritesProxyTransport for Sprites provider"

**Checklist**:
- ✅ Implements `WorkspaceTransport` interface (in plan)
- ✅ Reuses existing `RequestIDMiddleware` for trace IDs
- ✅ Uses existing error codes from `error_codes.py`
- ✅ Includes retry logic with structured error mapping
- ✅ Adds contract tests for handshake, timeout, relay cases
- ✅ No new frameworks or dependencies

**Verdict**: APPROVE

---

### Scenario 2: Unsafe PR - "Clean up file ops with Pydantic"

**PR description**: "Refactor file operation validation to use Pydantic v3 for better error messages"

**Checklist**:
- ❌ Introduces new framework (Pydantic) not in plan
- ❌ Refactors code unrelated to two-module split
- ❌ Adds new dependency without architectural justification
- ❌ Increases test maintenance burden

**Verdict**: REJECT - Out of scope. Manual validation in local-api is acceptable for this phase. Pydantic upgrade can be a separate initiative with its own test strategy.

---

### Scenario 3: Safe PR - Adding local-api handlers

**PR description**: "Move file operation handlers to local-api/files.py with workspace isolation"

**Checklist**:
- ✅ Implements WS-A (local_api extraction)
- ✅ Reuses existing file operation logic from `internal_files.py`
- ✅ Adds path validation via `APIConfig.validate_path()`
- ✅ Adds workspace isolation tests
- ✅ Uses existing logging/audit infrastructure
- ✅ No new abstractions beyond the plan

**Verdict**: APPROVE

---

### Scenario 4: Unsafe PR - "Add local-api caching layer"

**PR description**: "Improve local-api performance by adding in-memory file tree cache"

**Checklist**:
- ❌ Performance optimization not in refactor scope
- ❌ Adds new logic that complicates two-module operation
- ❌ May behave differently in local vs Sprites modes
- ❌ Performance decisions should be made after refactor proves the architecture

**Verdict**: REJECT - Out of scope for this refactor. File tree caching can be added in bd-1adh.9 (Operations Readiness) or later, with full measurement strategy.

---

### Scenario 5: Safe PR - "Add type hints to TargetResolver"

**PR description**: "Improve type safety for TargetResolver interface and implementations"

**Checklist**:
- ✅ Improves code quality without expanding scope
- ✅ Helps catch bugs early
- ✅ No changes to behavior or logic

**Verdict**: APPROVE

---

### Scenario 6: Unsafe PR - "Rewrite git commands with GitPython"

**PR description**: "Replace subprocess git calls with GitPython library for consistency"

**Checklist**:
- ❌ Introduces new dependency (GitPython)
- ❌ Refactors code unrelated to two-module split
- ❌ Changes behavior beyond the scope of moving code
- ❌ Requires separate testing and validation

**Verdict**: REJECT - Out of scope. Git subprocess handling is acceptable for this phase. GitPython migration can be a separate initiative.

---

## Part 5: Escalation Path

If a reviewer encounters a PR that MIGHT be in scope but is ambiguous:

1. **Check the plan**: Does TWO_MODULE_API_LOCAL_API_PLAN.md mention it? If yes, likely in scope.
2. **Check the inventory**: Does REUSE_INVENTORY.md document it? If yes, must reuse, not rebuild.
3. **Ask the author**: "Is this change necessary for the two-module split, or is it independent scope creep?"
4. **If still unclear**: Escalate to the maintainer with:
   - Link to the refactor plan section
   - Explanation of why it seems out of scope
   - Request explicit approval before merging

---

## Part 6: Phase-by-Phase Guidelines

### WS-A (local_api extraction)
- ✅ Acceptable: Move file/git/exec handlers to local_api package
- ✅ Acceptable: Add `router.py`, `app.py` factories
- ❌ Reject: New validation frameworks, new abstractions, performance work

### WS-B (Control-plane rewiring)
- ✅ Acceptable: Introduce `TargetResolver`, `WorkspaceTransport` interfaces
- ✅ Acceptable: Implement `SpritesProxyTransport`, `HTTPInternalTransport`
- ✅ Acceptable: Update imports, remove `internal_app.py`, `internal_api.py`
- ❌ Reject: New auth systems, new logging frameworks, new service modules

### WS-C (Docs and deployment matrix)
- ✅ Acceptable: Update TWO_MODULE_API_LOCAL_API_PLAN.md, add DEPLOYMENT_MATRIX.md
- ✅ Acceptable: Clarify mode behavior, env var matrix, security rules
- ❌ Reject: Comprehensive API docs, user guides, sequence diagrams

### WS-D (Cleanup)
- ✅ Acceptable: Remove stale one-off artifacts
- ✅ Acceptable: Clean up `.gitignore`, temporary scripts
- ❌ Reject: Unrelated code cleanup, file reorganization

---

## Part 7: Success Metrics

After all bd-1adh PRs are merged, success looks like:

1. **Code ownership is clear**: `api/` controls operations, `local-api/` handles workspace operations
2. **No duplication**: Auth, config, logging, audit are all reused from existing modules
3. **Hard cut is complete**: `internal_app.py` and `internal_api.py` are gone
4. **Test coverage**: Transport, local-api, and integration tests pass
5. **No scope creep**: No new frameworks, modules, or abstractions beyond the plan

---

## Appendix: Quick Reject Phrases

Use these when rejecting out-of-scope changes:

- "This is good, but it's architectural cleanup, not part of the two-module split. Let's open a separate issue."
- "This looks like a performance optimization. Save it for bd-1adh.9 (Operations Readiness) after we validate the architecture."
- "Adding a new framework is a separate decision with its own test strategy. Please open an ADR for this."
- "This duplicates existing `ServiceTokenIssuer` / `OIDCVerifier` / `AuditLogger` / etc. See REUSE_INVENTORY.md for how to reuse it."
- "Refactoring unrelated code increases merge conflict risk and dilutes focus. Keep this PR narrowly scoped to the two-module split."
- "Out of scope for this refactor. This is welcome as a follow-up PR after the two-module split is proven."

