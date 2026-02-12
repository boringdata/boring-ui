"""Hosted proxy handlers for sandbox operations (bd-1pwb.5.2 & 5.3).

Provides public API endpoints that proxy to private internal sandbox service
with policy enforcement, permission checking, and error mapping.

Routes exposed publicly but authenticated via capability tokens.
"""

from fastapi import APIRouter, HTTPException, status, Request
from .hosted_client import HostedSandboxClient, SandboxClientError
from ...auth_middleware import require_permission, get_auth_context
from ...capability_tokens import CapabilityTokenIssuer
from ...logging_middleware import get_request_id

import logging

logger = logging.getLogger(__name__)


def create_hosted_sandbox_proxy_router(
    client: HostedSandboxClient,
    capability_issuer: CapabilityTokenIssuer,
) -> APIRouter:
    """Create proxy router that forwards requests to internal sandbox service.
    
    Routes mounted at /api/v1/sandbox/proxy.
    Requires authentication and capability tokens.
    """
    router = APIRouter(prefix="/sandbox/proxy", tags=["sandbox-proxy"])

    def _issue_token(request: Request, operations: set[str]) -> str:
        auth = get_auth_context(request)
        workspace_id = auth.workspace_id or "default"
        return capability_issuer.issue_token(
            workspace_id=workspace_id,
            operations=operations,
            ttl_seconds=60,
        )

    def _raise_proxy_error(err: SandboxClientError) -> None:
        raise HTTPException(
            status_code=err.http_status,
            detail={
                "error": err.code,
                "message": err.message,
                "request_id": err.request_id,
                "trace_id": err.trace_id,
                "sandbox_status": err.sandbox_status,
            },
        )

    def _generic_proxy_error(request: Request) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "proxy_sandbox_failed",
                "message": "failed to access sandbox",
                "request_id": get_request_id(request) or "",
            },
        )

    # File operations (bd-1pwb.5.2)
    @router.get("/files/list")
    @require_permission("files:read")
    async def proxy_list_files(request: Request, path: str = "."):
        """Proxy: List files in sandbox."""
        try:
            token = _issue_token(request, {"files:list"})
            return await client.list_files(
                path,
                capability_token=token,
                request_id=get_request_id(request) or "",
            )
        except SandboxClientError as e:
            logger.error(
                "Files list proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise _generic_proxy_error(request)

    @router.get("/files/read")
    @require_permission("files:read")
    async def proxy_read_file(request: Request, path: str):
        """Proxy: Read file from sandbox."""
        try:
            token = _issue_token(request, {"files:read"})
            return await client.read_file(
                path,
                capability_token=token,
                request_id=get_request_id(request) or "",
            )
        except SandboxClientError as e:
            logger.error(
                "Files read proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            raise _generic_proxy_error(request)

    @router.post("/files/write")
    @require_permission("files:write")
    async def proxy_write_file(request: Request, path: str, content: str):
        """Proxy: Write file to sandbox."""
        try:
            token = _issue_token(request, {"files:write"})
            return await client.write_file(
                path,
                content,
                capability_token=token,
                request_id=get_request_id(request) or "",
            )
        except SandboxClientError as e:
            logger.error(
                "Files write proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            raise _generic_proxy_error(request)

    # Git operations (bd-1pwb.5.2)
    @router.get("/git/status")
    @require_permission("git:read")
    async def proxy_git_status(request: Request):
        """Proxy: Get git status from sandbox."""
        try:
            token = _issue_token(request, {"git:status"})
            return await client.git_status(
                capability_token=token,
                request_id=get_request_id(request) or "",
            )
        except SandboxClientError as e:
            logger.error(
                "Git status proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            raise _generic_proxy_error(request)

    @router.get("/git/diff")
    @require_permission("git:read")
    async def proxy_git_diff(request: Request, context: str = "working"):
        """Proxy: Get git diff from sandbox."""
        try:
            token = _issue_token(request, {"git:diff"})
            return await client.git_diff(
                context,
                capability_token=token,
                request_id=get_request_id(request) or "",
            )
        except SandboxClientError as e:
            logger.error(
                "Git diff proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to get git diff: {e}")
            raise _generic_proxy_error(request)

    # Exec operations (bd-1pwb.5.3)
    @router.post("/exec/run")
    @require_permission("exec:run")
    async def proxy_exec_run(request: Request, command: str, timeout_seconds: int = 30):
        """Proxy: Execute command in sandbox.
        
        Defensive guardrails:
        - Timeout enforcement (max 300s)
        - Rate limiting (will be added)
        - Audit logging of all exec operations

        Error semantics:
        - sandbox timeout -> 504 with structured detail
        - sandbox unreachable/http/protocol errors -> 502 with structured detail
        - unexpected proxy failures -> 502 `proxy_exec_failed`
        """
        try:
            # Enforce timeout limits
            timeout = min(timeout_seconds, 300)
            if timeout < 1:
                timeout = 30

            logger.info(f"Executing command in sandbox: {command[:50]}...")
            token = _issue_token(request, {"exec:run"})
            request_id = get_request_id(request) or ""
            return await client.exec_run(
                command,
                timeout,
                capability_token=token,
                request_id=request_id,
            )
        except SandboxClientError as e:
            logger.error(
                "Exec proxy sandbox error code=%s request_id=%s trace_id=%s sandbox_status=%s",
                e.code,
                e.request_id,
                e.trace_id,
                e.sandbox_status,
            )
            _raise_proxy_error(e)
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error": "proxy_exec_failed",
                    "message": "failed to execute in sandbox",
                    "request_id": get_request_id(request) or "",
                },
            )

    @router.get("/health")
    async def proxy_health():
        """Health check: verify internal sandbox service is reachable."""
        try:
            # Quick check by fetching client stats
            stats = client.get_stats()
            return {
                "status": "ok",
                "service": "sandbox-proxy",
                "internal_url": stats.get("internal_url"),
            }
        except Exception as e:
            logger.error(f"Sandbox proxy health check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sandbox service unavailable",
            )

    return router
