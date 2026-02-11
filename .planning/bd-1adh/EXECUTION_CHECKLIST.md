# bd-1adh Execution Checklist: Two-Module Refactor

**Status**: Ready for execution
**Blocks**: bd-1adh.2 (Module extraction), bd-1adh.3 (Runtime matrix)
**Depends On**: bd-1adh.1.1 (Component inventory), bd-1adh.1.2 (This checklist)

---

## Phase 1: Configuration & Startup (bd-1adh.3)

### Configuration Module Loading and Validation

- [ ] **Reuse**: `boring_ui.api.config:RunMode`
  - **Purpose**: Distinguish LOCAL vs HOSTED execution modes
  - **Usage**: Both api and local-api factories must call `RunMode.from_env()`
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 2 (RunMode + APIConfig)`
  - **Acceptance**: Mode selection is centralized, no duplicates

- [ ] **Reuse**: `boring_ui.api.config:APIConfig`
  - **Purpose**: Central configuration for all routers (dependency injection pattern)
  - **Usage**: Pass `config` to ALL router factories: `create_files_router(config)`, `create_git_router(config)`, etc.
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 2`
  - **Acceptance**: All routers receive config, no global state

- [ ] **Reuse**: `APIConfig.validate_path(path)`
  - **Purpose**: CRITICAL security control — prevent path traversal attacks
  - **Usage**: All file operations must call this BEFORE accessing filesystem
  - **Scope**: Both api and local-api file routers must use this
  - **Reference**: config.py:114-139
  - **Acceptance**: Zero path traversal vulnerabilities, consistent path validation

- [ ] **Reuse**: `APIConfig.validate_startup()`
  - **Purpose**: Enforce required environment variables per mode
  - **Usage**: Call in both app factories before mounting routers
  - **Reference**: config.py:164-192
  - **Acceptance**: Startup fails fast with actionable error messages if config invalid

### Startup Validation Rules

- [ ] **LOCAL mode required**: WORKSPACE_ROOT
  - **Implementation**: `APIConfig.validate_startup()` for LOCAL
  - **Reference**: config.py:159-160

- [ ] **HOSTED mode required**: WORKSPACE_ROOT, OIDC_ISSUER, OIDC_AUDIENCE (or DEV_AUTH_BYPASS=1)
  - **Implementation**: `APIConfig.validate_startup()` for HOSTED
  - **Reference**: config.py:147-155

- [ ] **No duplicate validation** in local-api
  - **Check**: Ensure local-api reuses the same `config.validate_startup()` call
  - **Reference**: REUSE_INVENTORY.md § Anti-Patterns

---

## Phase 2: Service-to-Service Authentication (bd-1pwb.3, bd-1adh integration)

### Service Token Issuance

- [ ] **Reuse**: `boring_ui.api.auth:ServiceTokenIssuer`
  - **Purpose**: JWT and bearer token issuance for direct service connections
  - **Token Types**:
    - JWT (HS256): For services that validate claims (Companion/Hono)
    - Bearer: Plain tokens for services with built-in auth (sandbox-agent)
    - Query param: Short-lived tokens (120s) for SSE/WS query params
  - **Usage**: Instantiate once per app (one issuer per process)
    ```python
    issuer = ServiceTokenIssuer()
    signing_key_env = issuer.signing_key_hex  # Pass to subprocesses
    ```
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 1`
  - **Acceptance**: Token issuance is consistent across api and local-api

- [ ] **Implement in API factory**: `create_app()`
  - **Code**: Instantiate `ServiceTokenIssuer` early, pass to service manager factories
  - **Usage**: `issuer.issue_token(service='sandbox', ttl_seconds=3600)`
  - **Reference**: auth.py:30-105

- [ ] **Implement in local-api factory**: If local-api manages its own service lifecycle
  - **Decision**: Does local-api spawn subservices? If yes, reuse `ServiceTokenIssuer`
  - **Status**: TBD (depends on local-api design from bd-1adh.2)

### Token Verification

- [ ] **Reuse**: `ServiceTokenIssuer.verify_token()`
  - **Purpose**: Verify JWT tokens issued by ServiceTokenIssuer
  - **Usage**: Both api and local-api services must validate tokens using the same logic
  - **Fail-Closed**: Returns None if key is missing (no exceptions)
  - **Reference**: auth.py:80-105
  - **Acceptance**: Token verification is consistent, no bypass paths

---

## Phase 3: OIDC Authentication (bd-1pwb.2 integration, HOSTED mode only)

### OIDC Provider Configuration

- [ ] **Reuse**: `boring_ui.api.auth:OIDCVerifier`
  - **Purpose**: Validate JWTs from external OIDC providers (Auth0, Cognito, etc.)
  - **Configuration** (env vars):
    - `OIDC_ISSUER`: IdP issuer URL
    - `OIDC_AUDIENCE`: Expected audience claim
    - `OIDC_CACHE_TTL_SECONDS`: JWKS cache lifetime (default 3600s)
  - **Features**:
    - Fetches and caches JWKS (.well-known/jwks.json)
    - Validates token signature (RS256), issuer, audience, expiry
    - Automatic key rotation (cache invalidation + retry on signature mismatch)
    - Observable cache stats for monitoring
  - **Usage**: Create via factory method in hosted-only setup
    ```python
    verifier = OIDCVerifier.from_env()  # Returns None if not configured
    ```
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 3`
  - **Acceptance**: OIDC verification is centralized, no duplicates, key rotation works

- [ ] **Implement in API factory** (HOSTED mode only)
  - **Code**: Call `OIDCVerifier.from_env()` and pass to middleware
  - **Mode Guard**: Only if `config.run_mode == RunMode.HOSTED`
  - **Reference**: auth.py:108-319

- [ ] **DO NOT implement in local-api**
  - **Reason**: local-api operates in sandbox context, no external IdP auth needed
  - **Note**: Use internal capability tokens instead (bd-1pwb.3)

---

## Phase 4: Request Correlation & Logging (bd-1pwb.9.1 integration)

### Request ID Middleware

- [ ] **Reuse**: `boring_ui.api.logging_middleware:RequestIDMiddleware`
  - **Purpose**: Generate and propagate unique request IDs for end-to-end tracing
  - **Behavior**:
    - Generates UUID for each request or inherits from X-Request-ID header
    - Attaches to `request.state.request_id`
    - Includes in response headers (X-Request-ID, X-Process-Time)
  - **Usage**: Add early in middleware stack
    ```python
    from boring_ui.api.logging_middleware import add_logging_middleware
    add_logging_middleware(app)
    ```
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 5`
  - **Acceptance**: Request IDs are globally unique, propagated across services

- [ ] **Implement in API factory**
  - **Code**: Call `add_logging_middleware(app)` before other middlewares
  - **Order**: Must be FIRST middleware for accurate request IDs
  - **Reference**: logging_middleware.py:78-113

- [ ] **Implement in local-api factory**
  - **Code**: Same `add_logging_middleware(app)` call
  - **Benefit**: Enables trace correlation between api and local-api

### Structured Logging

- [ ] **Reuse**: `boring_ui.api.logging_middleware` — JSON formatter
  - **Purpose**: Machine-readable JSON logs with correlation fields
  - **Fields**: timestamp, level, logger, message, request_id, user_id, method, path, status, latency_ms
  - **Usage**: Automatic via middleware setup
  - **Reference**: logging_middleware.py:20-75
  - **Acceptance**: All logs are JSON-formatted, parseable by aggregation systems

- [ ] **Helper functions available**:
  - `get_request_id(request)` — Extract request_id from request state
  - `propagate_request_context(request, headers)` — Build headers for outbound requests
  - **Reference**: REUSE_INVENTORY.md § 5

---

## Phase 5: Authentication Middleware (bd-1pwb.2 integration, HOSTED mode)

### JWT Validation & Auth Context Injection

- [ ] **Reuse**: `boring_ui.api.auth_middleware:add_oidc_auth_middleware`
  - **Purpose**: FastAPI middleware for JWT validation and auth context injection
  - **Behavior**:
    - Extracts Bearer token from Authorization header
    - Validates JWT using OIDCVerifier
    - Injects AuthContext into `request.state.auth_context`
    - Returns 401 for invalid/missing credentials
    - Allows public routes (/health, OPTIONS preflight) without auth
  - **Usage**: Add after logging middleware
    ```python
    from boring_ui.api.auth_middleware import add_oidc_auth_middleware
    verifier = OIDCVerifier.from_env()
    add_oidc_auth_middleware(app, verifier)
    ```
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 4`
  - **Acceptance**: All protected routes enforce authentication consistently

- [ ] **Implement in API factory** (HOSTED mode only)
  - **Code**: Add middleware after logging, before routers
  - **Mode Guard**: Only if `config.run_mode == RunMode.HOSTED`
  - **Reference**: auth_middleware.py:81-209

- [ ] **Implement in local-api factory**
  - **Decision**: Does local-api also use OIDC? Or internal capability tokens?
  - **Note**: TBD based on hosted control-plane/data-plane design (bd-1adh.5)

### AuthContext Dataclass

- [ ] **Reuse**: `boring_ui.api.auth_middleware:AuthContext`
  - **Purpose**: Represents authenticated user with permissions and workspace context
  - **Fields**:
    - `user_id`: Subject from JWT 'sub' claim
    - `workspace_id`: From JWT 'workspace' claim or default
    - `permissions`: Set of permission strings (e.g., 'files:read', 'git:*', 'exec:*')
    - `claims`: Full JWT payload
  - **Method**: `has_permission(permission)` — supports wildcards ('git:*', '*')
  - **Usage**: Available in request.state.auth_context
    ```python
    auth_context = get_auth_context(request)
    if auth_context.has_permission('files:read'):
        # Allow operation
    ```
  - **Reference**: auth_middleware.py:29-78
  - **Acceptance**: Permission checks are consistent, wildcard matching works

### Permission Enforcement

- [ ] **Reuse**: `require_permission(permission)` decorator
  - **Purpose**: Route-level permission checks
  - **Usage**:
    ```python
    @app.get('/api/files')
    @require_permission('files:read')
    async def list_files(request: Request):
        # Only executes if user has 'files:read' permission
    ```
  - **Reference**: auth_middleware.py:235-269
  - **Acceptance**: Route permissions are declarative, no manual checks needed

- [ ] **Implement in API routes** (HOSTED mode)
  - **Scope**: File operations, git operations, exec operations
  - **Permissions**: 'files:read', 'files:write', 'git:*', 'exec:exec'
  - **Reference**: REUSE_INVENTORY.md § 4

- [ ] **Implement in local-api routes**
  - **Decision**: Internal capability tokens or OIDC? TBD
  - **Status**: Depends on bd-1adh.5 design

---

## Phase 6: Audit & Compliance (bd-1pwb.9.2 integration)

### Audit Event Logging

- [ ] **Reuse**: `boring_ui.api.audit:AuditLogger`
  - **Purpose**: Centralized audit logging for security and compliance
  - **Event Types**: AUTH_SUCCESS, AUTH_FAILURE, FILE_READ, FILE_WRITE, EXEC_RUN, etc.
  - **Storage**: Persistent JSONL audit trail by default (FileAuditStore)
  - **Usage**: Global instance `audit_logger`
    ```python
    from boring_ui.api.audit import audit_logger
    from boring_ui.api.logging_middleware import get_request_id

    audit_logger.log_auth_success(
        user_id='user123',
        workspace_id='workspace-abc',
        request_id=get_request_id(request)
    )
    ```
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md § 6`
  - **Acceptance**: All sensitive operations are audited, trail is immutable

- [ ] **Implement in API routes**
  - **Events to log**:
    - Auth success/failure (in middleware)
    - File operations (read, write, delete)
    - Git operations (status, diff, show)
    - Exec operations (pty sessions, commands)
  - **Correlation**: Use `get_request_id(request)` in all audit calls
  - **Reference**: audit.py:25-150+

- [ ] **Implement in local-api routes**
  - **Reuse**: Same `audit_logger` instance
  - **Benefit**: Unified audit trail across both modules
  - **Note**: Ensure request_id propagation between api ↔ local-api

### Audit Storage

- [ ] **Reuse**: `boring_ui.api.audit_persistence:AuditStore` interface
  - **Purpose**: Abstract interface for audit event persistence
  - **Implementations**:
    - **FileAuditStore**: JSONL file at `.audit/events.jsonl` (production default)
    - **InMemoryAuditStore**: For testing/development
  - **Usage**: Configurable via factory
    ```python
    from boring_ui.api.audit_persistence import create_audit_store
    store = create_audit_store(store_type='file')
    audit_logger = AuditLogger(store=store)
    ```
  - **Reference**: audit_persistence.py
  - **Acceptance**: Audit events are persisted, queryable for compliance

- [ ] **NO custom audit storage**
  - **Check**: Ensure local-api uses same AuditStore
  - **Reference**: REUSE_INVENTORY.md § Anti-Patterns

---

## Phase 7: Route Patterns & Path Validation

### File Operations

- [ ] **Reuse**: `create_file_router(config: APIConfig, storage: Storage) -> APIRouter`
  - **Purpose**: File CRUD operations (read, write, delete, rename, move)
  - **Path Validation**: All routes use `config.validate_path()` helper
  - **Pattern**: Store abstraction allows pluggable backends (local, sandbox, sprites)
  - **Reference**: `.planning/bd-1adh/REUSE_INVENTORY.md (file patterns)`
  - **Acceptance**: No path traversal vulnerabilities, consistent path handling

- [ ] **Implement in API routes**
  - **Endpoints**: /api/tree, /api/file (GET/PUT/DELETE), /api/file/rename, /api/file/move
  - **Reference**: file_routes.py:28-80+

- [ ] **Implement in local-api routes**
  - **Copy pattern**: Use same `create_file_router()` factory
  - **Storage backend**: Pass local storage implementation to router

### Git Operations

- [ ] **Reuse**: `create_git_router(config: APIConfig) -> APIRouter`
  - **Purpose**: Git status, diff, show operations
  - **Pattern**: Subprocess execution with path validation, timeout (30s)
  - **Reference**: git_routes.py:8-90+

- [ ] **Implement in API routes**
  - **Endpoints**: /api/git/status, /api/git/diff, /api/git/show
  - **Reference**: git_routes.py

- [ ] **Implement in local-api routes**
  - **Copy pattern**: Use same `create_git_router()` factory
  - **Validation**: All git operations in same workspace context

---

## Phase 8: Error Handling & Error Semantics

### Authentication Error Contract

- [ ] **Reuse**: `boring_ui.api.auth_errors:AuthErrorEmitter`
  - **Purpose**: Standardize error responses for auth failures (401 vs 403)
  - **Error Types**:
    - 401 Unauthorized: Missing/invalid JWT token
    - 403 Forbidden: Valid token but insufficient permissions
  - **Error Contract**: `{code, message, request_id}` for machine-readable handling
  - **Usage**:
    ```python
    emitter = AuthErrorEmitter()
    return emitter.missing_token(request.url.path, request_id=request_id)
    return emitter.insufficient_permission(path, user_id, permission, perms, request_id)
    ```
  - **Reference**: auth_errors.py
  - **Acceptance**: Error semantics are consistent, frontend can distinguish authn vs authz failures

- [ ] **NO custom error responses for auth**
  - **Check**: Both api and local-api use same AuthErrorEmitter
  - **Reference**: REUSE_INVENTORY.md § Anti-Patterns

---

## Phase 9: Integration & Testing

### Cross-Module Integration

- [ ] **Verify config flow**
  - **Test**: Both api and local-api factories receive same APIConfig
  - **Test**: RunMode is correctly determined in both
  - **Test**: Path validation works consistently in both

- [ ] **Verify auth flow**
  - **Test**: ServiceTokenIssuer tokens validated consistently
  - **Test**: OIDCVerifier (if hosted) validates same tokens
  - **Test**: AuthContext permissions enforced in both modules

- [ ] **Verify logging & audit flow**
  - **Test**: Request IDs propagate from api → local-api (if applicable)
  - **Test**: Audit events logged consistently in both modules
  - **Test**: Audit trail is unified (single JSONL file)

### Test Coverage

- [ ] **Unit tests**: Components are tested individually
  - Reference: `src/back/boring_ui/api/test_*.py`

- [ ] **Integration tests**: Two modules work together
  - NEW: Add tests for api ↔ local-api interactions

- [ ] **E2E tests**: Full request flow from browser to storage
  - NEW: Verify LOCAL and HOSTED modes separately

---

## Phase 10: Non-Goals & Anti-Scope-Creep Checklist

- [ ] **DO NOT**:
  - [ ] Create new ServiceTokenIssuer-like class (reuse existing)
  - [ ] Create custom RunMode/APIConfig (reuse existing)
  - [ ] Implement custom OIDC verification (reuse OIDCVerifier)
  - [ ] Bypass auth_middleware (extend permissions instead)
  - [ ] Add custom logging to bypass logging_middleware
  - [ ] Rebuild audit trail (extend AuditLogger methods if needed)
  - [ ] Implement custom path validation (reuse `config.validate_path()`)

- [ ] **Reference**: REUSE_INVENTORY.md § Anti-Patterns

---

## Acceptance Criteria

- [x] **Component inventory completed** (bd-1adh.1.1)
- [x] **All components referenced with full module paths** (this checklist)
- [x] **Every major concern has a designated module or pattern**
- [x] **Anti-scope-creep checklist in place**
- [ ] **Next: bd-1adh.1.3 (Non-goals review)**
- [ ] **Next: bd-1adh.2 (Module extraction)**

---

## Related Documents

- `.planning/bd-1adh/REUSE_INVENTORY.md` — Component inventory with detailed documentation
- `.planning/DIRECT_CONNECT_ARCHITECTURE.md` — Service communication patterns
- `src/back/boring_ui/api/` — Implementation files
- `bd-1pwb.2` — Hosted Auth Middleware Stack (uses components from this checklist)
- `bd-1pwb.9` — Observability, Audit, and Operations (uses audit components)

---

## Beads Dependency Chain

```
bd-1adh.1.1 (Inventory)
    ↓
bd-1adh.1.2 (This checklist)
    ↓
bd-1adh.1.3 (Non-goals)
    ↓
bd-1adh.2 (Module extraction)
    ↓
bd-1adh.3 (Runtime matrix)
    ↓
bd-1adh.4 (Sprites proxy)
    ↓
bd-1adh.5 (Security boundaries)
    ↓
bd-1adh.6 (Auth middleware in local-api)
    ↓
bd-1adh.7 (Local mode strategy)
    ↓
bd-1adh.8 (Verification program)
    ↓
bd-1adh.9 (Docs & rollout)
```
