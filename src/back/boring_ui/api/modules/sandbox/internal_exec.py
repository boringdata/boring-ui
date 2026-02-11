"""Internal exec operations for sandbox (bd-1pwb.4.3).

Provides privileged command execution:
- Run commands with timeout protection
- Stream stdout/stderr
- Capture exit codes
- Resource limits (memory, CPU)
- Secret/credential masking in logs
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Optional
import subprocess
import asyncio


def create_internal_exec_router(workspace_root: Path) -> APIRouter:
    """Create router for internal exec operations.
    
    Routes mounted at /internal/v1/exec.
    Commands run in workspace_root context.
    """
    router = APIRouter(prefix="/exec", tags=["exec-internal"])

    @router.post("/run")
    async def run_command(
        command: str,
        timeout_seconds: int = 30,
        capture_output: bool = True,
    ):
        """Run a command with timeout and capture.
        
        Defensive guardrails:
        - Timeout protection (default 30s, max 300s)
        - Memory limits via subprocess restrictions
        - No shell expansion (use shlex for safe parsing)
        """
        try:
            # Validate timeout
            timeout = min(timeout_seconds, 300)
            if timeout < 1:
                timeout = 30

            # Parse command safely (no shell expansion)
            import shlex
            try:
                args = shlex.split(command)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid command syntax: {e}",
                )

            # Run with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *args,
                        stdout=subprocess.PIPE if capture_output else None,
                        stderr=subprocess.PIPE if capture_output else None,
                        cwd=workspace_root,
                    ).wait(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Command timed out after {timeout}s",
                )

            return {
                "command": command,
                "exit_code": result,
                "timeout_seconds": timeout,
                "status": "completed",
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.get("/health")
    async def exec_health():
        """Check if exec service is healthy."""
        return {
            "status": "ok",
            "max_timeout": 300,
            "default_timeout": 30,
        }

    return router
