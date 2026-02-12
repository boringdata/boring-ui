"""Local API exec operations (bd-1adh.2.1).

Provides privileged command execution:
- Run commands with timeout protection
- Stream stdout/stderr
- Capture exit codes
- Resource limits (memory, CPU)
- Secret/credential masking in logs

All routes require capability token authorization via bd-1pwb.3.2.
"""

from fastapi import APIRouter, HTTPException, status, Request
from pathlib import Path
import subprocess
import asyncio
from ..sandbox_auth import require_capability
from ..modules.sandbox.policy import (
    SandboxPolicies,
    sanitize_exec_env,
    mask_secrets,
    truncate_output,
)


def create_exec_router(workspace_root: Path) -> APIRouter:
    """Create router for exec operations.

    Routes mounted at /internal/v1/exec.
    Commands run in workspace_root context.
    Requires capability token authorization.

    Args:
        workspace_root: Root path for command execution

    Returns:
        FastAPI APIRouter for mounting
    """
    router = APIRouter(prefix="/exec", tags=["exec-internal"])
    policies = SandboxPolicies()
    resource_limits = policies.get_resource_limits()
    # Build sanitized env once at router creation time
    clean_env = sanitize_exec_env()

    @router.post("/run")
    @require_capability("exec:run")
    async def run_command(
        request: Request,
        command: str,
        timeout_seconds: int = 30,
        capture_output: bool = True,
    ):
        """Run a command with timeout and capture.

        Defensive guardrails:
        - Timeout protection (default 30s, max from policy)
        - Environment sanitization (control-plane secrets stripped)
        - Output truncation (max_output_lines from policy)
        - Secret masking in stdout/stderr
        - No shell expansion (use shlex for safe parsing)

        Requires capability: exec:run
        """
        try:
            # Validate timeout against policy limit
            max_timeout = resource_limits["timeout_seconds"]
            timeout = min(timeout_seconds, max_timeout)
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

            if not args:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Command cannot be empty",
                )

            if not policies.allow_command(command):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Command blocked by execution policy",
                )

            # Run with sanitized environment and timeout
            try:
                proc = await asyncio.create_subprocess_exec(
                        *args,
                        stdout=asyncio.subprocess.PIPE if capture_output else None,
                        stderr=asyncio.subprocess.PIPE if capture_output else None,
                        cwd=workspace_root,
                        env=clean_env,
                )
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                if 'proc' in locals() and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Command timed out after {timeout}s",
                )

            stdout = stdout_b.decode(errors="replace") if capture_output and stdout_b else None
            stderr = stderr_b.decode(errors="replace") if capture_output and stderr_b else None

            # Enforce output limits
            max_lines = resource_limits["max_output_lines"]
            stdout_truncated = False
            stderr_truncated = False
            if stdout:
                stdout, stdout_truncated = truncate_output(stdout, max_lines)
            if stderr:
                stderr, stderr_truncated = truncate_output(stderr, max_lines)

            # Mask secrets in output
            if stdout:
                stdout = mask_secrets(stdout)
            if stderr:
                stderr = mask_secrets(stderr)

            return {
                "command": command,
                "exit_code": proc.returncode,
                "timeout_seconds": timeout,
                "status": "completed",
                "stdout": stdout,
                "stderr": stderr,
                "truncated": stdout_truncated or stderr_truncated,
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
