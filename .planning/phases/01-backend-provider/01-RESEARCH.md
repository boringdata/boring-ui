# Phase 1: Backend Provider Abstraction - Research

**Researched:** 2026-02-09
**Domain:** Python subprocess management, FastAPI lifecycle, and provider abstraction patterns
**Confidence:** HIGH

## Summary

This phase creates a SandboxProvider abstract interface and LocalProvider implementation for managing sandbox-agent subprocess lifecycle. The research confirms that Python 3.13's asyncio subprocess API provides robust primitives for process management, FastAPI's lifespan pattern enables proper startup/shutdown orchestration, and the existing codebase patterns (from PTY module) offer excellent architectural guidance.

The LocalProvider will manage sandbox-agent as a long-running subprocess with health checking, log capture, and automatic crash recovery. Key challenges include coordinating async subprocess I/O with FastAPI's event loop, implementing reliable health polling with timeout handling, and managing process termination with graceful-then-forceful escalation.

**Primary recommendation:** Use Python's native asyncio.create_subprocess_exec (not shell) with stdout=PIPE/stderr=STDOUT for merged log capture, httpx.AsyncClient for health checks (FastAPI-native HTTP client), collections.deque(maxlen=1000) for ring buffer, and simple Enum-based state tracking without external FSM libraries. Follow the existing PTY module patterns for service structure and testing approach.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Process spawning:**
- Invoke sandbox-agent via **direct binary path**, not npx
- Binary path from **SANDBOX_AGENT_BIN** environment variable (with sensible default like `sandbox-agent`)
- If binary not found at startup: **fail fast with clear error** — app won't start
- Working directory from **SANDBOX_WORKSPACE** env var, default to cwd

**Lifecycle management:**
- Startup timeout: **30 seconds** to become healthy
- Crash recovery: **auto-restart with exponential backoff** (1s, 2s, 4s, max 3 attempts)
- Startup timing: **eager at app startup** — sandbox-agent starts when boring-ui starts
- Shutdown: **SIGTERM then SIGKILL after 5 seconds** — standard graceful pattern

**Log handling:**
- Ring buffer size: **1000 lines**
- Capture: **stdout + stderr merged** into single stream
- Timestamps: **add ISO timestamp prefix** on capture
- Persistence: Claude's discretion (likely in-memory only for v1)

**Health checking:**
- Startup polling: **500ms interval** until healthy or timeout
- Ongoing monitoring: **yes, periodic checks** every 10 seconds
- Failure threshold: **3 consecutive failures** before marking unhealthy and triggering restart

### Claude's Discretion

- Log persistence (in-memory vs file) — lean toward in-memory for simplicity
- Exact backoff timing implementation
- Health check HTTP client configuration (timeouts, retries)
- Internal state machine for sandbox lifecycle states

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib (Python 3.13+) | Async subprocess management | Built-in, battle-tested, no external deps. Official subprocess API. |
| httpx | ^0.27.0 | Async HTTP health checks | FastAPI ecosystem standard, supports sync/async, modern HTTP/2 |
| collections.deque | stdlib | Ring buffer for logs | Built-in, thread-safe operations, maxlen parameter auto-discards old items |
| abc | stdlib | Abstract base classes | Python standard for defining interfaces/protocols |
| pathlib.Path | stdlib | File path handling | Modern, cross-platform path operations |
| datetime | stdlib | Timestamps for logs | Timezone-aware datetime with UTC support |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| enum.Enum | stdlib | Process state enumeration | Type-safe state definitions (STARTING, RUNNING, STOPPED, etc.) |
| dataclasses | stdlib | Service/provider classes | Clean class definitions with default values |
| typing | stdlib | Type annotations | FastAPI dependency injection, mypy validation |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | aiohttp | aiohttp has better raw performance for high-concurrency, but httpx is FastAPI-native, simpler API, supports sync/async. For health checks (low frequency), httpx wins. |
| deque | ringbuf or custom | External ring buffer libs add dependency for minimal gain. deque with maxlen is stdlib, thread-safe for append/pop. |
| asyncio subprocess | ptyprocess | ptyprocess is for PTY sessions (interactive terminals). sandbox-agent is HTTP server, needs stdout/stderr capture not terminal emulation. |
| Simple Enum | python-statemachine or transitions | FSM libraries add complexity. This phase has simple state tracking (4-5 states, straightforward transitions). Enum + explicit state checks is clearer. |

**Installation:**

```bash
# Core dependencies (add to pyproject.toml)
pip install "httpx>=0.27.0"

# Already in project
# - fastapi>=0.100.0
# - uvicorn[standard]>=0.23.0
```

## Architecture Patterns

### Recommended Project Structure

```
src/back/boring_ui/api/modules/sandbox/
├── __init__.py              # Package exports
├── provider.py              # Abstract SandboxProvider interface
├── manager.py               # SandboxManager orchestration
├── providers/
│   ├── __init__.py          # Provider exports
│   ├── local.py             # LocalProvider implementation
│   └── modal.py             # ModalProvider stub (future)
└── schemas.py               # Pydantic models (optional, for API responses)
```

**Why this structure:**
- Mirrors existing `modules/pty/`, `modules/files/`, `modules/git/` patterns
- Separates interface (provider.py) from implementations (providers/)
- Manager orchestrates provider lifecycle, routers call manager
- Providers directory allows multiple backends (local, modal, docker, k8s)

### Pattern 1: Abstract Provider Interface

**What:** Define SandboxProvider as ABC with required methods for lifecycle management.

**When to use:** When you need multiple implementations of the same interface (local subprocess, modal, docker, etc.).

**Example:**

```python
# Source: Python ABC documentation + existing codebase patterns
from abc import ABC, abstractmethod
from typing import AsyncIterator
from datetime import datetime

class SandboxProvider(ABC):
    """Abstract interface for sandbox execution providers."""

    @abstractmethod
    async def start(self) -> None:
        """Start the sandbox process/service.

        Should block until healthy or raise on startup failure.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the sandbox gracefully, with timeout escalation."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if sandbox is healthy.

        Returns:
            True if healthy, False otherwise
        """
        ...

    @abstractmethod
    async def get_logs(self, tail: int = 100) -> list[str]:
        """Get recent log lines.

        Args:
            tail: Number of recent lines to return

        Returns:
            List of log lines with timestamps
        """
        ...

    @abstractmethod
    async def stream_logs(self) -> AsyncIterator[str]:
        """Stream logs in real-time.

        Yields:
            Log lines as they're produced
        """
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Get the sandbox base URL for API calls."""
        ...

    @property
    @abstractmethod
    def status(self) -> str:
        """Get current sandbox status (starting, running, stopped, failed)."""
        ...
```

### Pattern 2: Subprocess with Merged Output Capture

**What:** Use asyncio.create_subprocess_exec with stdout=PIPE, stderr=STDOUT to merge streams.

**When to use:** When you need single log stream from subprocess (not interactive terminal).

**Example:**

```python
# Source: Python asyncio subprocess docs (https://docs.python.org/3/library/asyncio-subprocess.html)
import asyncio
from collections import deque
from datetime import datetime, timezone

async def spawn_process(command: list[str], cwd: str):
    """Spawn subprocess with merged output capture."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
        env=None,  # Inherit parent environment
    )

    # Ring buffer for log history
    log_buffer = deque(maxlen=1000)

    # Read output in background
    async def read_output():
        while True:
            line_bytes = await process.stdout.readline()
            if not line_bytes:
                break

            # Decode and timestamp
            line = line_bytes.decode('utf-8', errors='replace').rstrip()
            timestamp = datetime.now(timezone.utc).isoformat()
            log_line = f"{timestamp} | {line}"

            log_buffer.append(log_line)

    # Start reading task
    read_task = asyncio.create_task(read_output())

    return process, read_task, log_buffer
```

### Pattern 3: Graceful Shutdown with Timeout Escalation

**What:** Send SIGTERM, wait with timeout, escalate to SIGKILL if needed.

**When to use:** Stopping any subprocess that should clean up resources gracefully.

**Example:**

```python
# Source: Python subprocess best practices + research on graceful shutdown patterns
import asyncio
import signal

async def stop_process_gracefully(process, timeout: float = 5.0):
    """Stop process with SIGTERM, escalate to SIGKILL after timeout.

    Args:
        process: asyncio.subprocess.Process instance
        timeout: Seconds to wait for graceful shutdown
    """
    if process.returncode is not None:
        # Already terminated
        return

    try:
        # Send SIGTERM for graceful shutdown
        process.terminate()

        # Wait with timeout
        await asyncio.wait_for(process.wait(), timeout=timeout)

    except asyncio.TimeoutError:
        # Process didn't exit gracefully, force kill
        process.kill()
        await process.wait()  # Clean up zombie
```

### Pattern 4: FastAPI Lifespan for Eager Startup

**What:** Use @asynccontextmanager lifespan to start sandbox-agent when app starts.

**When to use:** When subprocess/service needs to be ready before first request.

**Example:**

```python
# Source: FastAPI lifespan documentation (https://fastapi.tiangolo.com/advanced/events/)
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize sandbox provider
    manager = SandboxManager()
    await manager.start()  # Blocks until healthy or timeout

    # Store in app state for route access
    app.state.sandbox_manager = manager

    yield  # App handles requests here

    # Shutdown: Clean up sandbox
    await manager.stop()

app = FastAPI(lifespan=lifespan)

# Access in routes via request.app.state
@app.get('/sandbox/status')
async def get_status(request: Request):
    manager = request.app.state.sandbox_manager
    return await manager.get_info()
```

### Pattern 5: Health Check Polling with Backoff

**What:** Poll health endpoint with exponential backoff on startup, fixed interval for monitoring.

**When to use:** Waiting for service to become healthy after start, ongoing health monitoring.

**Example:**

```python
# Source: Research on health check patterns + backoff strategies
import asyncio
import httpx
from typing import Optional

async def wait_for_healthy(
    base_url: str,
    timeout: float = 30.0,
    interval: float = 0.5,
) -> bool:
    """Poll health endpoint until healthy or timeout.

    Args:
        base_url: Base URL of service
        timeout: Max seconds to wait
        interval: Polling interval in seconds

    Returns:
        True if became healthy, False on timeout
    """
    deadline = asyncio.get_event_loop().time() + timeout

    async with httpx.AsyncClient(timeout=2.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                response = await client.get(f"{base_url}/v1/health")
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass  # Service not ready yet

            await asyncio.sleep(interval)

    return False  # Timeout

async def monitor_health(
    base_url: str,
    interval: float = 10.0,
    failure_callback = None,
):
    """Monitor health with periodic checks.

    Calls failure_callback after 3 consecutive failures.
    """
    consecutive_failures = 0

    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            await asyncio.sleep(interval)

            try:
                response = await client.get(f"{base_url}/v1/health")
                if response.status_code == 200:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception:
                consecutive_failures += 1

            if consecutive_failures >= 3 and failure_callback:
                await failure_callback()
                consecutive_failures = 0  # Reset after triggering
```

### Pattern 6: Exponential Backoff for Crash Recovery

**What:** Retry failed starts with increasing delays (1s, 2s, 4s), max attempts limit.

**When to use:** Auto-restarting crashed processes without restart storms.

**Example:**

```python
# Source: Research on exponential backoff patterns
async def start_with_retry(
    start_func,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> bool:
    """Start with exponential backoff retry.

    Args:
        start_func: Async function to call for start
        max_attempts: Max retry attempts
        base_delay: Base delay in seconds (doubles each attempt)

    Returns:
        True if started successfully, False if all attempts failed
    """
    for attempt in range(max_attempts):
        try:
            await start_func()
            return True
        except Exception as e:
            if attempt == max_attempts - 1:
                # Final attempt failed
                raise

            # Exponential backoff: 1s, 2s, 4s
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)

    return False
```

### Pattern 7: Service Layer with Dependency Injection

**What:** Manager class orchestrates provider, exposes to FastAPI via dependency injection.

**When to use:** Decoupling provider lifecycle from routes, enabling testing.

**Example:**

```python
# Source: Existing boring-ui patterns (PTYService, FileService)
from dataclasses import dataclass
from typing import Optional

@dataclass
class SandboxManager:
    """Manages sandbox provider lifecycle."""

    provider: Optional[SandboxProvider] = None
    _monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the sandbox provider.

        Raises:
            RuntimeError: If provider fails to start
        """
        if self.provider and self.provider.status == 'running':
            return  # Already running

        # Create provider
        self.provider = LocalProvider()

        # Start with retry
        await start_with_retry(self.provider.start)

        # Start health monitoring
        self._monitor_task = asyncio.create_task(
            self._monitor_health()
        )

    async def stop(self):
        """Stop the sandbox provider."""
        if self._monitor_task:
            self._monitor_task.cancel()

        if self.provider:
            await self.provider.stop()

    async def _monitor_health(self):
        """Background health monitoring."""
        async def on_failure():
            # Restart provider
            await self.provider.stop()
            await start_with_retry(self.provider.start)

        await monitor_health(
            self.provider.base_url,
            failure_callback=on_failure,
        )

    async def get_info(self) -> dict:
        """Get sandbox status info."""
        if not self.provider:
            return {'status': 'not_started'}

        return {
            'status': self.provider.status,
            'base_url': self.provider.base_url,
            'healthy': await self.provider.health_check(),
        }
```

### Anti-Patterns to Avoid

- **Subprocess.Popen instead of asyncio:** Popen is sync, blocks event loop. Use asyncio.create_subprocess_exec.
- **Shell=True with user input:** Shell injection risk. Use shell=False (default) with command list.
- **Global process state without locks:** Race conditions. Use asyncio.Lock for state mutations.
- **Ignoring process exit codes:** Negative returncode means killed by signal. Check and log.
- **Communicate() without timeout:** Can deadlock with large output. Use asyncio.wait_for wrapper.
- **Capturing stdout/stderr separately:** Requires careful coordination. Merge with stderr=STDOUT.
- **Polling in tight loop:** Wastes CPU. Use await asyncio.sleep(interval) between checks.
- **No cleanup on shutdown:** Zombie processes leak resources. Always await process.wait() after kill.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client | Custom socket/request code | httpx.AsyncClient | SSL/TLS, redirects, connection pooling, timeout handling, HTTP/2. |
| Ring buffer | List with manual size management | collections.deque(maxlen=N) | Efficient, thread-safe for single-producer, auto-discards old. stdlib. |
| Process cleanup | Custom signal handlers | process.terminate() + process.kill() | Platform abstraction (SIGTERM/TerminateProcess), proper zombie cleanup. |
| State machine library | transitions, python-statemachine | Simple Enum + explicit checks | This phase has 4-5 states with straightforward transitions. FSM lib is overkill. |
| Event loop management | Threading or manual event loop | FastAPI's asyncio integration | FastAPI runs on uvicorn/asyncio event loop. Use native async/await. |
| Log rotation | Manual file management | In-memory deque (v1) | Simpler, no disk I/O, no rotation logic. If persistence needed later, use stdlib logging.handlers.RotatingFileHandler. |

**Key insight:** Python stdlib provides excellent subprocess, HTTP (via httpx), and data structure primitives. External libs add complexity without benefit for this use case. Focus on solid asyncio patterns.

## Common Pitfalls

### Pitfall 1: Deadlock with communicate() on Large Output

**What goes wrong:** Calling `process.communicate()` without timeout can hang if subprocess produces more output than OS buffer can hold.

**Why it happens:** communicate() reads all output into memory. If subprocess writes continuously, stdout pipe buffer fills, subprocess blocks on write, communicate() blocks on read.

**How to avoid:**
- Use `asyncio.wait_for(process.communicate(), timeout=30)` to enforce timeout
- For long-running processes, read output incrementally with `stdout.readline()` in background task
- For this phase: Use readline() pattern since sandbox-agent runs continuously

**Warning signs:**
- Process hangs during startup
- High memory usage (output accumulating)
- No response from process.wait()

### Pitfall 2: Process Exits Immediately (Binary Not Found)

**What goes wrong:** Subprocess spawns but exits with code 127 or raises FileNotFoundError.

**Why it happens:**
- Binary path is wrong or not in PATH
- Binary doesn't have execute permissions
- Working directory doesn't exist

**How to avoid:**
- **Validate binary exists before spawning:** `shutil.which(binary_path)` or `Path(binary_path).exists()`
- **Fail fast at app startup** (user decision): Check in lifespan startup, raise clear error
- Log full command + cwd for debugging: `logger.error(f"Failed to spawn {command} in {cwd}")`

**Warning signs:**
- Process exits immediately with returncode 127 (command not found)
- FileNotFoundError or PermissionError on spawn
- Empty output, process.returncode is not None right after spawn

### Pitfall 3: Health Check False Negatives

**What goes wrong:** Service is healthy but health check fails, causing unnecessary restarts.

**Why it happens:**
- Timeout too short (service slow to respond)
- Network/DNS issues (unlikely for localhost)
- Health endpoint not fully implemented (returns 500)
- Race condition (checked before service bound to port)

**How to avoid:**
- Use reasonable timeouts: 2s for health checks (not 200ms)
- Retry logic: 3 consecutive failures before marking unhealthy
- Log health check failures with details: status code, error message
- Wait for port binding: Small delay (100ms) after spawn before first check

**Warning signs:**
- Frequent restarts in logs
- Health checks timing out consistently
- Service works manually (curl succeeds) but code reports unhealthy

### Pitfall 4: Zombie Processes

**What goes wrong:** Process.kill() called but process becomes zombie (defunct), leaks PID.

**Why it happens:** Parent process doesn't call wait() after kill, so OS keeps entry in process table.

**How to avoid:**
- **Always await process.wait() after kill:** Even if killed forcefully
- In cleanup: `process.kill(); await process.wait()`
- Handle exceptions: Try/except around wait() in case process already reaped

**Warning signs:**
- `ps aux | grep defunct` shows zombie processes
- PID count increases over time
- Process exists but can't interact with it

### Pitfall 5: Startup Race Conditions

**What goes wrong:** Health check runs before sandbox-agent binds to port, reports unhealthy, triggers restart.

**Why it happens:** Process spawn is async, health check starts immediately. Port binding takes time.

**How to avoid:**
- Small initial delay (100-200ms) before first health check
- Ignore initial connection errors (expected during startup)
- Log first successful health check: "Sandbox became healthy in Xs"

**Warning signs:**
- First health check always fails
- Works on second attempt
- Logs show "connection refused" immediately after spawn

### Pitfall 6: Environment Variable Leakage

**What goes wrong:** Subprocess inherits sensitive env vars from parent, logs them, or exposes via API.

**Why it happens:** asyncio.create_subprocess_exec uses os.environ by default. Parent may have tokens, API keys.

**How to avoid:**
- **Pass explicit env dict:** Don't rely on inheritance
- Filter sensitive vars: Remove ANTHROPIC_API_KEY, tokens before passing
- For this phase: Inherit environment but be aware in logs

**Warning signs:**
- Secrets appear in subprocess logs
- Unintended API calls from subprocess
- Security audit failures

### Pitfall 7: Log Buffer Memory Growth

**What goes wrong:** deque maxlen not set, log buffer grows unbounded, memory leak.

**Why it happens:** If maxlen is None, deque grows indefinitely. Continuous log output fills memory.

**How to avoid:**
- **Always set maxlen:** `deque(maxlen=1000)` (user decision)
- Monitor memory usage: Log buffer size in get_info()
- For very verbose processes: Lower maxlen or implement log levels

**Warning signs:**
- Memory usage grows over time
- OOM errors after days of uptime
- deque contains millions of entries

## Code Examples

### Example 1: LocalProvider Skeleton

```python
# Source: Synthesized from research + existing codebase patterns
import asyncio
import os
import shutil
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx


class SandboxState(Enum):
    """Sandbox lifecycle states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    FAILED = "failed"


class SandboxProvider(ABC):
    """Abstract interface for sandbox providers."""

    @abstractmethod
    async def start(self) -> None:
        """Start the sandbox, wait until healthy."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the sandbox gracefully."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if sandbox is healthy."""
        ...

    @abstractmethod
    async def get_logs(self, tail: int = 100) -> list[str]:
        """Get recent log lines."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Get the sandbox base URL."""
        ...

    @property
    @abstractmethod
    def status(self) -> SandboxState:
        """Get current status."""
        ...


class LocalProvider(SandboxProvider):
    """Local subprocess-based sandbox provider."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        workspace: Optional[Path] = None,
        host: str = "127.0.0.1",
        port: int = 2468,
    ):
        # Configuration from env vars with defaults
        self.binary_path = binary_path or os.environ.get(
            'SANDBOX_AGENT_BIN',
            'sandbox-agent'
        )
        self.workspace = workspace or Path(
            os.environ.get('SANDBOX_WORKSPACE', Path.cwd())
        )
        self.host = host
        self.port = port

        # State
        self._state = SandboxState.STOPPED
        self._process: Optional[asyncio.subprocess.Process] = None
        self._read_task: Optional[asyncio.Task] = None
        self._logs = deque(maxlen=1000)
        self._logs_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def status(self) -> SandboxState:
        return self._state

    async def start(self) -> None:
        """Start sandbox-agent subprocess."""
        if self._state in (SandboxState.STARTING, SandboxState.RUNNING):
            return  # Already started

        # Validate binary exists (fail fast)
        resolved = shutil.which(self.binary_path)
        if not resolved:
            raise FileNotFoundError(
                f"sandbox-agent binary not found: {self.binary_path}. "
                f"Set SANDBOX_AGENT_BIN environment variable."
            )

        self._state = SandboxState.STARTING

        # Spawn subprocess
        command = [
            resolved, "server",
            "--host", self.host,
            "--port", str(self.port),
            "--no-token",  # Local development
        ]

        self._process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # Merge stderr
        )

        # Start log reading task
        self._read_task = asyncio.create_task(self._read_output())

        # Wait for healthy (30 second timeout)
        healthy = await self._wait_for_healthy(timeout=30.0)
        if not healthy:
            await self.stop()
            self._state = SandboxState.FAILED
            raise TimeoutError(
                f"Sandbox failed to become healthy within 30s"
            )

        self._state = SandboxState.RUNNING

    async def stop(self) -> None:
        """Stop sandbox gracefully."""
        if self._state == SandboxState.STOPPED:
            return

        self._state = SandboxState.STOPPING

        # Cancel log reading
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # Graceful shutdown with escalation
        if self._process and self._process.returncode is None:
            try:
                # SIGTERM
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # SIGKILL
                self._process.kill()
                await self._process.wait()

        self._state = SandboxState.STOPPED

    async def health_check(self) -> bool:
        """Check if sandbox is healthy."""
        if self._state != SandboxState.RUNNING:
            return False

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Note: Actual endpoint TBD, assuming /v1/health based on research
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def get_logs(self, tail: int = 100) -> list[str]:
        """Get recent log lines."""
        async with self._logs_lock:
            # Return last N lines
            return list(self._logs)[-tail:]

    async def stream_logs(self) -> AsyncIterator[str]:
        """Stream logs in real-time."""
        # Simple implementation: yield from buffer
        # Production version would use asyncio.Queue for new lines
        async with self._logs_lock:
            for line in self._logs:
                yield line

    async def _read_output(self):
        """Background task to read and buffer subprocess output."""
        while self._process and self._process.returncode is None:
            try:
                line_bytes = await self._process.stdout.readline()
                if not line_bytes:
                    break

                # Decode and timestamp
                line = line_bytes.decode('utf-8', errors='replace').rstrip()
                timestamp = datetime.now(timezone.utc).isoformat()
                log_line = f"{timestamp} | {line}"

                async with self._logs_lock:
                    self._logs.append(log_line)

            except Exception:
                break

    async def _wait_for_healthy(self, timeout: float = 30.0) -> bool:
        """Poll health endpoint until healthy or timeout."""
        deadline = asyncio.get_event_loop().time() + timeout

        # Small initial delay for port binding
        await asyncio.sleep(0.2)

        async with httpx.AsyncClient(timeout=2.0) as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    response = await client.get(f"{self.base_url}/health")
                    if response.status_code == 200:
                        return True
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass  # Not ready yet

                await asyncio.sleep(0.5)  # 500ms polling interval

        return False
```

### Example 2: SandboxManager with Crash Recovery

```python
# Source: Synthesized from patterns + user requirements
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SandboxManager:
    """Manages sandbox provider with crash recovery."""

    provider: Optional[LocalProvider] = None
    _monitor_task: Optional[asyncio.Task] = None
    _restart_attempts: int = 0
    _max_restart_attempts: int = 3

    async def start(self):
        """Start sandbox with exponential backoff retry."""
        if self.provider and self.provider.status == SandboxState.RUNNING:
            return

        # Try up to 3 times with exponential backoff
        for attempt in range(self._max_restart_attempts):
            try:
                self.provider = LocalProvider()
                await self.provider.start()

                # Success, start monitoring
                self._monitor_task = asyncio.create_task(self._monitor_health())
                return

            except Exception as e:
                if attempt == self._max_restart_attempts - 1:
                    raise RuntimeError(
                        f"Failed to start sandbox after {self._max_restart_attempts} attempts"
                    ) from e

                # Exponential backoff: 1s, 2s, 4s
                delay = 1.0 * (2 ** attempt)
                await asyncio.sleep(delay)

    async def stop(self):
        """Stop sandbox and monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self.provider:
            await self.provider.stop()

    async def _monitor_health(self):
        """Background health monitoring with auto-restart."""
        consecutive_failures = 0

        while True:
            await asyncio.sleep(10.0)  # Check every 10 seconds

            healthy = await self.provider.health_check()

            if healthy:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

                if consecutive_failures >= 3:
                    # Restart provider
                    await self.provider.stop()
                    self.provider._state = SandboxState.UNHEALTHY

                    # Retry with backoff
                    for attempt in range(self._max_restart_attempts):
                        try:
                            await self.provider.start()
                            break
                        except Exception:
                            if attempt < self._max_restart_attempts - 1:
                                delay = 1.0 * (2 ** attempt)
                                await asyncio.sleep(delay)
                            else:
                                # All attempts failed
                                self.provider._state = SandboxState.FAILED

                    consecutive_failures = 0

    async def get_info(self) -> dict:
        """Get sandbox status info."""
        if not self.provider:
            return {'status': 'not_started'}

        return {
            'status': self.provider.status.value,
            'base_url': self.provider.base_url,
            'healthy': await self.provider.health_check(),
            'restart_attempts': self._restart_attempts,
        }
```

### Example 3: FastAPI Integration

```python
# Source: FastAPI lifespan patterns + existing app.py structure
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize and start sandbox
    manager = SandboxManager()
    await manager.start()  # Blocks until healthy or raises

    app.state.sandbox_manager = manager

    yield  # App handles requests

    # Shutdown: Stop sandbox gracefully
    await manager.stop()

app = FastAPI(lifespan=lifespan)

@app.get('/api/sandbox/status')
async def get_sandbox_status(request: Request):
    """Get sandbox provider status."""
    manager = request.app.state.sandbox_manager
    return await manager.get_info()

@app.get('/api/sandbox/logs')
async def get_sandbox_logs(request: Request, tail: int = 100):
    """Get recent sandbox logs."""
    manager = request.app.state.sandbox_manager
    if not manager.provider:
        return {'logs': []}

    logs = await manager.provider.get_logs(tail=tail)
    return {'logs': logs}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| subprocess.Popen sync | asyncio.create_subprocess_exec | Python 3.4+ (2014) | Non-blocking subprocess management, proper asyncio integration |
| @app.on_event decorators | lifespan context manager | FastAPI 0.93+ (2023) | Cleaner startup/shutdown logic, natural state sharing, unified API |
| requests library | httpx | 2020+ | Native async support, HTTP/2, same API for sync/async |
| Manual state tracking | Enum-based states | Always available but increasingly preferred | Type safety, IDE autocomplete, clearer intent |
| threading + Queue | asyncio + deque | Python 3.4+ asyncio maturity | Single-threaded concurrency, simpler mental model |
| Shell commands (shell=True) | Direct exec (shell=False) | Security best practice evolution | Avoids shell injection, explicit args |

**Deprecated/outdated:**
- **subprocess.Popen without asyncio:** Still works but blocks event loop in async apps. Use asyncio.create_subprocess_exec.
- **@app.on_event("startup/shutdown"):** FastAPI still supports but lifespan is the modern pattern (cleaner, more powerful).
- **aiohttp for FastAPI projects:** httpx is now the ecosystem standard (Starlette/FastAPI maintainer preference).
- **poll() method on subprocess:** Not available in asyncio subprocess. Use await process.wait() or check returncode.

## Open Questions

1. **Sandbox-agent health endpoint path**
   - What we know: sandbox-agent runs HTTP server on configurable port, has OpenAPI spec
   - What's unclear: Exact health endpoint path (/health, /v1/health, /api/health?)
   - Recommendation: Implement with configurable health_path parameter (default "/health"), test with actual sandbox-agent binary during phase execution, update if needed

2. **Sandbox-agent stdout verbosity**
   - What we know: It's a server process, likely logs startup/requests
   - What's unclear: Log volume, log levels, structured logging format
   - Recommendation: Start with 1000 line buffer (user decision), monitor in testing, adjust maxlen if needed. Consider adding log level filtering if very verbose.

3. **Process group handling for cleanup**
   - What we know: sandbox-agent may spawn child processes (agent subprocesses)
   - What's unclear: Does it create process group? Do children get cleaned up on SIGTERM?
   - Recommendation: Test kill behavior. If zombies persist, consider process group kill (os.killpg). Document cleanup behavior.

4. **Modal provider architecture**
   - What we know: Need stub for future phase
   - What's unclear: Will Modal provider manage HTTP endpoint or subprocess? Different base_url pattern?
   - Recommendation: Keep interface generic (base_url property), Modal stub just raises NotImplementedError, defer implementation details to Modal phase.

## Sources

### Primary (HIGH confidence)

- [Python asyncio subprocess documentation](https://docs.python.org/3/library/asyncio-subprocess.html) - Official API reference for asyncio.create_subprocess_exec, Process methods
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Official documentation on lifespan context manager pattern
- [Python ABC module documentation](https://docs.python.org/3/library/abc.html) - Abstract base class patterns
- [Python collections.deque documentation](https://docs.python.org/3/library/collections.html#collections.deque) - Ring buffer implementation details
- Existing codebase patterns (PTYService, FileService, modules structure) - HIGH confidence for architectural consistency

### Secondary (MEDIUM confidence)

- [HTTPX vs aiohttp comparison (2026)](https://dev.to/piyushatghara/fastapi-vs-aiohttp-vs-httpx-a-comparative-guide-3kib) - Ecosystem recommendations
- [FastAPI HTTPX client best practices](https://medium.com/@benshearlaw/how-to-use-httpx-request-client-with-fastapi-16255a9984a4) - AsyncClient usage patterns
- [Python subprocess SIGTERM/SIGKILL patterns](https://pypi.org/project/graceful-shutdown/) - Graceful shutdown strategies
- [Python-StateMachine documentation](https://python-statemachine.readthedocs.io/) - FSM patterns (evaluated but not recommended for this phase)
- [Rivet sandbox-agent repository](https://github.com/rivet-dev/sandbox-agent) - Architecture understanding (health endpoint specifics unclear)

### Tertiary (LOW confidence)

- [Exponential backoff patterns (backoff library)](https://pypi.org/project/backoff/) - Considered but not using library
- [Ring buffer implementations comparison](https://medium.com/@tihomir.manushev/ring-buffers-in-python-3-06266efaaba6) - Confirmed deque is best choice
- Various StackOverflow/Medium articles on subprocess management - General validation of approaches

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using stdlib + httpx (FastAPI standard), verified with multiple sources
- Architecture patterns: HIGH - Synthesized from official docs + existing codebase patterns + verified best practices
- Pitfalls: MEDIUM-HIGH - Based on documentation, common issues in research, and async subprocess gotchas
- Code examples: HIGH - Synthesized from official docs, tested patterns, and existing codebase style

**Research date:** 2026-02-09
**Valid until:** ~30 days (Python stdlib stable, FastAPI patterns stable, sandbox-agent may evolve but interface is abstracted)

**Key assumptions:**
- sandbox-agent binary will be available (user installs separately)
- Health endpoint exists (path may need adjustment in testing)
- Python 3.10+ environment (asyncio features, type hints)
- FastAPI 0.100+ (lifespan parameter support)

**Phase 1 scope boundaries (confirmed):**
- ✅ Provider abstraction and LocalProvider implementation
- ✅ Subprocess lifecycle management
- ✅ Health checking and log capture
- ✅ SandboxManager orchestration
- ❌ API routes (Phase 2)
- ❌ Frontend integration (Phase 3)
- ❌ Modal provider implementation (future phase)
