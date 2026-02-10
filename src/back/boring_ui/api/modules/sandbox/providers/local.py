"""Local subprocess provider for sandbox-agent.

Runs sandbox-agent as a local subprocess on the host machine.
"""
import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

import httpx

from ..provider import SandboxInfo, SandboxProvider


@dataclass
class LocalSandbox:
    """State for a local sandbox subprocess."""

    id: str
    process: subprocess.Popen | None
    port: int
    logs: list[str] = field(default_factory=list)
    workspace: Path = field(default_factory=Path.cwd)
    _log_task: asyncio.Task | None = field(default=None, repr=False)


class LocalProvider(SandboxProvider):
    """Runs sandbox-agent as local subprocess.

    This provider:
    - Spawns sandbox-agent via npx
    - Captures stdout/stderr for log streaming
    - Monitors process health
    - Supports single sandbox per port

    Example:
        provider = LocalProvider(port=2468, workspace=Path('/my/project'))
        info = await provider.create('default', {})
        # sandbox-agent now running at http://127.0.0.1:2468
    """

    def __init__(
        self,
        port: int = 2468,
        workspace: Path | None = None,
        token: str | None = None,
        cors_origin: str | None = None,
    ):
        """Initialize the local provider.

        Args:
            port: Port for sandbox-agent to listen on
            workspace: Working directory for sandbox-agent
            token: Bearer token for sandbox-agent auth. If None, starts with --no-token.
            cors_origin: CORS allowed origin for direct browser connections.
        """
        self.port = port
        self.workspace = workspace or Path.cwd()
        self.token = token
        self.cors_origin = cors_origin
        self.sandboxes: dict[str, LocalSandbox] = {}

    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        """Start a sandbox-agent subprocess.

        Args:
            sandbox_id: Unique identifier for this sandbox
            config: Optional config (unused for local provider)

        Returns:
            SandboxInfo with connection URL

        Raises:
            TimeoutError: If sandbox-agent fails to start within timeout
        """
        # Check if already exists
        existing = self.sandboxes.get(sandbox_id)
        if existing and existing.process and existing.process.poll() is None:
            return SandboxInfo(
                id=sandbox_id,
                base_url=f"http://127.0.0.1:{existing.port}",
                status="running",
                workspace_path=str(existing.workspace),
                provider="local",
            )

        # Start sandbox-agent process
        # Package: sandbox-agent from rivet-dev/sandbox-agent
        cmd = [
            "npx",
            "sandbox-agent",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]

        # Auth: use --token if provided, otherwise --no-token
        if self.token:
            cmd.extend(["--token", self.token])
        else:
            cmd.append("--no-token")

        # CORS: allow direct browser connections from boring-ui frontend
        if self.cors_origin:
            cmd.extend([
                "--cors-allow-origin", self.cors_origin,
                "--cors-allow-header", "Authorization,Content-Type",
                "--cors-allow-method", "GET,POST,PUT,DELETE,OPTIONS",
            ])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(self.workspace),
        )

        sandbox = LocalSandbox(
            id=sandbox_id,
            process=process,
            port=self.port,
            logs=[],
            workspace=self.workspace,
        )
        self.sandboxes[sandbox_id] = sandbox

        # Start log reader task
        sandbox._log_task = asyncio.create_task(self._read_logs(sandbox))

        # Wait for server to be ready
        await self._wait_ready(sandbox)

        return SandboxInfo(
            id=sandbox_id,
            base_url=f"http://127.0.0.1:{self.port}",
            status="running",
            workspace_path=str(self.workspace),
            provider="local",
        )

    async def _read_logs(self, sandbox: LocalSandbox) -> None:
        """Background task to read process stdout into logs buffer."""
        if not sandbox.process or not sandbox.process.stdout:
            return

        loop = asyncio.get_event_loop()
        while sandbox.process.poll() is None:
            try:
                line = await loop.run_in_executor(
                    None, sandbox.process.stdout.readline
                )
                if line:
                    sandbox.logs.append(line.rstrip())
                    # Keep bounded buffer
                    if len(sandbox.logs) > 1000:
                        sandbox.logs.pop(0)
            except Exception:
                break

    async def _wait_ready(
        self, sandbox: LocalSandbox, timeout: int = 30
    ) -> None:
        """Wait for sandbox-agent to respond to health check.

        Args:
            sandbox: The sandbox to wait for
            timeout: Maximum seconds to wait

        Raises:
            TimeoutError: If sandbox doesn't respond in time
        """
        for _ in range(timeout * 2):
            # Check if process died
            if sandbox.process and sandbox.process.poll() is not None:
                # Get any error output
                logs = sandbox.logs[-10:] if sandbox.logs else []
                raise RuntimeError(
                    f"sandbox-agent process exited with code "
                    f"{sandbox.process.returncode}. Logs: {logs}"
                )
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"http://127.0.0.1:{sandbox.port}/v1/health",
                        timeout=2.0,
                    )
                    if r.status_code == 200:
                        return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError(
            f"sandbox-agent failed to start within {timeout}s"
        )

    async def destroy(self, sandbox_id: str) -> None:
        """Stop and cleanup sandbox subprocess."""
        sandbox = self.sandboxes.pop(sandbox_id, None)
        if not sandbox:
            return

        # Cancel log reader
        if sandbox._log_task and not sandbox._log_task.done():
            sandbox._log_task.cancel()
            try:
                await sandbox._log_task
            except asyncio.CancelledError:
                pass

        # Terminate process
        if sandbox.process and sandbox.process.poll() is None:
            sandbox.process.terminate()
            try:
                sandbox.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sandbox.process.kill()
                sandbox.process.wait()

    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get sandbox status."""
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return None

        if sandbox.process is None:
            status = "stopped"
        elif sandbox.process.poll() is None:
            status = "running"
        else:
            status = "stopped"

        return SandboxInfo(
            id=sandbox_id,
            base_url=f"http://127.0.0.1:{sandbox.port}",
            status=status,
            workspace_path=str(sandbox.workspace),
            provider="local",
        )

    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        """Get buffered log lines."""
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return []
        return sandbox.logs[-limit:]

    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        """Stream log lines as they arrive."""
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return

        last_idx = len(sandbox.logs)
        while True:
            # Check if sandbox still exists
            if sandbox_id not in self.sandboxes:
                break

            # Yield new log lines
            current_len = len(sandbox.logs)
            if current_len > last_idx:
                for line in sandbox.logs[last_idx:current_len]:
                    yield line
                last_idx = current_len

            # Check if process ended
            if sandbox.process and sandbox.process.poll() is not None:
                # Yield any remaining lines
                if len(sandbox.logs) > last_idx:
                    for line in sandbox.logs[last_idx:]:
                        yield line
                break

            await asyncio.sleep(0.3)

    async def health_check(self, sandbox_id: str) -> bool:
        """Check if sandbox-agent is responding."""
        sandbox = self.sandboxes.get(sandbox_id)
        if not sandbox:
            return False

        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"http://127.0.0.1:{sandbox.port}/v1/health",
                    timeout=5.0,
                )
                return r.status_code == 200
        except Exception:
            return False
