# bd-1adh.1.1: Component Inventory for Reuse

**Date**: 2026-02-11
**Task**: Inventory existing auth/config/audit/logging components to reuse in two-module refactor

## Overview

This document catalogs all existing reusable components in the boring-ui backend that should be referenced and reused during the `bd-1adh` refactor. The goal is to maximize code reuse and minimize re-implementation of stable, proven patterns.

## Configuration & Startup (config.py)

### RunMode Enum
- **Purpose**: Distinguish LOCAL vs HOSTED execution modes
- **Location**: `config.py:8-31`
- **Key Features**:
  - Case-insensitive parsing via `RunMode.from_env()`
  - Defaults to LOCAL if `BORING_UI_RUN_MODE` not set
  - Used throughout app to branch behavior

### APIConfig Dataclass
- **Purpose**: Central configuration for all API routers (dependency injection)
- **Location**: `config.py:83-193`
- **Key Fields**:
  - `workspace_root`: Base directory for all file operations
  - `run_mode`: LOCAL or HOSTED
  - `cors_origins`: CORS whitelist
  - `filesystem_source`: 'local', 'sandbox', or 'sprites'
  - `pty_providers`: Shell and Claude CLI config
  - `oidc_*`: OIDC IdP configuration (hosted mode)

### Path Validation (APIConfig.validate_path)
- **Purpose**: CRITICAL security control - prevent path traversal attacks
- **Location**: `config.py:114-139`
- **Contract**: All file operations MUST use this before accessing filesystem
- **Returns**: Absolute path within workspace_root or raises ValueError
- **Pattern**: Used in file_routes.py and git_routes.py

### Startup Validation (APIConfig.validate_startup)
- **Purpose**: Enforce required environment variables per mode at startup
- **Location**: `config.py:164-192`
- **LOCAL mode requires**: WORKSPACE_ROOT
- **HOSTED mode requires**: WORKSPACE_ROOT, OIDC_ISSUER, OIDC_AUDIENCE (or DEV_AUTH_BYPASS=1)
- **Error Handling**: Raises ValueError with actionable message

### Helper Functions
- **`get_cors_origin()`** (line 52): Detect CORS origin from env for subprocess config
- **`is_dev_auth_bypass_enabled()`** (line 74): Check DEV_AUTH_BYPASS flag (dev-only)

## Authentication: Service Tokens (auth.py)

### ServiceTokenIssuer Class
- **Purpose**: Issues tokens for service-to-service auth (Direct Connect)
- **Location**: `auth.py:30-105`
- **Two token types**:
  1. **JWT (HS256)**: For services that validate claims (Companion/Hono)
     - Method: `issue_token(service, ttl_seconds=3600)` → JWT string
     - Short-lived: `issue_query_param_token(service)` → 120s TTL (safe for query params)
  2. **Bearer token**: For services with built-in `--token` flag (sandbox-agent)
     - Method: `generate_service_token()` → hex string (no JWT, no expiry)
- **Signing Key**: Random 256-bit generated at startup, regenerated each session
- **Key Property**: `signing_key_hex` for passing to subprocesses via env var
- **Verification**: `verify_token(token, signing_key_hex, expected_service)` → dict or None (fail-closed)

### OIDCVerifier Class
- **Purpose**: Validate JWTs from external OIDC identity providers (Auth0, Cognito, etc.)
- **Location**: `auth.py:108-319`
- **Configuration** (env vars):
  - `OIDC_ISSUER`: IdP issuer URL
  - `OIDC_AUDIENCE`: Expected audience claim
  - `OIDC_CACHE_TTL_SECONDS`: JWKS cache lifetime (default 3600s)
- **Key Features**:
  - Fetches and caches JWKS from `.well-known/jwks.json`
  - Validates token signature (RS256), issuer, audience, expiry
  - Automatic key rotation: on signature mismatch, refreshes JWKS
  - Observable cache stats: `cache_stats` property (hits, misses, total)
- **Methods**:
  - `verify_token(token)` → claims dict or None (fail-closed)
  - `from_env()` → OIDCVerifier or None (factory method)
- **Cache Behavior**:
  - Hit: return cached JWKS
  - Miss: fetch fresh, cache for TTL, log refresh
  - Key rotation: detected on InvalidSignatureError, cache cleared, retry once

## Authentication Errors (auth_errors.py)

### AuthErrorEmitter Class
- **Purpose**: Standardize error responses for auth failures (401 vs 403)
- **Location**: `auth_errors.py`
- **Key Methods**:
  - `missing_token(path, request_id)` → JSONResponse (401)
  - `invalid_token(path, reason, request_id)` → JSONResponse (401)
  - `insufficient_permission(path, user_id, permission, current_perms, request_id)` → JSONResponse (403)
- **Error Contract**: `{code, message, request_id}` for machine-readable handling

## Authentication Middleware (auth_middleware.py)

### AuthContext Dataclass
- **Purpose**: Represents authenticated user with permissions and workspace context
- **Location**: `auth_middleware.py:29-78`
- **Fields**:
  - `user_id`: Subject from JWT 'sub' claim
  - `workspace_id`: From JWT 'workspace' claim or default
  - `permissions`: Set of permission strings (e.g., 'files:read', 'git:*')
  - `claims`: Full JWT payload
- **Methods**:
  - `has_permission(permission)` → bool (supports wildcards: 'git:*', '*')

### add_oidc_auth_middleware() Function
- **Purpose**: FastAPI middleware for JWT validation and auth context injection
- **Location**: `auth_middleware.py:81-209`
- **Behavior**:
  - Extracts Bearer token from Authorization header
  - Validates JWT using OIDCVerifier
  - Injects AuthContext into `request.state.auth_context`
  - Returns 401 for invalid/missing credentials
  - Allows public routes (/health, OPTIONS preflight) without auth
- **Integration**: Only activates if OIDC configured and run_mode is HOSTED

### Helper Functions
- **`get_auth_context(request)`** (line 212): Extract AuthContext, raise 401 if missing
- **`require_permission(permission)`** (line 235): Decorator for route-level permission checks

## Audit & Observability

### AuditEvent & AuditEventType (audit_models.py)
- **Purpose**: Data structures for audit logging
- **Location**: `audit_models.py`
- **Event Types**: AUTH_SUCCESS, AUTH_FAILURE, FILE_READ, FILE_WRITE, GIT_OPERATION, EXEC_RUN, etc.

### AuditLogger Class
- **Purpose**: Centralized audit logging for security and compliance
- **Location**: `audit.py:25-150+`
- **Key Methods**:
  - `log_auth_success(user_id, workspace_id, request_id)` → Event
  - `log_auth_failure(reason, request_id)` → Event
  - `log_file_operation(user_id, workspace_id, op_type, path, request_id)` → Event
  - `log_git_operation(user_id, workspace_id, command, request_id)` → Event
  - `log_exec_operation(user_id, workspace_id, command, status, request_id)` → Event
- **Metrics Integration**: Records counters via `self.metrics`
- **Persistence**: Optional storage backend (bd-1pwb.9.2) for forensics

### AuditStore Interface & FileAuditStore
- **Purpose**: Abstraction for audit event persistence
- **Location**: `audit_persistence.py`
- **Methods**: `store(event)` → writes to backend
- **Implementations**: FileAuditStore (write to disk), extensible for other backends

## Logging & Request Correlation (logging_middleware.py)

### RequestIDMiddleware Class
- **Purpose**: Generate and propagate request IDs for end-to-end tracing
- **Location**: `logging_middleware.py:78-113+`
- **Behavior**:
  - Generates UUID for each request (or uses X-Request-ID header if present)
  - Attaches to `request.state.request_id`
  - Includes in response headers (X-Request-ID)
  - Tracks latency for performance instrumentation

### Structured Logging
- **Purpose**: JSON-formatted logs with correlation fields
- **Location**: `logging_middleware.py:20-75`
- **Configuration**: `_configure_structured_logging()`
- **Log Fields**: timestamp, level, logger, message, request_id, user_id, method, path, status, latency_ms
- **Use Pattern**: Create log records with custom fields via `logger.makeRecord()`

## Capability Tokens (capability_tokens.py)

### CapabilityToken Dataclass
- **Purpose**: Operation-scoped, short-lived tokens for service-to-service auth
- **Location**: `capability_tokens.py:33-82`
- **Fields**:
  - `workspace_id`: Target workspace
  - `operations`: Set of allowed ops (e.g., 'files:read', 'git:status')
  - `ttl_seconds`: Token lifetime (5-3600s, default 60s)
  - `jti`: Unique ID for replay resistance
- **Method**: `to_claims()` → JWT claims dict

### CapabilityTokenIssuer Class
- **Purpose**: Signs capability tokens (RS256)
- **Location**: `capability_tokens.py:85-120+`
- **Methods**: `issue_token(capability)` → signed JWT

## Route Patterns

### create_file_router(config: APIConfig, storage: Storage) -> APIRouter
- **Location**: `file_routes.py:28-80+`
- **Pattern**:
  - All routes use `validate_and_relativize(path)` helper
  - Path validation prevents traversal attacks
  - Storage backend abstraction allows pluggable implementations
- **Endpoints**:
  - GET `/tree` - list directory
  - GET `/file` - read file
  - PUT `/file` - write file
  - DELETE `/file` - delete file
  - POST `/file/rename` - rename
  - POST `/file/move` - move

### create_git_router(config: APIConfig) -> APIRouter
- **Location**: `git_routes.py:8-90+`
- **Pattern**:
  - Runs git commands in workspace_root
  - All commands use subprocess with timeout (30s)
  - Error handling converts git stderr to HTTPException
- **Endpoints**:
  - GET `/status` - repository status (porcelain format)
  - GET `/diff` - diff against HEAD
  - GET `/show` - show file at commit

## Key Patterns for Reuse

1. **Configuration Injection**: Pass APIConfig to all router factories
2. **Path Validation**: All file operations must validate via `config.validate_path()`
3. **Error Context**: Request IDs and user IDs in all structured logs
4. **Fail-Closed Auth**: Missing/invalid tokens return None (no exceptions)
5. **Token Naming**: SERVICE = service name, JTI = UUID for replay resistance
6. **Middleware Stacking**: RequestIDMiddleware → add_oidc_auth_middleware() → routers
7. **Storage Abstraction**: File operations use Storage interface (not direct filesystem)

## Acceptance Criteria for Reuse

- [x] All auth/config/audit/logging components identified
- [x] Inventory documents component purposes and locations
- [x] Key patterns for reuse are clear
- [x] Non-goals: no re-implementation, only reference and document

## Files to Reference During Refactor

- `config.py` - RunMode, APIConfig, path validation, startup checks
- `auth.py` - ServiceTokenIssuer, OIDCVerifier
- `auth_errors.py` - AuthErrorEmitter, error contract
- `auth_middleware.py` - AuthContext, middleware setup
- `audit.py` - AuditLogger, audit events
- `audit_models.py` - AuditEvent, AuditEventType
- `audit_persistence.py` - AuditStore interface
- `logging_middleware.py` - RequestIDMiddleware, structured logging
- `capability_tokens.py` - CapabilityToken, CapabilityTokenIssuer
- `file_routes.py` - Router factory pattern, path validation
- `git_routes.py` - Subprocess execution pattern

## Next Steps (bd-1adh.1.2+)

1. **bd-1adh.1.2**: Embed concrete module references into architecture plan
2. **bd-1adh.1.3**: Define non-goals and anti-scope-creep checklist
3. **bd-1adh.2.1**: Create local_api package with parity implementations
4. **bd-1adh.2.2**: Compose local_api router/app factories
5. **bd-1adh.2.3**: Rewire control-plane imports, remove legacy modules
