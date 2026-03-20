"""Command execution service for boring-ui API."""
import asyncio
import time
from pathlib import Path

from fastapi import HTTPException

from ...config import APIConfig
from ...workspace.paths import resolve_path_beneath


_TIMEOUT_SECONDS = 60
_MAX_OUTPUT_BYTES = 512 * 1024  # 512 KB


async def execute_command(
    command: str,
    cwd: str | None,
    workspace_root: Path,
) -> dict:
    """Execute a shell command within the workspace.

    Args:
        command: Shell command to execute
        cwd: Working directory relative to workspace root (None = workspace root)
        workspace_root: Absolute path to the workspace root

    Returns:
        dict with stdout, stderr, exit_code, duration_ms
    """
    resolved_root = Path(workspace_root).resolve()

    if cwd is not None:
        try:
            exec_dir = resolve_path_beneath(resolved_root, Path(cwd))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not exec_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {cwd}")
    else:
        exec_dir = resolved_root

    env = {
        'HOME': str(resolved_root),
        'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    }

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(exec_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=5,
            )
        except Exception:
            stdout_bytes = b''
            stderr_bytes = b''
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            'stdout': stdout_bytes[:_MAX_OUTPUT_BYTES].decode(errors='replace'),
            'stderr': stderr_bytes[:_MAX_OUTPUT_BYTES].decode(errors='replace')
                + f'\n[killed: timeout after {_TIMEOUT_SECONDS}s]',
            'exit_code': -1,
            'duration_ms': duration_ms,
        }

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        'stdout': stdout_bytes[:_MAX_OUTPUT_BYTES].decode(errors='replace'),
        'stderr': stderr_bytes[:_MAX_OUTPUT_BYTES].decode(errors='replace'),
        'exit_code': proc.returncode,
        'duration_ms': duration_ms,
    }
