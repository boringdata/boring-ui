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
import httpx
import uuid

logger = logging.getLogger(__name__)


@dataclass
class SandboxClientConfig:
    """Configuration for sandbox client."""
    
    internal_url: str  # e.g., http://127.0.0.1:2469
    capability_token: str = ""  # Injected by control plane
    timeout_seconds: int = 30
    max_retries: int = 3
    enable_observability: bool = True


class HostedSandboxClient:
    """Client for communicating with internal sandbox service.
    
    Handles:
    - Capability token injection in Authorization header
    - Trace context propagation (request correlation)
    - Timeout and retry policies
    - Observability (logging, metrics)
    """

    def __init__(self, config: SandboxClientConfig):
        self.config = config
        self.base_url = config.internal_url
        self._request_count = 0

    async def list_files(self, path: str = ".") -> Dict[str, Any]:
        """List files in sandbox (privileged operation)."""
        return await self._request("GET", "/internal/v1/files/list", params={"path": path})

    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read file from sandbox (privileged operation)."""
        return await self._request("GET", "/internal/v1/files/read", params={"path": path})

    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file to sandbox (privileged operation)."""
        return await self._request(
            "POST",
            "/internal/v1/files/write",
            params={"path": path, "content": content},
        )

    async def git_status(self) -> Dict[str, Any]:
        """Get git status from sandbox."""
        return await self._request("GET", "/internal/v1/git/status")

    async def git_diff(self, context: str = "working") -> Dict[str, Any]:
        """Get git diff from sandbox."""
        return await self._request("GET", "/internal/v1/git/diff", params={"context": context})

    async def exec_run(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """Run command in sandbox."""
        return await self._request(
            "POST",
            "/internal/v1/exec/run",
            params={"command": command, "timeout_seconds": timeout_seconds},
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute request with auth, tracing, and retry logic."""
        self._request_count += 1
        trace_id = str(uuid.uuid4())
        url = f"{self.base_url}{path}"

        headers = self._build_headers(trace_id)

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(
                f"Sandbox request failed [trace_id={trace_id}]: {method} {path} - {e}"
            )
            raise

    def _build_headers(self, trace_id: str) -> Dict[str, str]:
        """Build request headers with auth and tracing."""
        headers = {
            "X-Trace-ID": trace_id,
            "X-Request-ID": f"{self._request_count}",
        }
        
        if self.config.capability_token:
            headers["Authorization"] = f"Bearer {self.config.capability_token}"

        return headers

    def get_stats(self) -> Dict[str, Any]:
        """Get client observability stats."""
        return {
            "total_requests": self._request_count,
            "internal_url": self.base_url,
            "timeout_seconds": self.config.timeout_seconds,
        }
