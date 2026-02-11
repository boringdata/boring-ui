# Plan: Add sandbox-agent Chat to boring-ui

## Overview
Add sandbox-agent as an alternative chat option in boring-ui with a **generic provider abstraction** that supports:
- **Local**: subprocess on host (implement now)
- **Remote**: Modal/E2B sandbox with tmp filesystem (future)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    boring-ui backend (FastAPI)                       │
│                                                                     │
│  ┌────────────────────┐     ┌──────────────────────────────────┐   │
│  │  Existing routers  │     │  sandbox module (new)            │   │
│  │  /api/files        │     │                                  │   │
│  │  /api/git          │     │  SandboxManager                  │   │
│  │  /ws/claude-stream │     │       │                          │   │
│  └────────────────────┘     │       ▼                          │   │
│                             │  SandboxProvider (interface)     │   │
│                             │       │                          │   │
│                             │  ┌────┴────┐                     │   │
│                             │  │         │                     │   │
│                             │  ▼         ▼                     │   │
│                             │ Local    Modal (future)          │   │
│                             └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │ (local)                 │                         │ (future)
              ▼                         │                         ▼
┌──────────────────────────┐            │           ┌──────────────────────────┐
│ sandbox-agent subprocess │            │           │ Modal Sandbox            │
│ http://127.0.0.1:2468    │            │           │ - tmp filesystem         │
│ workspace: current dir   │            │           │ - sandbox-agent :2468    │
└──────────────────────────┘            │           │ - isolated environment   │
                                        │           └──────────────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    boring-ui frontend (React)                        │
│                                                                     │
│  ┌─────────────────────┐        ┌─────────────────────────────────┐ │
│  │  ClaudeStreamChat   │        │  SandboxChatPanel               │ │
│  │  (existing)         │        │  (from Inspector UI)            │ │
│  └─────────────────────┘        └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Backend Module Structure

```
src/back/boring_ui/api/modules/sandbox/
├── __init__.py
├── router.py              # API routes (proxy + logs + status)
├── manager.py             # SandboxManager orchestrator
├── provider.py            # Abstract SandboxProvider interface
└── providers/
    ├── __init__.py
    ├── local.py           # Local subprocess (implement now)
    └── modal.py           # Modal sandbox (stub for future)
```

## Provider Interface

**provider.py:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class SandboxInfo:
    id: str
    base_url: str           # URL to reach sandbox-agent API
    status: str             # starting, running, stopped, error
    workspace_path: str     # Path to workspace inside sandbox
    provider: str           # "local" or "modal"

class SandboxProvider(ABC):
    """Abstract interface for sandbox providers.

    Implementations:
    - LocalProvider: subprocess on host machine
    - ModalProvider: remote sandbox on Modal with tmp filesystem (future)
    """

    @abstractmethod
    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        """Create and start a sandbox with sandbox-agent running."""
        pass

    @abstractmethod
    async def destroy(self, sandbox_id: str) -> None:
        """Stop and cleanup sandbox."""
        pass

    @abstractmethod
    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get sandbox status and URL."""
        pass

    @abstractmethod
    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        """Get sandbox-agent logs."""
        pass

    @abstractmethod
    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        """Async generator yielding log lines."""
        pass

    @abstractmethod
    async def health_check(self, sandbox_id: str) -> bool:
        """Check if sandbox-agent is responding."""
        pass
```

## Local Provider (implement now)

**providers/local.py:**
```python
import subprocess
import asyncio
from pathlib import Path
import httpx

@dataclass
class LocalSandbox:
    id: str
    process: subprocess.Popen
    port: int
    logs: list[str]
    workspace: Path

class LocalProvider(SandboxProvider):
    """Runs sandbox-agent as local subprocess."""

    def __init__(self, port: int = 2468, workspace: Path | None = None):
        self.port = port
        self.workspace = workspace or Path.cwd()
        self.sandboxes: dict[str, LocalSandbox] = {}

    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        process = subprocess.Popen(
            ["npx", "@sandbox-agent/cli", "server",
             "--no-token", "--host", "127.0.0.1", "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(self.workspace)
        )

        sandbox = LocalSandbox(
            id=sandbox_id,
            process=process,
            port=self.port,
            logs=[],
            workspace=self.workspace
        )
        self.sandboxes[sandbox_id] = sandbox

        # Start log reader
        asyncio.create_task(self._read_logs(sandbox))

        # Wait for ready
        await self._wait_ready(sandbox)

        return SandboxInfo(
            id=sandbox_id,
            base_url=f"http://127.0.0.1:{self.port}",
            status="running",
            workspace_path=str(self.workspace),
            provider="local"
        )

    async def _read_logs(self, sandbox: LocalSandbox):
        loop = asyncio.get_event_loop()
        while sandbox.process.poll() is None:
            line = await loop.run_in_executor(
                None, sandbox.process.stdout.readline
            )
            if line:
                sandbox.logs.append(line.rstrip())
                if len(sandbox.logs) > 1000:
                    sandbox.logs.pop(0)

    async def _wait_ready(self, sandbox: LocalSandbox, timeout: int = 30):
        for _ in range(timeout * 2):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"http://127.0.0.1:{sandbox.port}/v1/health"
                    )
                    if r.status_code == 200:
                        return
            except:
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError("sandbox-agent failed to start")

    async def destroy(self, sandbox_id: str) -> None:
        sandbox = self.sandboxes.pop(sandbox_id, None)
        if sandbox and sandbox.process:
            sandbox.process.terminate()
            sandbox.process.wait(timeout=5)

    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return None
        status = "running" if sandbox.process.poll() is None else "stopped"
        return SandboxInfo(
            id=sandbox_id,
            base_url=f"http://127.0.0.1:{sandbox.port}",
            status=status,
            workspace_path=str(sandbox.workspace),
            provider="local"
        )

    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        sandbox = self.sandboxes.get(sandbox_id)
        return sandbox.logs[-limit:] if sandbox else []

    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return
        last_idx = len(sandbox.logs)
        while True:
            if len(sandbox.logs) > last_idx:
                for line in sandbox.logs[last_idx:]:
                    yield line
                last_idx = len(sandbox.logs)
            await asyncio.sleep(0.3)

    async def health_check(self, sandbox_id: str) -> bool:
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"http://127.0.0.1:{sandbox.port}/v1/health")
                return r.status_code == 200
        except:
            return False
```

## Modal Provider (stub for future)

**providers/modal.py:**
```python
class ModalProvider(SandboxProvider):
    """Runs sandbox-agent in Modal sandbox with isolated tmp filesystem.

    Future implementation will:
    - Create Modal sandbox with sandbox-agent pre-installed
    - Mount ephemeral tmp filesystem as /workspace
    - Start sandbox-agent server inside container
    - Return public URL to sandbox-agent
    - Auto-cleanup on timeout
    """

    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        # Future: modal.Sandbox.create(image="sandbox-agent")
        raise NotImplementedError("Modal provider coming soon")

    async def destroy(self, sandbox_id: str) -> None:
        raise NotImplementedError()

    # ... other methods stub
```

## Manager (orchestrator)

**manager.py:**
```python
class SandboxManager:
    """Manages sandbox lifecycle using configured provider."""

    def __init__(self, provider: SandboxProvider):
        self.provider = provider
        self.default_sandbox_id = "default"

    async def ensure_running(self) -> SandboxInfo:
        """Get or create the default sandbox."""
        info = await self.provider.get_info(self.default_sandbox_id)
        if info and info.status == "running":
            return info
        return await self.provider.create(self.default_sandbox_id, {})

    async def get_base_url(self) -> str:
        info = await self.ensure_running()
        return info.base_url

    async def get_logs(self, limit: int = 100) -> list[str]:
        return await self.provider.get_logs(self.default_sandbox_id, limit)

    async def stream_logs(self):
        async for line in self.provider.stream_logs(self.default_sandbox_id):
            yield line

    async def shutdown(self):
        await self.provider.destroy(self.default_sandbox_id)


def create_provider(config: dict) -> SandboxProvider:
    """Factory to create provider based on config."""
    provider_type = config.get("SANDBOX_PROVIDER", "local")

    if provider_type == "local":
        return LocalProvider(
            port=config.get("SANDBOX_PORT", 2468),
            workspace=Path(config.get("SANDBOX_WORKSPACE", "."))
        )
    elif provider_type == "modal":
        return ModalProvider()  # Future
    else:
        raise ValueError(f"Unknown provider: {provider_type}")
```

## Router

**router.py:**
```python
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter(prefix="/api/sandbox")

@router.get("/status")
async def get_status(manager: SandboxManager = Depends(get_manager)):
    """Get sandbox status."""
    info = await manager.provider.get_info(manager.default_sandbox_id)
    return info or {"status": "not_running"}

@router.get("/logs")
async def get_logs(
    limit: int = 100,
    manager: SandboxManager = Depends(get_manager)
):
    """Get sandbox-agent logs."""
    return {"logs": await manager.get_logs(limit)}

@router.get("/logs/stream")
async def stream_logs(manager: SandboxManager = Depends(get_manager)):
    """SSE stream of sandbox-agent logs."""
    async def generate():
        async for line in manager.stream_logs():
            yield f"data: {line}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(
    request: Request,
    path: str,
    manager: SandboxManager = Depends(get_manager)
):
    """Proxy requests to sandbox-agent."""
    base_url = await manager.get_base_url()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request(
            method=request.method,
            url=f"{base_url}/{path}",
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=await request.body()
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )
```

## Frontend

### Git Submodule
```bash
git submodule add https://github.com/nicholasgriffintn/sandbox-agent.git vendor/sandbox-agent
```

### Wrapper: `src/front/components/sandbox-chat/index.jsx`
```jsx
import { ChatPanel } from '../../../vendor/sandbox-agent/frontend/packages/inspector/src/components/ChatPanel'
import './overrides/theme.css'

export function SandboxChatPanel(props) {
  return <ChatPanel {...props} baseUrl="/api/sandbox" />
}
```

## Files to Create

**Backend:**
- `src/back/boring_ui/api/modules/sandbox/__init__.py`
- `src/back/boring_ui/api/modules/sandbox/provider.py`
- `src/back/boring_ui/api/modules/sandbox/manager.py`
- `src/back/boring_ui/api/modules/sandbox/router.py`
- `src/back/boring_ui/api/modules/sandbox/providers/__init__.py`
- `src/back/boring_ui/api/modules/sandbox/providers/local.py`
- `src/back/boring_ui/api/modules/sandbox/providers/modal.py` (stub)

**Frontend:**
- `src/front/components/sandbox-chat/index.jsx`
- `src/front/components/sandbox-chat/api.js`
- `src/front/components/sandbox-chat/overrides/theme.css`

## Files to Modify

- `src/back/boring_ui/api/app.py` - Add lifespan + router
- `pyproject.toml` - Add httpx dependency
- `src/front/vite.config.js` - Add vendor path
- Panel registration (dockview)

## Configuration

```bash
# Environment variables
SANDBOX_PROVIDER=local        # or "modal" (future)
SANDBOX_PORT=2468
SANDBOX_WORKSPACE=/path/to/workspace
```

## Phases

1. **Backend provider abstraction**: Create provider interface + LocalProvider
2. **Backend router**: Create manager + proxy router + log endpoints
3. **Frontend**: Add submodule, create wrapper, register panel
4. **Test**: End-to-end with mock agent

## Verification

1. `npm run dev` → sandbox-agent starts automatically
2. `curl http://localhost:8000/api/sandbox/status` → check provider info
3. `curl http://localhost:8000/api/sandbox/v1/health` → proxy works
4. `curl http://localhost:8000/api/sandbox/logs` → see subprocess logs
5. Open Sandbox Chat panel, send message with mock agent
