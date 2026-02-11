# Component Reuse Inventory (bd-1adh.1.1)

**Status**: Ready for embedded references in architecture plan
**Scope**: bd-1adh (Filesystem-as-Parameter Program: Two-Module API/Local-API Refactor)
**Blocks**: bd-1adh.1.2, bd-1adh.2, bd-1adh.3 (Architecture plan execution checklist)

---

## Overview

This document catalogs existing components that **MUST be reused** (not rebuilt) during the two-module refactor (bd-1adh.2). Each entry includes:
- **Module path**: Where the component lives
- **Responsibility**: What it does (concise)
- **Integration point**: How to use it
- **Reuse constraint**: What must NOT change

---

## 1. Service Token Issuance (ServiceTokenIssuer)

**Module**: `src/back/boring_ui/api/auth.py:ServiceTokenIssuer`

**Responsibility**:
- Issues JWT tokens (HS256) for direct service authentication
- Generates plain bearer tokens for services with built-in auth (e.g., sandbox-agent)
- Each app startup generates a new 256-bit signing key (in-memory)
- Token types:
  - **JWT**: For services that validate JWT claims (Companion, Hono) — 1hr TTL default
  - **Query param tokens**: Short-lived (120s) for SSE/WS query params (log-leak mitigation)
  - **Bearer**: Plain random strings for services with `--token` CLI flag (no expiry until restart)

**Integration Point**:
- Location: `boring_ui.api.auth:ServiceTokenIssuer` (import as-is)
- Usage: Instantiate once at app startup: `issuer = ServiceTokenIssuer()`
- Key access: `issuer.signing_key_hex` (pass to subprocesses via env var)
- Token methods:
  - `issuer.issue_token(service: str, ttl_seconds: int)` → JWT string
  - `issuer.issue_query_param_token(service: str)` → Short-lived JWT
  - `issuer.generate_service_token()` → Plain bearer token
- Verification: `ServiceTokenIssuer.verify_token(token, signing_key_hex, expected_service)` (static)

**Reuse Constraint**:
- ✅ **MUST be reused**: Direct import and instantiation in both public (api) and private (local-api) app factories
- ❌ **DO NOT modify**: JWT algorithm (HS256), key generation (os.urandom(32)), token structure
- ❌ **DO NOT rebuild**: Any custom service token system
- **Justification**: Service auth is orthogonal to API layering; reuse ensures consistent token validation across modules

**Test Coverage**:
- `src/back/boring_ui/api/test_service_auth.py` — JWT issuance, verification, and bearer token generation

---

## 2. Configuration (RunMode + APIConfig)

**Module**: `src/back/boring_ui/api/config.py`

**Responsibility**:

### RunMode (Enum)
- Execution mode for boring-ui: LOCAL or HOSTED
- Determines which routers/features are available
- Loaded from `BORING_UI_RUN_MODE` env var (case-insensitive, defaults to LOCAL)
- Used for startup validation and mode-specific logic branching

### APIConfig (Dataclass)
- Central configuration object passed to all router factories
- Avoids global state and enables dependency injection
- Validates required env vars based on run mode at startup
- Manages:
  - **workspace_root**: Workspace filesystem root (validates path traversal)
  - **run_mode**: LOCAL or HOSTED
  - **cors_origins**: CORS allow-list (default: dev origins)
  - **filesystem_source**: 'local', 'sandbox', or 'sprites' (determines FileTree source)
  - **pty_providers**: Shell command config (e.g., bash, claude)
  - **oidc_***: OIDC config for hosted JWT verification

**Integration Point**:
- Location: `boring_ui.api.config:RunMode`, `APIConfig`
- Usage pattern:
  ```python
  from boring_ui.api.config import RunMode, APIConfig

  # Get run mode
  mode = RunMode.from_env()

  # Create config
  config = APIConfig(
      workspace_root=Path(os.environ['WORKSPACE_ROOT']),
      run_mode=mode,
  )

  # Validate at app startup (raise ValueError if invalid)
  config.validate_startup()

  # Pass config to all router factories
  files_router = create_files_router(config)
  ```
- Path validation: `config.validate_path(path)` — used by file ops to prevent traversal
- Mode checks: `if config.run_mode == RunMode.HOSTED: ...`

**Reuse Constraint**:
- ✅ **MUST be reused**: Direct import; pass config to all router factories
- ✅ **MUST be extended** (if needed): Add new config fields for new routers, but preserve existing fields
- ❌ **DO NOT modify**: Config loading from env vars (uses os.environ.get directly for testability)
- ❌ **DO NOT rebuild**: Mode validation logic or startup checks
- **Justification**: Config is the single source of truth for mode selection and validation; consistency across modules depends on it

**Test Coverage**:
- Config loading and validation logic in existing unit tests

---

## 3. OIDC JWT Verification (OIDCVerifier)

**Module**: `src/back/boring_ui/api/auth.py:OIDCVerifier`

**Responsibility**:
- Validates JWTs from external OIDC identity providers (Auth0, Cognito, custom IdP)
- Fetches and caches JWKS (.well-known/jwks.json) with TTL (default 3600s)
- Validates: token signature (RS256), issuer claim, audience claim, expiry
- Handles key rotation transparently (cache invalidation + retry on signature mismatch)
- Observable: cache hit/miss statistics for monitoring

**Integration Point**:
- Location: `boring_ui.api.auth:OIDCVerifier`
- Setup (typically in hosted mode):
  ```python
  from boring_ui.api.auth import OIDCVerifier

  # Factory method (from env vars)
  verifier = OIDCVerifier.from_env(
      issuer_env='OIDC_ISSUER',
      audience_env='OIDC_AUDIENCE'
  )
  # Returns None if not configured

  # Or direct instantiation
  verifier = OIDCVerifier(
      issuer_url='https://auth.example.com',
      audience='my-app',
      cache_ttl_seconds=3600
  )
  ```
- Token validation:
  ```python
  claims = verifier.verify_token(jwt_string)
  if claims is None:
      # Token invalid
  ```
- Monitoring:
  ```python
  stats = verifier.cache_stats  # {'hits': N, 'misses': M, 'total': N+M}
  ```

**Reuse Constraint**:
- ✅ **MUST be reused**: Import directly for hosted mode auth middleware
- ❌ **DO NOT modify**: RS256 algorithm validation, JWKS caching logic, key rotation handling
- ❌ **DO NOT rebuild**: Any custom OIDC implementation
- **Justification**: OIDC verification is critical for hosted mode security; reuse prevents auth bypass bugs

**Test Coverage**:
- Token validation, cache behavior, key rotation logic in existing unit tests

---

## 4. Authentication Middleware (auth_middleware.py)

**Module**: `src/back/boring_ui/api/auth_middleware.py`

**Responsibility**:
- FastAPI middleware stack for JWT validation and auth context injection
- Extracts Bearer token from Authorization header
- Validates JWT using OIDCVerifier (if provided)
- Injects AuthContext into request.state (user_id, workspace_id, permissions, claims)
- Enforces error semantics: 401 (invalid token), 403 (insufficient permission)
- Permission checking with wildcard support (git:*, files:*, *)

**Key Components**:

### AuthContext (Dataclass)
- User identity: user_id (from JWT 'sub' claim)
- Workspace: workspace_id (from JWT 'workspace' claim or default)
- Permissions: set of permission strings (e.g., files:read, git:*, exec:exec)
- Method: `has_permission(permission)` — checks with wildcard matching

### Middleware Function
- `add_oidc_auth_middleware(app: FastAPI, verifier: OIDCVerifier | None)`
- Skipped if verifier is None (only activates in hosted mode)
- Public routes: /health, OPTIONS (preflight)

### Helper Functions
- `get_auth_context(request)` → AuthContext or raise 401
- `require_permission(permission)` → Decorator for route-level permission checks

**Integration Point**:
- Location: `boring_ui.api.auth_middleware`
- Usage in app factory:
  ```python
  from boring_ui.api.auth_middleware import (
      add_oidc_auth_middleware,
      get_auth_context,
      require_permission,
  )
  from boring_ui.api.auth import OIDCVerifier

  # Add middleware (typically in hosted mode)
  verifier = OIDCVerifier.from_env()
  add_oidc_auth_middleware(app, verifier)

  # Use in routes
  @app.get('/api/protected')
  @require_permission('files:read')
  async def protected_route(request: Request):
      auth_context = get_auth_context(request)
      user_id = auth_context.user_id
      # ...
  ```

**Reuse Constraint**:
- ✅ **MUST be reused**: Direct import in both public (hosted) and private (sandbox internal) routers
- ✅ **MUST be extended** (if needed): Add new permission types (e.g., observability:read), but preserve existing checks
- ❌ **DO NOT modify**: Permission wildcard matching logic or error semantics
- ❌ **DO NOT rebuild**: Custom auth context injection mechanism
- **Justification**: Auth middleware is the gate for all authenticated operations; consistency across modules is critical

**Error Handling**:
- 401 Unauthorized: Missing/invalid JWT token
- 403 Forbidden: Valid token but insufficient permissions
- See `auth_errors.py` for error response formatting

**Test Coverage**:
- Permission matching, middleware initialization, error handling in unit tests

---

## 5. Logging Middleware (logging_middleware.py)

**Module**: `src/back/boring_ui/api/logging_middleware.py`

**Responsibility**:
- Request ID generation and propagation for end-to-end tracing
- Structured logging with correlation fields (JSON format)
- Cross-service trace correlation (sandbox, companion, etc.)
- Performance instrumentation (latency tracking per request)

**Key Components**:

### RequestIDMiddleware
- Generates unique request_id (UUID) for each request or inherits from X-Request-ID header
- Attaches to request.state.request_id
- Includes in response headers (X-Request-ID, X-Process-Time)

### StructuredLoggingMiddleware
- Logs all HTTP requests with structured fields: request_id, method, path, status, latency_ms, user_id
- Skips logging for health checks, DEBUG level for internal endpoints
- JSON-formatted logs for machine parsing

### Helper Functions
- `get_request_id(request)` → Extract request_id from request state
- `propagate_request_context(request, headers)` → Build headers for outbound requests to maintain trace correlation
- `_configure_structured_logging()` → Set up JSON formatter for Python logging

**Integration Point**:
- Location: `boring_ui.api.logging_middleware`
- Usage in app factory (add early in middleware stack):
  ```python
  from boring_ui.api.logging_middleware import (
      add_logging_middleware,
      get_request_id,
      propagate_request_context,
  )

  # Add to app (must be before other middlewares)
  add_logging_middleware(app)

  # Use in routes
  async def my_route(request: Request):
      request_id = get_request_id(request)
      logger.info(f"Processing request {request_id}")

      # Propagate to subservices
      headers = propagate_request_context(request, {'User-Agent': 'MyApp'})
      response = await client.get(..., headers=headers)
  ```

**Reuse Constraint**:
- ✅ **MUST be reused**: Import in both public and private app factories
- ✅ **Observable**: Logs are machine-readable JSON for aggregation into observability platforms
- ❌ **DO NOT modify**: Request ID generation logic, JSON formatter structure
- ❌ **DO NOT rebuild**: Custom logging middleware
- **Justification**: Request correlation is critical for debugging distributed systems; reuse ensures consistent trace IDs across modules

**Integration with Audit** (bd-1pwb.9.1):
- Audit events use request_id from logging middleware for correlation
- Structured log fields (request_id, user_id, workspace_id) are standard across all audit events

---

## 6. Audit Logging (audit.py + audit_persistence.py)

**Module**: `src/back/boring_ui/api/audit.py` and `audit_persistence.py`

**Responsibility**:

### AuditLogger (audit.py)
- Centralized audit logging for security and compliance
- Logs both to stdout (structured logging) and persistent storage
- Records: auth events (success/failure/denial), file operations (read/write), exec operations
- Query interface for compliance review and forensics
- Metrics collection: counters for auth success/failure, file ops, exec ops, uptime

### AuditStore (Abstract, audit_persistence.py)
- Abstract interface for audit event persistence
- Two implementations:
  - **InMemoryAuditStore**: Fast, for testing/development (events lost on restart)
  - **FileAuditStore**: JSONL file for production (immutable audit trail)

### AuditEvent (audit_models.py)
- Data structure for audit events
- Fields: event_type, timestamp, trace_id, user_id, workspace_id, resource, action, status, details
- Event types: AUTH_SUCCESS, AUTH_FAILURE, AUTHZ_DENIED, FILE_READ, FILE_WRITE, EXEC_RUN

**Integration Point**:
- Location: `boring_ui.api.audit:AuditLogger`, `audit_persistence`
- Global instance: `boring_ui.api.audit:audit_logger` (FileAuditStore by default)
- Usage:
  ```python
  from boring_ui.api.audit import audit_logger
  from boring_ui.api.logging_middleware import get_request_id

  # Log auth success
  audit_logger.log_auth_success(
      user_id='user123',
      workspace_id='workspace-abc',
      request_id=get_request_id(request)
  )

  # Log file operation
  audit_logger.log_file_operation(
      user_id='user123',
      operation='read',
      path='/path/to/file.txt',
      workspace_id='workspace-abc',
      request_id=get_request_id(request)
  )

  # Query events
  events = await audit_logger.query_events(
      user_id='user123',
      start_time=datetime.now() - timedelta(days=7)
  )

  # Get metrics
  metrics = audit_logger.get_metrics()
  ```

**Reuse Constraint**:
- ✅ **MUST be reused**: Global audit_logger instance in both modules
- ✅ **MUST integrate with logging middleware**: All audit events use request_id from logging_middleware for correlation
- ❌ **DO NOT modify**: AuditEvent structure, event type enums, store interface
- ❌ **DO NOT rebuild**: Custom audit logging implementation
- **Justification**: Audit trail is immutable and cross-module; reuse ensures comprehensive forensics

**Storage** (bd-1pwb.9.2):
- Default: FileAuditStore at `.audit/events.jsonl` (JSONL format, thread-safe)
- Configurable: Pass different store type via factory: `create_audit_store(store_type='memory')`
- Query interface supports filtering by event type, user, workspace, time range

**Test Coverage**:
- Audit event logging and storage in existing unit tests
- Query filtering and metrics collection tested

---

## Summary Table

| Component | Module | Responsibility | Must Reuse? | Must NOT Rebuild |
|-----------|--------|-----------------|-------------|------------------|
| **ServiceTokenIssuer** | auth.py | JWT/bearer token issuance | ✅ YES | Custom token systems |
| **RunMode + APIConfig** | config.py | Configuration + mode selection | ✅ YES | Custom config loading |
| **OIDCVerifier** | auth.py | OIDC JWT verification | ✅ YES | Custom OIDC handlers |
| **AuthMiddleware** | auth_middleware.py | JWT validation + context injection | ✅ YES | Custom auth context logic |
| **LoggingMiddleware** | logging_middleware.py | Request correlation + structured logs | ✅ YES | Custom logging middleware |
| **AuditLogger** | audit.py | Audit event logging | ✅ YES | Custom audit systems |
| **AuditStore** | audit_persistence.py | Audit persistence interface | ✅ YES | Custom storage backends |

---

## Anti-Patterns (What NOT to Do)

1. ❌ **DO NOT create a new ServiceTokenIssuer-like class** — Reuse the existing one
2. ❌ **DO NOT create custom RunMode/APIConfig** — Reuse the dataclass pattern
3. ❌ **DO NOT implement custom OIDC verification** — Reuse OIDCVerifier
4. ❌ **DO NOT bypass auth_middleware** — Extend permissions instead
5. ❌ **DO NOT add custom logging to bypass logging_middleware** — Extend formatter if needed
6. ❌ **DO NOT rebuild audit trail** — Extend AuditLogger methods if needed

---

## Import Convention (For Refactor)

All components should be imported with full module paths for clarity:

```python
# ✅ Good - clear where each component comes from
from boring_ui.api.auth import ServiceTokenIssuer, OIDCVerifier
from boring_ui.api.config import RunMode, APIConfig
from boring_ui.api.auth_middleware import add_oidc_auth_middleware, AuthContext, get_auth_context
from boring_ui.api.logging_middleware import add_logging_middleware, get_request_id
from boring_ui.api.audit import audit_logger

# ❌ Avoid - ambiguous imports
from boring_ui.api.auth import *
```

---

## Related Beads

- **bd-1adh.1.2**: Embed these module references into architecture plan
- **bd-1adh.1.3**: Define non-goals to prevent scope creep
- **bd-1adh.2**: Extract local-api package (uses all of these components)
- **bd-1adh.3**: Runtime mode matrix (uses RunMode/APIConfig)
- **bd-1pwb.2**: Hosted auth middleware (reuses all auth components)
- **bd-1pwb.9**: Observability/audit (reuses logging + audit components)
