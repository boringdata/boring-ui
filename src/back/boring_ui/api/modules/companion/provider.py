"""Companion server provider — manages Bun subprocess lifecycle.

Runs The Vibe Companion as a local subprocess. Passes auth
and CORS config via environment variables.
"""
import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

import httpx


@dataclass
class CompanionInfo:
    """Status of a Companion server instance."""

    id: str
    base_url: str
    status: str  # starting, running, stopped, error
    workspace_path: str
    provider: str = "companion"


@dataclass
class _CompanionProcess:
    """Internal state for a Companion subprocess."""

    id: str
    process: subprocess.Popen | None
    port: int
    logs: list[str] = field(default_factory=list)
    workspace: Path = field(default_factory=Path.cwd)
    _log_task: asyncio.Task | None = field(default=None, repr=False)


class CompanionProvider:
    """Runs Companion server as a local Bun subprocess.

    Requires Bun to be installed on the host system.

    Example:
        provider = CompanionProvider(port=3456, workspace=Path('/my/project'))
        info = await provider.create('default', {})
        # Companion now running at http://127.0.0.1:3456
    """

    def __init__(
        self,
        port: int = 3456,
        workspace: Path | None = None,
        signing_key_hex: str | None = None,
        cors_origin: str | None = None,
        server_dir: Path | None = None,
    ):
        """Initialize the Companion provider.

        Args:
            port: Port for Companion server to listen on.
            workspace: Working directory for Claude Code sessions.
            signing_key_hex: Hex-encoded JWT signing key for auth middleware.
            cors_origin: Allowed CORS origin for browser connections.
            server_dir: Path to Companion server source. Defaults to
                vendor/companion/ relative to the workspace.
        """
        self.port = port
        self.workspace = workspace or Path.cwd()
        self.signing_key_hex = signing_key_hex
        self.cors_origin = cors_origin
        self.server_dir = server_dir
        self._instances: dict[str, _CompanionProcess] = {}

    def _check_bun(self) -> str:
        """Verify Bun is installed and return its path."""
        bun = shutil.which("bun")
        if not bun:
            raise RuntimeError(
                "Bun runtime not found. "
                "Install: curl -fsSL https://bun.sh/install | bash"
            )
        return bun

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for the subprocess."""
        env = {**os.environ}
        env["PORT"] = str(self.port)
        env["HOST"] = "127.0.0.1"
        env["DEFAULT_CWD"] = str(self.workspace)

        if self.signing_key_hex:
            env["SERVICE_AUTH_SECRET"] = self.signing_key_hex
        elif not env.get("AUTH_DISABLED"):
            # Fail-closed: no secret and auth not disabled = reject all
            env["AUTH_DISABLED"] = "false"

        if self.cors_origin:
            env["CORS_ORIGIN"] = self.cors_origin

        return env

    async def create(self, instance_id: str, config: dict) -> CompanionInfo:
        """Start a Companion server subprocess."""
        existing = self._instances.get(instance_id)
        if existing and existing.process and existing.process.poll() is None:
            return CompanionInfo(
                id=instance_id,
                base_url=f"http://127.0.0.1:{existing.port}",
                status="running",
                workspace_path=str(existing.workspace),
            )

        bun = self._check_bun()
        env = self._build_env()

        # Determine server entry point
        server_dir = self.server_dir
        if not server_dir:
            # Look in common locations
            candidates = [
                self.workspace / "vendor" / "companion",
                Path(__file__).parent / "vendor",
            ]
            for candidate in candidates:
                if (candidate / "package.json").exists():
                    server_dir = candidate
                    break

        if not server_dir or not server_dir.exists():
            raise RuntimeError(
                f"Companion server source not found. "
                f"Expected at vendor/companion/ with package.json"
            )

        process = subprocess.Popen(
            [bun, "run", "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(server_dir),
            env=env,
        )

        instance = _CompanionProcess(
            id=instance_id,
            process=process,
            port=self.port,
            logs=[],
            workspace=self.workspace,
        )
        self._instances[instance_id] = instance

        # Start log reader
        instance._log_task = asyncio.create_task(self._read_logs(instance))

        # Wait for server ready
        await self._wait_ready(instance)

        return CompanionInfo(
            id=instance_id,
            base_url=f"http://127.0.0.1:{self.port}",
            status="running",
            workspace_path=str(self.workspace),
        )

    async def _read_logs(self, instance: _CompanionProcess) -> None:
        """Background task to read process stdout into logs buffer."""
        if not instance.process or not instance.process.stdout:
            return

        loop = asyncio.get_event_loop()
        while instance.process.poll() is None:
            try:
                line = await loop.run_in_executor(
                    None, instance.process.stdout.readline
                )
                if line:
                    instance.logs.append(line.rstrip())
                    if len(instance.logs) > 1000:
                        instance.logs.pop(0)
            except Exception:
                break

    async def _wait_ready(
        self, instance: _CompanionProcess, timeout: int = 30
    ) -> None:
        """Wait for Companion to respond to health check."""
        for _ in range(timeout * 2):
            if instance.process and instance.process.poll() is not None:
                logs = instance.logs[-10:] if instance.logs else []
                raise RuntimeError(
                    f"Companion process exited with code "
                    f"{instance.process.returncode}. Logs: {logs}"
                )
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"http://127.0.0.1:{instance.port}/health",
                        timeout=2.0,
                    )
                    if r.status_code == 200:
                        return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError(
            f"Companion failed to start within {timeout}s"
        )

    async def destroy(self, instance_id: str) -> None:
        """Stop and cleanup Companion subprocess."""
        instance = self._instances.pop(instance_id, None)
        if not instance:
            return

        if instance._log_task and not instance._log_task.done():
            instance._log_task.cancel()
            try:
                await instance._log_task
            except asyncio.CancelledError:
                pass

        if instance.process and instance.process.poll() is None:
            instance.process.terminate()
            try:
                instance.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                instance.process.kill()
                instance.process.wait()

    async def get_info(self, instance_id: str) -> CompanionInfo | None:
        """Get Companion status."""
        instance = self._instances.get(instance_id)
        if not instance:
            return None

        if instance.process is None:
            status = "stopped"
        elif instance.process.poll() is None:
            status = "running"
        else:
            status = "stopped"

        return CompanionInfo(
            id=instance_id,
            base_url=f"http://127.0.0.1:{instance.port}",
            status=status,
            workspace_path=str(instance.workspace),
        )

    async def get_logs(self, instance_id: str, limit: int = 100) -> list[str]:
        """Get buffered log lines."""
        instance = self._instances.get(instance_id)
        if not instance:
            return []
        return instance.logs[-limit:]

    async def stream_logs(self, instance_id: str) -> AsyncIterator[str]:
        """Stream log lines as they arrive."""
        instance = self._instances.get(instance_id)
        if not instance:
            return

        last_idx = len(instance.logs)
        while True:
            if instance_id not in self._instances:
                break

            current_len = len(instance.logs)
            if current_len > last_idx:
                for line in instance.logs[last_idx:current_len]:
                    yield line
                last_idx = current_len

            if instance.process and instance.process.poll() is not None:
                if len(instance.logs) > last_idx:
                    for line in instance.logs[last_idx:]:
                        yield line
                break

            await asyncio.sleep(0.3)

    async def health_check(self, instance_id: str) -> bool:
        """Check if Companion is responding."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"http://127.0.0.1:{instance.port}/health",
                    timeout=5.0,
                )
                return r.status_code == 200
        except Exception:
            return False
