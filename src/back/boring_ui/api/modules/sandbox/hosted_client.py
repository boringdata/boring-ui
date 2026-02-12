"""Hosted control plane client abstraction for sandbox operations (bd-1pwb.5.1).

Provides:
- Unified client for communicating with private internal sandbox service
- Capability token injection and auth header management
- Timeout and retry policy
- Request correlation via trace IDs
- Observability hooks
"""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
import asyncio
import httpx
import uuid
import json
from urllib.parse import urlencode
from ...auth import ServiceTokenSigner
from ...transport import WorkspaceTransport

logger = logging.getLogger(__name__)


@dataclass
class SandboxClientError(Exception):
    """Typed sandbox client error with stable mapping metadata."""

    code: str
    message: str
    http_status: int
    request_id: str
    trace_id: str
    sandbox_status: int | None = None
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


@dataclass
class SandboxClientConfig:
    """Configuration for sandbox client."""

    internal_url: str  # e.g., http://127.0.0.1:2469
    capability_token: str = ""  # Injected by control plane
    timeout_seconds: int = 30
    max_retries: int = 3
    enable_observability: bool = True
    service_signer: ServiceTokenSigner | None = None
    transport: WorkspaceTransport | None = None


class HostedSandboxClient:
    """Client for communicating with internal sandbox service.

    Handles:
    - Capability token injection in Authorization header
    - Trace context propagation (request correlation)
    - Timeout and retry policies (via HostedClient if provided, else httpx)
    - Observability (logging, metrics)
    - Transport abstraction (supports HTTP and Sprites via HostedClient)
    """

    def __init__(self, config: SandboxClientConfig):
        self.config = config
        self.base_url = config.internal_url
        self._request_count = 0
        self._transport = config.transport

    async def list_files(
        self, path: str = ".", capability_token: str = "", request_id: str = ""
    ) -> Dict[str, Any]:
        """List files in sandbox (privileged operation)."""
        return await self._request(
            "GET",
            "/internal/v1/files/list",
            params={"path": path},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def read_file(
        self, path: str, capability_token: str = "", request_id: str = ""
    ) -> Dict[str, Any]:
        """Read file from sandbox (privileged operation)."""
        return await self._request(
            "GET",
            "/internal/v1/files/read",
            params={"path": path},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def write_file(
        self, path: str, content: str, capability_token: str = "", request_id: str = ""
    ) -> Dict[str, Any]:
        """Write file to sandbox (privileged operation)."""
        return await self._request(
            "POST",
            "/internal/v1/files/write",
            json_body={"path": path, "content": content},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def delete_file(
        self, path: str, capability_token: str = "", request_id: str = ""
    ) -> Dict[str, Any]:
        """Delete file/directory in sandbox (privileged operation)."""
        return await self._request(
            "DELETE",
            "/internal/v1/files/delete",
            params={"path": path},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def rename_file(
        self,
        old_path: str,
        new_path: str,
        capability_token: str = "",
        request_id: str = "",
    ) -> Dict[str, Any]:
        """Rename file/directory in sandbox (privileged operation)."""
        return await self._request(
            "POST",
            "/internal/v1/files/rename",
            params={"old_path": old_path, "new_path": new_path},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def move_file(
        self,
        src_path: str,
        dest_dir: str,
        capability_token: str = "",
        request_id: str = "",
    ) -> Dict[str, Any]:
        """Move file/directory in sandbox (privileged operation)."""
        return await self._request(
            "POST",
            "/internal/v1/files/move",
            params={"src_path": src_path, "dest_dir": dest_dir},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def git_status(self, capability_token: str = "", request_id: str = "") -> Dict[str, Any]:
        """Get git status from sandbox."""
        return await self._request(
            "GET",
            "/internal/v1/git/status",
            capability_token=capability_token,
            request_id=request_id,
        )

    async def git_diff(
        self, context: str = "working", capability_token: str = "", request_id: str = ""
    ) -> Dict[str, Any]:
        """Get git diff from sandbox."""
        return await self._request(
            "GET",
            "/internal/v1/git/diff",
            params={"context": context},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def exec_run(
        self,
        command: str,
        timeout_seconds: int = 30,
        capability_token: str = "",
        request_id: str = "",
    ) -> Dict[str, Any]:
        """Run command in sandbox."""
        return await self._request(
            "POST",
            "/internal/v1/exec/run",
            json_body={"command": command, "timeout_seconds": timeout_seconds},
            capability_token=capability_token,
            request_id=request_id,
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        capability_token: str = "",
        request_id: str = "",
    ) -> Dict[str, Any]:
        """Execute request with auth, tracing, and retry logic.

        Uses injected transport when configured; otherwise falls back to direct httpx.
        """
        self._request_count += 1
        trace_id = str(uuid.uuid4())

        headers = self._build_headers(
            trace_id=trace_id,
            capability_token=capability_token,
            request_id=request_id,
        )

        # Use transport abstraction when available (bd-2j57.4)
        if self._transport:
            return await self._request_via_transport(
                method, path, params, json_body, headers, trace_id
            )

        # Fallback to direct httpx (for cases where transport not needed)
        return await self._request_via_httpx(
            method, path, params, json_body, headers, trace_id
        )

    async def _request_via_transport(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]],
        json_body: Optional[Dict[str, Any]],
        headers: Dict[str, str],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute request via WorkspaceTransport with retry/backoff."""
        import json as json_lib
        from ...error_codes import TransportError

        # Build full path with query params if present
        full_path = path
        if params:
            full_path = f"{path}?{urlencode(params)}"

        # Prepare request body
        body_bytes = None
        if json_body:
            body_bytes = json_lib.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        attempts = max(1, self.config.max_retries)
        backoff_ms = [100, 300, 900]
        response_body: bytes = b""
        status_code = 502

        for attempt in range(attempts):
            try:
                status_code, _, response_body = await self._transport.request(
                    method=method,
                    path=full_path,
                    body=body_bytes,
                    headers=headers,
                    timeout_sec=float(self.config.timeout_seconds),
                    trace_id=trace_id,
                )
            except TransportError as te:
                retryable = te.retryable or te.http_status in (502, 503, 504)
                if retryable and attempt < attempts - 1:
                    await asyncio.sleep(backoff_ms[min(attempt, len(backoff_ms) - 1)] / 1000)
                    continue
                if te.http_status == 504:
                    mapped_status = 504
                elif te.http_status >= 500:
                    mapped_status = 502
                else:
                    mapped_status = te.http_status
                raise SandboxClientError(
                    code=f"transport_{te.code.value}",
                    message=te.message,
                    http_status=mapped_status,
                    request_id=headers.get("X-Request-ID", ""),
                    trace_id=trace_id,
                    sandbox_status=te.http_status,
                    retryable=te.retryable,
                )

            if status_code in (502, 503, 504) and attempt < attempts - 1:
                await asyncio.sleep(backoff_ms[min(attempt, len(backoff_ms) - 1)] / 1000)
                continue
            break

        # Check final response status
        if status_code >= 400:
            body_text = response_body.decode("utf-8", errors="replace") if response_body else ""
            is_timeout = status_code in (408, 504)
            is_unavailable = status_code in (502, 503)
            raise SandboxClientError(
                code="sandbox_timeout" if is_timeout else "sandbox_unavailable" if is_unavailable else "sandbox_error",
                message=body_text or f"Sandbox returned status {status_code}",
                http_status=504 if is_timeout else 502 if is_unavailable else status_code,
                request_id=headers.get("X-Request-ID", ""),
                trace_id=trace_id,
                sandbox_status=status_code,
                retryable=is_timeout or is_unavailable,
            )

        # Parse JSON response
        if not response_body:
            return {}
        return json_lib.loads(response_body.decode("utf-8"))

    async def _request_via_httpx(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]],
        json_body: Optional[Dict[str, Any]],
        headers: Dict[str, str],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute request via httpx directly."""
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                if response.status_code >= 400:
                    raise SandboxClientError(
                        code="sandbox_http_error",
                        message=f"sandbox returned status {response.status_code}",
                        http_status=502,
                        request_id=headers["X-Request-ID"],
                        trace_id=trace_id,
                        sandbox_status=response.status_code,
                    )
                try:
                    return response.json()
                except ValueError as exc:
                    raise SandboxClientError(
                        code="sandbox_invalid_response",
                        message="sandbox returned non-JSON response",
                        http_status=502,
                        request_id=headers["X-Request-ID"],
                        trace_id=trace_id,
                    ) from exc
        except SandboxClientError:
            raise
        except httpx.TimeoutException as e:
            logger.error(
                f"Sandbox request timeout [trace_id={trace_id}]: {method} {path} - {e}"
            )
            raise SandboxClientError(
                code="sandbox_timeout",
                message="sandbox request timed out",
                http_status=504,
                request_id=headers["X-Request-ID"],
                trace_id=trace_id,
                retryable=True,
            ) from e
        except httpx.RequestError as e:
            logger.error(
                f"Sandbox request failed [trace_id={trace_id}]: {method} {path} - {e}"
            )
            raise SandboxClientError(
                code="sandbox_unreachable",
                message="sandbox service unreachable",
                http_status=502,
                request_id=headers["X-Request-ID"],
                trace_id=trace_id,
                retryable=True,
            ) from e

    def _build_headers(self, trace_id: str, capability_token: str, request_id: str = "") -> Dict[str, str]:
        """Build request headers with auth and tracing."""
        headers = {
            "X-Trace-ID": trace_id,
            "X-Request-ID": request_id or f"{self._request_count}",
        }

        token = capability_token or self.config.capability_token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        if self.config.service_signer:
            headers["X-Service-Token"] = self.config.service_signer.sign_request(ttl_seconds=60)

        return headers

    def get_stats(self) -> Dict[str, Any]:
        """Get client observability stats."""
        return {
            "total_requests": self._request_count,
            "internal_url": self.base_url,
            "timeout_seconds": self.config.timeout_seconds,
        }
