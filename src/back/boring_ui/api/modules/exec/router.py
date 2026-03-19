"""Direct exec endpoint — runs commands on the workspace VM.

No sandbox layer. Each workspace runs in its own Fly VM (Firecracker).
The VM boundary IS the isolation. Post-MVP: add bwrap for defense-in-depth.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class ExecRequest(BaseModel):
    command: str
    cwd: str = "."
    timeout_seconds: int = Field(default=60, ge=1, le=600)


class ExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool


_MAX_OUTPUT_BYTES = 512 * 1024  # 512 KB per stream


def create_exec_router(config) -> APIRouter:
    router = APIRouter(prefix="/api/v1/sandbox", tags=["exec"])

    @router.post("/exec", response_model=ExecResponse)
    async def exec_command(body: ExecRequest, request: Request):
        workspace_root = getattr(config, "workspace_root", ".")
        cwd = str(workspace_root / body.cwd) if hasattr(workspace_root, "__truediv__") else body.cwd

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                body.command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=body.timeout_seconds,
            )
        except asyncio.TimeoutError:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecResponse(
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {body.timeout_seconds}s",
                duration_ms=duration_ms,
                truncated=False,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        truncated = len(stdout_bytes) > _MAX_OUTPUT_BYTES or len(stderr_bytes) > _MAX_OUTPUT_BYTES

        return ExecResponse(
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            stderr=stderr_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
            truncated=truncated,
        )

    return router
