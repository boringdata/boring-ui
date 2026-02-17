# Sprites Provider Integration

## Bead: bd-sprites

**Status**: Draft
**Priority**: P2
**Type**: Feature
**Owner**: —

---

## Executive Summary

Integrate the `poc-sprites` proof-of-concept into boring-ui by creating a `SpritesProvider` that implements the existing `SandboxProvider` interface. This enables persistent, per-user coding sandboxes using Sprites.dev (Fly.io) with near-zero idle cost and fast wake times.

**Key integration point**: SpritesProvider implements the Direct Connect architecture — browsers connect directly to sprite-hosted sandbox-agent, not through boring-ui proxy.

---

## Background

### What is Sprites.dev?

Sprites.dev (by Fly.io) provides persistent Linux VMs that:
- Sleep after ~30s of idle (costs ~$0 while sleeping)
- Wake automatically on HTTP request (~3-5s)
- Persist filesystem across sleep/wake cycles
- Support copy-on-write checkpoints (~300ms to create)

### POC-sprites Architecture

The proof-of-concept at `~/projects/boring-agent-sandbox/poc-sprites/` demonstrates:

```
POST /sandboxes ──► FastAPI ──► Sprites.dev
                              │
                              ▼
                     ┌──────────────────────────┐
                     │  Sprite (persistent VM)  │
                     │                          │
                     │  /home/sprite/workspace/ │
                     │    └─ <cloned repo>      │
                     │                          │
                     │  sandbox-agent :2468     │
                     │    ├─ Claude Code agent  │
                     │    ├─ Session management │
                     │    └─ SSE streaming      │
                     └──────────────────────────┘
```

### Existing boring-ui Provider System

boring-ui already has a provider abstraction in `src/back/boring_ui/api/modules/sandbox/`:

| File | Purpose |
|------|---------|
| `provider.py` | Abstract `SandboxProvider` interface |
| `providers/local.py` | `LocalProvider` - subprocess on host |
| `providers/modal.py` | `ModalProvider` - stub for future |
| `manager.py` | `SandboxManager` orchestration + factory |

### Direct Connect Architecture

boring-ui uses a **Direct Connect** architecture where browsers connect directly to chat services. The backend is the **control plane** (lifecycle, auth tokens), not the **data plane** (chat traffic).

See `.planning/DIRECT_CONNECT_ARCHITECTURE.md` for full details.

---

## Requirements

### Functional

1. **SpritesProvider** - Implement `SandboxProvider` interface for Sprites.dev
2. **SpritesClient** - Async client wrapping Sprites REST API + CLI exec
3. **Multi-user support** - Each user gets their own persistent sprite (1:1 mapping)
4. **Checkpoint API** - Create and restore filesystem snapshots
5. **Direct Connect integration** - Browser connects directly to sprite URL with HMAC token
6. **Credential handling** - API key/OAuth token passed at creation, stored only in sprite
7. **Auth secret rotation** - Mechanism to update `SERVICE_AUTH_SECRET` in persistent sprites

### Non-Functional

1. **Cold start**: ~24s for new user (sprite creation + setup)
2. **Warm start**: ~3-5s for returning user (sprite wake)
3. **Checkpoint create**: ~300ms
4. **Checkpoint restore**: ~1s
5. **Idle cost**: ~$0/month (durable storage only)

---

## Direct Connect Integration (NEW)

### Architecture

SpritesProvider extends the Direct Connect architecture to remote VMs:

```
┌─────────────────────────────────────────────────────────────────┐
│                boring-ui Backend (FastAPI :8000)                  │
│                       CONTROL PLANE                              │
│                                                                  │
│  SpritesProvider                                                 │
│    ├─ Creates/destroys sprites                                   │
│    ├─ Provisions SERVICE_AUTH_SECRET to sprites                  │
│    ├─ Rotates secrets on backend restart                         │
│    └─ Returns sprite URL + token via capabilities                │
│                                                                  │
│  ServiceTokenIssuer                                              │
│    └─ Issues HMAC tokens for browser → sprite auth               │
└───────────────────────────────────────────────────────────────────┘
         │                              │
   secret provisioning           token issuance
         │                              │
         ▼                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Sprite VM (Fly.io)                             │
│                    https://sb-{user_hash}.sprites.app             │
│                                                                  │
│  sandbox-agent :2468                                             │
│    ├─ Auth middleware validates HMAC tokens                      │
│    ├─ SERVICE_AUTH_SECRET from /home/sprite/.auth/secret         │
│    └─ CORS_ORIGIN from /home/sprite/.auth/cors_origin            │
│                                                                  │
│  /home/sprite/workspace/                                         │
│    └─ <cloned repo>                                              │
│                                                                  │
│  /home/sprite/.auth/  (NOT in workspace, excluded from checkpoint)│
│    ├─ secret          (SERVICE_AUTH_SECRET)                      │
│    ├─ cors_origin     (allowed origin for CORS)                  │
│    └─ credentials.env (ANTHROPIC_API_KEY, etc)                   │
└──────────────────────────────────────────────────────────────────┘
         ▲
         │
    DIRECT connection
    (HMAC token in header)
         │
    ┌────┴────┐
    │ Browser │
    └─────────┘
```

### Connection Flow

```
1. User requests sandbox via boring-ui frontend
2. Frontend calls POST /api/sandbox/start
3. SpritesProvider.create() provisions sprite:
   a. Creates sprite (or wakes existing)
   b. Writes SERVICE_AUTH_SECRET to /home/sprite/.auth/secret
   c. Writes CORS_ORIGIN to /home/sprite/.auth/cors_origin
   d. Restarts sandbox-agent service if secrets changed
4. Backend returns via GET /api/capabilities:
   {
     "services": {
       "sandbox": {
         "url": "https://sb-a1b2c3.sprites.app",
         "token": "eyJhbGciOiJIUzI1NiJ9...",
         "protocol": "rest+sse"
       }
     }
   }
5. Frontend connects DIRECTLY to sprite URL with token
6. sandbox-agent validates token using SERVICE_AUTH_SECRET
```

### Secret Provisioning & Rotation

**Problem**: boring-ui generates a new `SERVICE_AUTH_SECRET` on each startup. Persistent sprites would have stale secrets.

**Solution**: SpritesProvider provisions secrets to sprites on every `ensure_running()` call:

```python
async def ensure_running(self, sandbox_id: str) -> SandboxInfo:
    """Ensure sprite is running with current auth secret.

    Called before returning capabilities. Handles:
    1. Wake sprite if sleeping
    2. Check if SERVICE_AUTH_SECRET matches current
    3. If mismatch, update secret and restart sandbox-agent
    4. Return SandboxInfo with current sprite URL
    """
    sprite = await self._client.get_sprite(sandbox_id)

    # Read current secret from sprite
    current_secret = await self._read_sprite_secret(sandbox_id)

    if current_secret != self._signing_key_hex:
        # Secret rotated - update sprite and restart service
        await self._provision_auth_secret(sandbox_id)
        await self._restart_sandbox_agent(sandbox_id)

    return SandboxInfo(
        id=sandbox_id,
        base_url=sprite["url"],
        status="running",
        ...
    )
```

### Auth Secret Storage in Sprite

Secrets are stored outside the workspace to exclude from checkpoints:

```
/home/sprite/
├── .auth/                    # Auth directory (NOT checkpointed)
│   ├── secret                # SERVICE_AUTH_SECRET (hex)
│   ├── cors_origin           # Allowed CORS origin
│   └── credentials.env       # ANTHROPIC_API_KEY, etc
│
├── workspace/                # User's cloned repo (checkpointed)
│   └── ...
│
└── start-agent.sh            # Launcher that reads from .auth/
```

**start-agent.sh** (reads secrets at runtime, not embedded):

```bash
#!/bin/bash
set -e

# Load auth secret for token validation
export SERVICE_AUTH_SECRET=$(cat /home/sprite/.auth/secret)
export CORS_ORIGIN=$(cat /home/sprite/.auth/cors_origin)

# Load user credentials
if [ -f /home/sprite/.auth/credentials.env ]; then
    source /home/sprite/.auth/credentials.env
fi

cd /home/sprite/workspace
exec sandbox-agent server --no-token --host 0.0.0.0 --port 2468
```

This design means:
- **Checkpoints do NOT include secrets** (`.auth/` is outside workspace)
- **Secret rotation is safe** (just update files and restart)
- **Restore doesn't restore old secrets** (secrets are not in checkpoint)

---

## Technical Design

### Identity Model

**Single source of truth**: `user_id` is the authority. `sandbox_id` is derived.

```python
def _derive_sandbox_id(self, user_id: str) -> str:
    """Derive deterministic sandbox_id from user_id.

    Uses SHA256 hash prefix to:
    - Sanitize arbitrary user_id input
    - Prevent information disclosure (can't reverse to user_id)
    - Ensure valid sprite name characters
    - Fixed length (prevents long names)
    """
    user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    return f"{self._name_prefix}sb-{user_hash}"
```

**Callers provide `user_id` only**, not `sandbox_id`:

```python
async def create(self, config: SandboxCreateConfig) -> SandboxInfo:
    """Create sandbox for user.

    sandbox_id is derived from config.user_id, NOT passed separately.
    This prevents mismatched identity values.
    """
    if not config.user_id:
        raise ValueError("user_id is required")

    sandbox_id = self._derive_sandbox_id(config.user_id)
    # ... rest of creation
```

### Input Sanitization

All user-provided inputs that touch shell commands MUST be sanitized:

```python
from typing import Literal
import shlex
import re

class InputSanitizer:
    """Sanitize user inputs before shell interpolation."""

    # Allowed characters for git refs (branches)
    GIT_REF_PATTERN = re.compile(r'^[a-zA-Z0-9._/-]+$')

    # Allowed URL schemes
    ALLOWED_SCHEMES = ('https://', 'git@')

    @staticmethod
    def sanitize_branch(branch: str) -> str:
        """Validate and return branch name.

        Raises ValueError if invalid.
        """
        if not branch or len(branch) > 255:
            raise ValueError(f"Invalid branch length: {len(branch)}")
        if not InputSanitizer.GIT_REF_PATTERN.match(branch):
            raise ValueError(f"Invalid branch name: {branch}")
        if '..' in branch:
            raise ValueError("Branch name cannot contain '..'")
        return branch

    @staticmethod
    def sanitize_repo_url(url: str) -> str:
        """Validate and return repo URL.

        Raises ValueError if invalid.
        """
        if not url or len(url) > 2048:
            raise ValueError(f"Invalid URL length: {len(url)}")
        if not any(url.startswith(scheme) for scheme in InputSanitizer.ALLOWED_SCHEMES):
            raise ValueError(f"URL must start with {InputSanitizer.ALLOWED_SCHEMES}")
        # Basic injection check - no shell metacharacters
        if any(c in url for c in ['$', '`', ';', '|', '&', '\n', '\r']):
            raise ValueError("URL contains invalid characters")
        return url

    @staticmethod
    def quote_for_shell(value: str) -> str:
        """Shell-escape a value for safe interpolation."""
        return shlex.quote(value)
```

### SpritesClient

Async client with **argv-based execution** (not shell strings):

```python
class SpritesClient:
    """Async client for Sprites.dev platform.

    REST API for CRUD + checkpoints.
    CLI for command execution (exec API is WebSocket-only).
    """

    def __init__(
        self,
        token: str,
        org: str,
        base_url: str = "https://api.sprites.dev",
        cli_path: str = "sprite",
        name_prefix: str = "",
        retry_config: RetryConfig | None = None,
    ):
        self._token = token
        self._org = org
        self._base_url = base_url
        self._cli_path = cli_path
        self._name_prefix = name_prefix
        self._retry_config = retry_config or RetryConfig()

        # Fail fast if CLI not available
        self._verify_cli_available()

    # Command execution - ARGV form, not shell string
    async def exec_argv(
        self,
        sprite_name: str,
        argv: list[str],
        timeout: float = 120.0,
        cwd: str = "/home/sprite",
    ) -> tuple[int, str, str]:
        """Execute command in sprite using argv (no shell).

        Args:
            sprite_name: Target sprite
            argv: Command as list ['git', 'clone', url]
            timeout: Max seconds to wait
            cwd: Working directory in sprite

        Returns:
            (return_code, stdout, stderr)

        This is the PREFERRED method - no shell interpolation.
        """
        # Build sprite CLI command
        cmd = [self._cli_path, "exec", sprite_name, "--", *argv]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # ... timeout handling

    async def exec_script(
        self,
        sprite_name: str,
        script: str,
        timeout: float = 120.0,
    ) -> tuple[int, str, str]:
        """Execute shell script in sprite.

        WARNING: Only use for trusted scripts (setup scripts).
        Never interpolate user input into script.

        Args:
            sprite_name: Target sprite
            script: Shell script content (must be trusted)
            timeout: Max seconds to wait

        Returns:
            (return_code, stdout, stderr)
        """
        # Write script to temp file, then execute
        # This avoids shell escaping issues with complex scripts
        ...
```

### Retry Strategy

Enhanced retry with jitter and proper status handling:

```python
from dataclasses import dataclass
import random

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter_factor: float = 0.5
    retry_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    # Operations safe to retry (idempotent)
    safe_operations: frozenset[str] = frozenset({
        "get_sprite", "list_sprites", "list_checkpoints",
        "health_check", "exec_argv", "exec_script",
    })

async def _request_with_retry(
    self,
    method: str,
    url: str,
    operation: str,
    **kwargs,
) -> httpx.Response:
    """Make HTTP request with exponential backoff + jitter.

    Args:
        method: HTTP method
        url: Request URL
        operation: Operation name (for retry safety check)
        **kwargs: Passed to httpx

    Raises:
        SpritesAPIError: On non-retryable error or exhausted retries
    """
    last_error = None

    for attempt in range(self._retry_config.max_retries):
        try:
            resp = await self._http.request(method, url, **kwargs)

            # Handle rate limiting
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                if attempt < self._retry_config.max_retries - 1:
                    await asyncio.sleep(retry_after)
                    continue

            # Retry on configured statuses
            if resp.status_code in self._retry_config.retry_statuses:
                raise SpritesAPIError(resp.status_code, resp.text)

            return resp

        except (httpx.ConnectError, httpx.TimeoutException, SpritesAPIError) as e:
            last_error = e

            # Only retry safe operations
            if operation not in self._retry_config.safe_operations:
                raise

            if attempt < self._retry_config.max_retries - 1:
                # Exponential backoff with jitter
                delay = min(
                    self._retry_config.base_delay * (2 ** attempt),
                    self._retry_config.max_delay,
                )
                jitter = delay * self._retry_config.jitter_factor * random.random()
                await asyncio.sleep(delay + jitter)
            else:
                raise

    raise last_error
```

### Provider Error Types

Consistent error hierarchy at provider boundary:

```python
# provider.py - Base errors

class SandboxError(Exception):
    """Base exception for sandbox operations."""
    pass

class SandboxNotFoundError(SandboxError):
    """Sandbox does not exist."""
    pass

class SandboxExistsError(SandboxError):
    """Sandbox already exists with incompatible config."""
    def __init__(self, sandbox_id: str, existing_repo: str, requested_repo: str):
        self.sandbox_id = sandbox_id
        self.existing_repo = existing_repo
        self.requested_repo = requested_repo
        super().__init__(
            f"Sandbox {sandbox_id} exists with repo {existing_repo}, "
            f"cannot change to {requested_repo}"
        )

class SandboxProvisionError(SandboxError):
    """Failed to provision sandbox."""
    pass

class SandboxTimeoutError(SandboxError):
    """Operation timed out."""
    pass

class SandboxAuthError(SandboxError):
    """Authentication/authorization error."""
    pass

class CheckpointError(SandboxError):
    """Checkpoint operation failed."""
    pass

class CheckpointNotSupportedError(CheckpointError):
    """Provider does not support checkpoints."""
    pass
```

### Checkpoint API Design

Use structured result types instead of `None`:

```python
from dataclasses import dataclass
from typing import TypeVar, Generic

T = TypeVar('T')

@dataclass
class CheckpointResult(Generic[T]):
    """Result of a checkpoint operation."""
    success: bool
    data: T | None = None
    error: str | None = None

@dataclass
class CheckpointInfo:
    """Information about a checkpoint."""
    id: str
    label: str
    created_at: str
    size_bytes: int | None = None

class SandboxProvider(ABC):
    # ... existing methods ...

    def supports_checkpoints(self) -> bool:
        """Whether this provider supports checkpoints."""
        return False

    async def create_checkpoint(
        self, sandbox_id: str, label: str = ""
    ) -> CheckpointResult[CheckpointInfo]:
        """Create filesystem checkpoint.

        Returns:
            CheckpointResult with success=False if not supported

        Raises:
            CheckpointError: On failure (if supported)
        """
        return CheckpointResult(success=False, error="Not supported")

    async def restore_checkpoint(
        self, sandbox_id: str, checkpoint_id: str
    ) -> CheckpointResult[None]:
        """Restore to checkpoint.

        After restore, credentials are automatically refreshed
        (provider invariant - callers don't need to remember).

        Returns:
            CheckpointResult with success=False if not supported

        Raises:
            CheckpointError: On failure (if supported)
        """
        return CheckpointResult(success=False, error="Not supported")

    async def list_checkpoints(
        self, sandbox_id: str
    ) -> CheckpointResult[list[CheckpointInfo]]:
        """List available checkpoints.

        Returns:
            CheckpointResult with empty list if supported but none exist,
            or success=False if not supported
        """
        return CheckpointResult(success=False, error="Not supported")
```

### SpritesProvider - Checkpoint with Auto-Credential Refresh

```python
class SpritesProvider(SandboxProvider):
    """Sprites.dev provider with Direct Connect support."""

    def supports_checkpoints(self) -> bool:
        return True

    async def restore_checkpoint(
        self, sandbox_id: str, checkpoint_id: str
    ) -> CheckpointResult[None]:
        """Restore checkpoint with automatic credential refresh.

        INVARIANT: After restore, credentials are always refreshed.
        This is enforced at provider level - callers cannot forget.
        """
        logger.info(f"Restoring checkpoint {checkpoint_id} for {sandbox_id}")

        try:
            # 1. Restore the checkpoint
            await self._client.restore_checkpoint(sandbox_id, checkpoint_id)

            # 2. ALWAYS refresh auth secrets (provider invariant)
            # This ensures restored checkpoint doesn't have stale secrets
            await self._provision_auth_secret(sandbox_id)

            # 3. ALWAYS refresh user credentials if we have them
            if sandbox_id in self._credential_cache:
                await self._provision_credentials(
                    sandbox_id,
                    self._credential_cache[sandbox_id]
                )

            # 4. Restart sandbox-agent to pick up refreshed secrets
            await self._restart_sandbox_agent(sandbox_id)

            logger.info(f"Checkpoint restored and credentials refreshed for {sandbox_id}")
            return CheckpointResult(success=True)

        except Exception as e:
            logger.error(f"Checkpoint restore failed: {e}")
            raise CheckpointError(f"Failed to restore checkpoint: {e}") from e
```

### SandboxCreateConfig - Complete

```python
@dataclass
class SandboxCreateConfig:
    """Configuration for creating a sandbox."""

    # Required
    user_id: str
    repo_url: str

    # Git options
    branch: str = "main"

    # Credentials (one required)
    anthropic_api_key: str | None = None
    oauth_token: str | None = None

    # Agent options
    agent: str = "claude"  # claude, codex, opencode, amp

    # Direct Connect options (set by backend, not user)
    service_auth_secret: str | None = None  # Injected by manager
    cors_origin: str | None = None          # Injected by manager

    # Behavior options
    force_recreate: bool = False  # Destroy existing and recreate
    setup_timeout: float = 180.0  # Max seconds for initial setup
    health_timeout: float = 30.0  # Max seconds for health check

    def __post_init__(self):
        """Validate config."""
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.repo_url:
            raise ValueError("repo_url is required")
        if not self.anthropic_api_key and not self.oauth_token:
            raise ValueError("Either anthropic_api_key or oauth_token required")

        # Sanitize inputs
        self.repo_url = InputSanitizer.sanitize_repo_url(self.repo_url)
        self.branch = InputSanitizer.sanitize_branch(self.branch)
```

### SandboxInfo - Extended for Direct Connect

```python
@dataclass
class SandboxInfo:
    """Information about a sandbox."""
    id: str
    status: SandboxStatus
    provider: str

    # Connection info for Direct Connect
    base_url: str              # e.g., "https://sb-a1b2c3.sprites.app"
    protocol: str = "rest+sse" # Service protocol

    # Workspace info
    workspace_path: str = ""

    # Metadata
    user_id: str = ""
    repo_url: str = ""
    created_at: str = ""
    last_active: str = ""

    # Provider-specific
    can_checkpoint: bool = False
    sprite_status: str | None = None  # sleeping, waking, running (sprites only)

# Status enum mapped to Sprites API states
SandboxStatus = Literal[
    "creating",   # Sprite being provisioned
    "starting",   # Setup scripts running
    "running",    # sandbox-agent healthy
    "sleeping",   # Sprite sleeping (will wake on request)
    "waking",     # Sprite waking from sleep
    "stopping",   # Shutdown in progress
    "stopped",    # Sprite stopped
    "error",      # Failed state
]

# Mapping from Sprites API status to SandboxStatus
SPRITES_STATUS_MAP = {
    "creating": "creating",
    "starting": "starting",
    "running": "running",
    "suspended": "sleeping",
    "resuming": "waking",
    "stopping": "stopping",
    "stopped": "stopped",
    "failed": "error",
}
```

### Concurrency Control

Prevent race conditions with per-sandbox mutex:

```python
import asyncio
from contextlib import asynccontextmanager

class SpritesProvider(SandboxProvider):
    def __init__(self, ...):
        ...
        # Per-sandbox locks to prevent concurrent setup
        self._sandbox_locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, sandbox_id: str) -> asyncio.Lock:
        """Get or create lock for sandbox."""
        if sandbox_id not in self._sandbox_locks:
            self._sandbox_locks[sandbox_id] = asyncio.Lock()
        return self._sandbox_locks[sandbox_id]

    @asynccontextmanager
    async def _sandbox_lock(self, sandbox_id: str):
        """Acquire exclusive access to sandbox operations."""
        lock = self._get_lock(sandbox_id)
        async with lock:
            yield

    async def create(self, config: SandboxCreateConfig) -> SandboxInfo:
        """Create sandbox with concurrency protection."""
        sandbox_id = self._derive_sandbox_id(config.user_id)

        async with self._sandbox_lock(sandbox_id):
            # Check existing state
            existing = await self._get_existing_sandbox(sandbox_id)

            if existing:
                if existing.repo_url != config.repo_url and not config.force_recreate:
                    raise SandboxExistsError(
                        sandbox_id, existing.repo_url, config.repo_url
                    )
                if existing.status == "running":
                    # Idempotent - return existing
                    return existing
                # Re-run setup for incomplete state

            # Proceed with creation/setup
            return await self._do_create(sandbox_id, config)
```

### Multi-Tenant Authorization

Name prefix is collision prevention, not authorization. Add explicit checks:

```python
class SpritesProvider(SandboxProvider):
    """Provider with authorization enforcement."""

    def __init__(
        self,
        ...
        authorization_callback: Callable[[str, str], bool] | None = None,
    ):
        """
        Args:
            authorization_callback: Optional callback (user_id, sandbox_id) -> bool
                                   to verify user is authorized for sandbox.
                                   If None, uses default derivation check.
        """
        self._authz_callback = authorization_callback or self._default_authz

    def _default_authz(self, user_id: str, sandbox_id: str) -> bool:
        """Default authorization: sandbox_id must match derivation from user_id."""
        expected = self._derive_sandbox_id(user_id)
        return sandbox_id == expected

    async def get_info(self, sandbox_id: str, user_id: str) -> SandboxInfo | None:
        """Get sandbox info with authorization check.

        Raises:
            SandboxAuthError: If user not authorized for sandbox
        """
        if not self._authz_callback(user_id, sandbox_id):
            raise SandboxAuthError(f"User {user_id} not authorized for {sandbox_id}")

        return await self._do_get_info(sandbox_id)
```

---

## Configuration

Environment variables for SpritesProvider:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPRITES_TOKEN` | Yes | — | Sprites.dev API token |
| `SPRITES_ORG` | No | — | Sprites organization slug |
| `SPRITES_API` | No | `https://api.sprites.dev` | API base URL |
| `SPRITES_NAME_PREFIX` | No | — | Prefix for sprite names (collision prevention) |
| `SANDBOX_AGENT_PORT` | No | `2468` | Port for sandbox-agent |
| `DEFAULT_AGENT` | No | `claude` | Coding agent to install |

---

## File Structure

```
src/back/boring_ui/api/modules/sandbox/
├── provider.py              # Extended with Direct Connect, typed errors
├── manager.py               # Updated factory with auth secret injection
├── errors.py                # NEW: Provider error hierarchy
├── sanitize.py              # NEW: Input sanitization
├── providers/
│   ├── __init__.py
│   ├── local.py             # Unchanged
│   ├── modal.py             # Unchanged (stub)
│   ├── sprites.py           # NEW: SpritesProvider
│   └── sprites_client.py    # NEW: Sprites API client
```

---

## Stories

### Story 1: SpritesClient

Create async client for Sprites.dev API.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/providers/sprites_client.py`

**Acceptance criteria:**
- [ ] CLI availability check at init (fail fast with clear error message)
- [ ] REST endpoints for sprite CRUD (create, get, delete, list)
- [ ] `exec_argv()` for safe command execution (no shell)
- [ ] `exec_script()` for trusted scripts only (documented warning)
- [ ] Checkpoint endpoints (create, list, restore)
- [ ] Exponential backoff + jitter for transient errors
- [ ] Respect `Retry-After` header for 429 responses
- [ ] Distinguish safe-to-retry operations from unsafe ones
- [ ] Custom exception hierarchy
- [ ] Unit tests with mocked HTTP/subprocess

**Dependencies:** None (can start immediately)

### Story 2: Provider Interface Extensions

Add Direct Connect support, typed errors, and checkpoint API to base interface.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/provider.py`
- `src/back/boring_ui/api/modules/sandbox/errors.py` (new)
- `src/back/boring_ui/api/modules/sandbox/sanitize.py` (new)

**Acceptance criteria:**
- [ ] Add `SandboxStatus` type with Sprites state mapping
- [ ] Add `SandboxCreateConfig` dataclass with validation
- [ ] Add `CheckpointResult[T]` generic result type
- [ ] Add `CheckpointInfo` dataclass
- [ ] Add checkpoint methods with structured results
- [ ] Add `SandboxInfo.protocol` for Direct Connect
- [ ] Add error hierarchy (SandboxError, SandboxNotFoundError, etc.)
- [ ] Add `InputSanitizer` with branch/URL validation
- [ ] Backward compatible - LocalProvider unchanged
- [ ] Unit tests for all new types and sanitization

**Dependencies:** None (can start immediately, parallel with Story 1)

### Story 3: SpritesProvider Implementation

Implement `SandboxProvider` for Sprites.dev with Direct Connect integration.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/providers/sprites.py`

**Acceptance criteria:**
- [ ] Identity: `sandbox_id` derived from `user_id` hash
- [ ] Direct Connect: provision `SERVICE_AUTH_SECRET` to `.auth/secret`
- [ ] Direct Connect: provision `CORS_ORIGIN` to `.auth/cors_origin`
- [ ] Direct Connect: `ensure_running()` rotates secrets if changed
- [ ] Direct Connect: `start-agent.sh` reads secrets at runtime
- [ ] Credentials: stored in `.auth/credentials.env` (outside workspace)
- [ ] Checkpoints: auto-refresh credentials on restore (provider invariant)
- [ ] Concurrency: per-sandbox mutex prevents race conditions
- [ ] Authorization: verify user authorized for sandbox_id
- [ ] Input sanitization: all user inputs validated before shell
- [ ] Proper cleanup on failure
- [ ] Structured logging with sandbox_id context
- [ ] Unit tests with mocked SpritesClient
- [ ] Test credential refresh on restore
- [ ] Test concurrent create requests

**Dependencies:** Story 1 (SpritesClient), Story 2 (interface)

### Story 4: Manager Integration

Update factory to support sprites provider with Direct Connect auth injection.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/manager.py`
- `src/back/boring_ui/api/modules/sandbox/providers/__init__.py`

**Acceptance criteria:**
- [ ] `create_provider()` supports `SANDBOX_PROVIDER=sprites`
- [ ] Validates required config (SPRITES_TOKEN) at startup
- [ ] Injects `service_auth_secret` from `ServiceTokenIssuer`
- [ ] Injects `cors_origin` from config
- [ ] Calls `ensure_running()` before returning capabilities
- [ ] Export SpritesProvider from `__init__.py`
- [ ] Integration test with real capabilities endpoint

**Dependencies:** Story 3 (SpritesProvider)

### Story 5: Orphan Cleanup Job

Background job to cleanup orphaned sprites.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/cleanup.py`

**Acceptance criteria:**
- [ ] List all sprites with configured prefix
- [ ] Track last activity via sprite metadata (set on each operation)
- [ ] Identify sprites not accessed in N days (configurable)
- [ ] Dry-run mode by default
- [ ] Delete with confirmation in non-dry-run mode
- [ ] Log cleanup actions with sprite names and last access
- [ ] Can be run as CLI command or scheduled task
- [ ] Emit metrics: sprites_deleted, sprites_active, sprites_orphaned
- [ ] Unit tests with mocked client

**Dependencies:** Story 1 (SpritesClient)

### Story 6: Baseline Observability (NEW)

Add minimum production observability.

**Files:**
- `src/back/boring_ui/api/modules/sandbox/metrics.py` (new)

**Acceptance criteria:**
- [ ] Metrics: `sprite_create_duration_seconds` histogram
- [ ] Metrics: `sprite_wake_duration_seconds` histogram
- [ ] Metrics: `sprite_health_check_failures_total` counter
- [ ] Metrics: `sprite_checkpoint_operations_total` counter (labels: operation, result)
- [ ] Metrics: `sprites_active_total` gauge
- [ ] Structured logging for all operations with timing
- [ ] Health check endpoint includes sprite stats
- [ ] Unit tests for metric registration

**Dependencies:** Story 3 (SpritesProvider)

---

## Story Execution Order

```
Week 1:
  Story 1 (SpritesClient)     ──────────────────►
  Story 2 (Interface)         ──────────────────►

Week 2:
                               Story 3 (SpritesProvider) ──────────────────►

Week 3:
                                                          Story 4 (Manager) ─────►
                               Story 5 (Cleanup)         ──────────────────────►
                               Story 6 (Observability)   ──────────────────────►
```

- **Stories 1 & 2**: Parallel (no dependencies)
- **Story 3**: Blocked by 1 & 2
- **Stories 4, 5, 6**: Can run in parallel after Story 3 (4 depends on 3, 5 & 6 only need client)

---

## Testing Strategy

### Unit Tests

- `SpritesClient`: Mock httpx and subprocess, test retry logic, test argv execution
- `SpritesProvider`: Mock client, test identity derivation, test secret rotation
- `InputSanitizer`: Test rejection of malicious inputs
- `CheckpointResult`: Test type safety

### Integration Tests

- Real Sprites.dev account with test org
- Create sprite, provision secrets, verify sandbox-agent validates tokens
- Test secret rotation (restart backend, verify new tokens work)
- Test checkpoint restore + credential refresh
- Concurrent sandbox creation for same user (verify mutex)

### Security Tests

- Injection attempts in `repo_url`: `https://github.com/foo; rm -rf /`
- Injection attempts in `branch`: `main; echo pwned`
- Injection attempts in `user_id`: `admin$(whoami)`
- Verify credentials not logged
- Verify credentials not in checkpoint

### Manual Validation

- Create sandbox via API
- Verify Direct Connect works (browser → sprite URL with token)
- Restart boring-ui backend, verify tokens still work (secret rotation)
- Create checkpoint, restore, verify credentials still work

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shell injection | Critical | Input sanitization + argv execution |
| Secret rotation fails | Auth broken | Explicit error handling, health check after rotation |
| Checkpoint restores old secrets | Auth broken | Secrets outside workspace, auto-refresh on restore |
| Race condition in create | Partial setup | Per-sandbox mutex |
| Cross-tenant access | Security breach | Authorization callback, not just prefix |
| Sprite orphaning | Cost leak | Cleanup job with activity tracking |
| Sprites API unavailable | Create fails | Retry with backoff, graceful degradation |

---

## Out of Scope

- Router endpoints for checkpoint API (separate bead)
- Frontend UI for checkpoint management (separate bead)
- Sprite pre-warming / pooling (future optimization)
- Server-side credential storage (explicitly rejected)
- Multi-sandbox per user (1:1 mapping for V1, see Design Decisions)
- Circuit breaker pattern (future resilience improvement)

---

## Design Decisions

### 1:1 User-to-Sprite Mapping

**Decision**: Each user gets exactly one sprite.

**Rationale**:
- Simplifies identity model
- Prevents orphan accumulation
- Matches current UX (one workspace per user)

**Tradeoffs**:
- Blocks multi-repo workflows
- Blocks per-project isolation

**Migration path**: If needed, can expand to `sandbox_id = hash(user_id + project_id)` with cleanup job for old sprites.

### Secrets Outside Workspace

**Decision**: Store secrets in `/home/sprite/.auth/` not `/home/sprite/workspace/`.

**Rationale**:
- Checkpoints only capture workspace
- Prevents credential rollback via checkpoint restore
- Allows secret rotation without checkpoint

**Tradeoffs**:
- Extra complexity in setup scripts
- Need to document `.auth/` directory

---

## Answers to Review Questions

1. **How will browser reach sprite's sandbox-agent?**
   - Sprite URL is public HTTPS (e.g., `https://sb-a1b2c3.sprites.app`)
   - Sprites.dev routes to internal port 2468
   - No tunnel needed

2. **How will Direct Connect auth work?**
   - boring-ui issues HMAC token (same as local)
   - `SERVICE_AUTH_SECRET` provisioned to sprite via exec
   - sandbox-agent validates token using middleware
   - Secret rotated on backend restart via `ensure_running()`

3. **What sanitization for user_id?**
   - Hashed with SHA256 to derive sandbox_id
   - No direct interpolation of user_id into shell

4. **How is repo cloned?**
   - Using `exec_argv(['git', 'clone', '--branch', branch, url, 'workspace'])`
   - URL and branch validated first
   - No shell interpolation

5. **What is multi-tenant?**
   - Different customers in one boring-ui deployment
   - Prefix prevents collisions, authorization callback prevents access

6. **Lifecycle of sprite?**
   - Persists until cleanup job deletes (N days inactive)
   - Activity tracked via metadata on each operation

7. **Checkpoint scope?**
   - Secrets NOT in checkpoint (stored in `.auth/`)
   - Credentials auto-refreshed on restore (provider invariant)

---

## Review Feedback Addressed

| Issue | Resolution |
|-------|------------|
| P0: Direct Connect not specified | Added full section with architecture diagram |
| P0: Token signing key rotation | `ensure_running()` provisions fresh secret |
| P0: sandbox_id vs user_id | Derive sandbox_id from user_id hash |
| P0: Shell injection too narrow | Input sanitization + argv execution |
| P0: Credentials in checkpoints | Secrets in `.auth/` (outside workspace) |
| P0: Multi-tenant isolation weak | Authorization callback + prefix |
| P1: Checkpoint API ambiguity | `CheckpointResult[T]` structured type |
| P1: SandboxCreateConfig incomplete | Added all needed fields |
| P1: Error taxonomy incomplete | Full error hierarchy |
| P1: Retry needs jitter | Added jitter + 429/Retry-After |
| P1: Race conditions | Per-sandbox mutex |
| P1: 1:1 mapping tradeoffs | Documented with migration path |
| P1: Observability deferred | Added Story 6 with baseline metrics |
| P1: Cleanup depends on missing data | Activity tracking via metadata |
| P2: Status enum mapping | Added SPRITES_STATUS_MAP |
| P2: SandboxInfo missing fields | Added protocol field |
| P2: exec(cmd: str) unsafe | Changed to exec_argv(list[str]) |

---

*Created: 2026-02-10*
*Updated: 2026-02-10 (incorporated code review feedback)*
*Updated: 2026-02-10 (addressed Codex architecture review)*
*Source: POC at ~/projects/boring-agent-sandbox/poc-sprites/*
