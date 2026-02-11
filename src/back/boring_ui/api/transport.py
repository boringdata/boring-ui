"""Workspace transport abstraction for control-plane to local-api communication (bd-1adh.4).

Defines a unified transport interface to abstract away provider-specific connection details.

Current implementations:
- HTTPInternalTransport: For direct HTTP to internal_sandbox_url
- SpritesProxyTransport: For WebSocket relay through Sprites proxy API
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
from typing import Optional


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status for workspace transport."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class WorkspaceResponse:
    """Response from a workspace transport request.

    Attributes:
        status_code: HTTP status code
        headers: Response headers dict
        body: Response body bytes
        elapsed_sec: Time elapsed for request
        transport_type: Type of transport used ('http', 'sprites_proxy', etc.)
        error_code: Optional error code for transport-level errors
    """
    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed_sec: float
    transport_type: str
    error_code: Optional[str] = None


class WorkspaceTransport(ABC):
    """Abstract interface for workspace transport.

    Implementations handle the specifics of connecting to local-api
    on behalf of the control plane.
    """

    @abstractmethod
    async def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 30.0,
        trace_id: str | None = None,
    ) -> WorkspaceResponse:
        """Send a request to the workspace plane.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (e.g., /internal/v1/files/tree)
            body: Optional request body
            headers: Optional additional headers
            timeout_sec: Request timeout in seconds
            trace_id: Trace ID for observability

        Returns:
            WorkspaceResponse with status, headers, body

        Raises:
            asyncio.TimeoutError: If request times out
            Exception: For other transport errors
        """
        ...

    @abstractmethod
    async def health_check(
        self,
        timeout_sec: float = 5.0,
    ) -> HealthStatus:
        """Check health of workspace transport.

        Args:
            timeout_sec: Health check timeout

        Returns:
            HealthStatus enum value
        """
        ...


class HTTPInternalTransport(WorkspaceTransport):
    """HTTP transport to internal sandbox URL (non-Sprites hosted mode).

    Direct HTTP requests to INTERNAL_SANDBOX_URL with optional auth.
    Used for non-Sprites hosted providers that run local-api separately
    but on a reachable internal network.
    """

    def __init__(
        self,
        base_url: str,
        default_timeout_sec: float = 30.0,
    ):
        """Initialize HTTP transport.

        Args:
            base_url: Base URL of local-api (e.g., http://internal.local:9000)
            default_timeout_sec: Default request timeout
        """
        self.base_url = base_url.rstrip("/")
        self.default_timeout_sec = default_timeout_sec
        self.session = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float | None = None,
        trace_id: str | None = None,
    ) -> WorkspaceResponse:
        """Send HTTP request to internal sandbox.

        Args:
            method: HTTP method
            path: URL path
            body: Optional body
            headers: Optional headers
            timeout_sec: Request timeout (uses default if not specified)
            trace_id: Trace ID header

        Returns:
            WorkspaceResponse with HTTP response

        Raises:
            asyncio.TimeoutError: On timeout
            Exception: On connection/parse error
        """
        import aiohttp
        import time

        if timeout_sec is None:
            timeout_sec = self.default_timeout_sec

        url = f"{self.base_url}{path}"
        req_headers = headers or {}

        if trace_id:
            req_headers["X-Trace-ID"] = trace_id

        start = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    data=body,
                    headers=req_headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_sec),
                ) as resp:
                    response_body = await resp.read()
                    elapsed = time.time() - start

                    return WorkspaceResponse(
                        status_code=resp.status,
                        headers=dict(resp.headers),
                        body=response_body,
                        elapsed_sec=elapsed,
                        transport_type="http",
                    )
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            logger.error(
                f"HTTP transport timeout after {elapsed:.1f}s to {url}",
                extra={"trace_id": trace_id},
            )
            raise
        except Exception as e:
            elapsed = time.time() - start
            logger.error(
                f"HTTP transport error after {elapsed:.1f}s to {url}: {e}",
                extra={"trace_id": trace_id},
            )
            raise

    async def health_check(
        self,
        timeout_sec: float = 5.0,
    ) -> HealthStatus:
        """Check HTTP endpoint health."""
        try:
            response = await self.request(
                "GET",
                "/internal/health",
                timeout_sec=timeout_sec,
            )
            if response.status_code == 200:
                return HealthStatus.HEALTHY
            else:
                logger.warning(
                    f"Health check got status {response.status_code}"
                )
                return HealthStatus.DEGRADED
        except asyncio.TimeoutError:
            return HealthStatus.UNAVAILABLE
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return HealthStatus.ERROR


class SpritesProxyTransport(WorkspaceTransport):
    """WebSocket relay transport through Sprites proxy API (bd-1adh.4.1).

    Implements deterministic one-request-per-connection relay:
    1. Open WebSocket to Sprites proxy
    2. Send handshake: {host, port}
    3. Send exactly one HTTP request
    4. Receive and parse HTTP response
    5. Close connection

    All steps are time-bounded and parser-protected.
    """

    def __init__(
        self,
        sprites_token: str,
        sprite_name: str,
        local_api_port: int,
        connect_timeout_sec: float = 5.0,
        handshake_timeout_sec: float = 5.0,
        response_timeout_sec: float = 30.0,
        max_response_bytes: int = 10 * 1024 * 1024,  # 10MB default
    ):
        """Initialize Sprites proxy transport.

        Args:
            sprites_token: Sprites API token (Bearer token)
            sprite_name: Target sprite name
            local_api_port: Port where local-api listens in sprite
            connect_timeout_sec: WebSocket connect timeout
            handshake_timeout_sec: Handshake frame timeout
            response_timeout_sec: Response receive timeout
            max_response_bytes: Max response size before error
        """
        self.sprites_token = sprites_token
        self.sprite_name = sprite_name
        self.local_api_port = local_api_port
        self.connect_timeout_sec = connect_timeout_sec
        self.handshake_timeout_sec = handshake_timeout_sec
        self.response_timeout_sec = response_timeout_sec
        self.max_response_bytes = max_response_bytes

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float | None = None,
        trace_id: str | None = None,
    ) -> WorkspaceResponse:
        """Send request through Sprites proxy relay.

        Args:
            method: HTTP method
            path: URL path
            body: Optional body
            headers: Optional headers
            timeout_sec: Request timeout (uses response_timeout_sec if not specified)
            trace_id: Trace ID for observability

        Returns:
            WorkspaceResponse with relayed HTTP response

        Raises:
            asyncio.TimeoutError: On various timeout scenarios
            Exception: On relay or parse error
        """
        import json
        import websockets
        import time

        if timeout_sec is None:
            timeout_sec = self.response_timeout_sec

        ws_url = (
            f"wss://api.sprites.dev/v1/sprites/{self.sprite_name}/proxy"
        )
        auth_header = f"Bearer {self.sprites_token}"

        start = time.time()

        try:
            # 1. Connect to Sprites proxy
            logger.debug(
                f"Sprites: Connecting to {ws_url}",
                extra={"trace_id": trace_id},
            )

            async with asyncio.timeout(self.connect_timeout_sec):
                async with websockets.connect(
                    ws_url,
                    extra_headers={"Authorization": auth_header},
                ) as websocket:
                    logger.debug(
                        f"Sprites: Connected, sending handshake",
                        extra={"trace_id": trace_id},
                    )

                    # 2. Send handshake
                    handshake = json.dumps({
                        "host": "localhost",
                        "port": self.local_api_port,
                    })

                    try:
                        async with asyncio.timeout(self.handshake_timeout_sec):
                            await websocket.send(handshake)
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Sprites: Handshake send timeout",
                            extra={"trace_id": trace_id},
                        )
                        raise
                    except Exception as e:
                        logger.error(
                            f"Sprites: Handshake send error: {e}",
                            extra={"trace_id": trace_id},
                        )
                        raise

                    # 3. Wait for handshake response
                    try:
                        async with asyncio.timeout(self.handshake_timeout_sec):
                            handshake_resp = await websocket.recv()
                            logger.debug(
                                f"Sprites: Handshake response: {handshake_resp}",
                                extra={"trace_id": trace_id},
                            )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Sprites: Handshake response timeout",
                            extra={"trace_id": trace_id},
                        )
                        raise
                    except Exception as e:
                        logger.error(
                            f"Sprites: Handshake response error: {e}",
                            extra={"trace_id": trace_id},
                        )
                        raise

                    # 4. Build HTTP request
                    req_headers = headers or {}
                    req_headers["Connection"] = "close"  # Deterministic close
                    if trace_id:
                        req_headers["X-Trace-ID"] = trace_id

                    http_request = self._build_http_request(
                        method, path, req_headers, body
                    )

                    logger.debug(
                        f"Sprites: Sending HTTP request ({len(http_request)} bytes)",
                        extra={"trace_id": trace_id},
                    )

                    # 5. Send HTTP request
                    try:
                        async with asyncio.timeout(timeout_sec):
                            await websocket.send(http_request)
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Sprites: HTTP request send timeout",
                            extra={"trace_id": trace_id},
                        )
                        raise
                    except Exception as e:
                        logger.error(
                            f"Sprites: HTTP request send error: {e}",
                            extra={"trace_id": trace_id},
                        )
                        raise

                    # 6. Receive HTTP response
                    response_chunks = []
                    total_bytes = 0

                    try:
                        async with asyncio.timeout(timeout_sec):
                            while True:
                                chunk = await websocket.recv()
                                if isinstance(chunk, bytes):
                                    response_chunks.append(chunk)
                                    total_bytes += len(chunk)

                                    if total_bytes > self.max_response_bytes:
                                        logger.error(
                                            f"Sprites: Response exceeded {self.max_response_bytes} bytes",
                                            extra={"trace_id": trace_id},
                                        )
                                        raise ValueError(
                                            f"Response too large: {total_bytes} > {self.max_response_bytes}"
                                        )
                                elif isinstance(chunk, str):
                                    # Text frame might indicate end
                                    if chunk == "":
                                        break
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Sprites: Response receive timeout",
                            extra={"trace_id": trace_id},
                        )
                        raise
                    except Exception as e:
                        logger.error(
                            f"Sprites: Response receive error: {e}",
                            extra={"trace_id": trace_id},
                        )
                        raise

                    # 7. Parse HTTP response
                    raw_response = b"".join(response_chunks)
                    status_code, response_headers, response_body = (
                        self._parse_http_response(raw_response)
                    )

                    elapsed = time.time() - start
                    logger.info(
                        f"Sprites: Request complete - status {status_code}, {elapsed:.2f}s",
                        extra={"trace_id": trace_id},
                    )

                    return WorkspaceResponse(
                        status_code=status_code,
                        headers=response_headers,
                        body=response_body,
                        elapsed_sec=elapsed,
                        transport_type="sprites_proxy",
                    )

        except asyncio.TimeoutError:
            elapsed = time.time() - start
            logger.error(
                f"Sprites: Request timeout after {elapsed:.1f}s",
                extra={"trace_id": trace_id},
            )
            raise

        except Exception as e:
            elapsed = time.time() - start
            logger.error(
                f"Sprites: Request failed after {elapsed:.1f}s: {e}",
                extra={"trace_id": trace_id},
            )
            raise

    def _build_http_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> bytes:
        """Build raw HTTP/1.1 request bytes.

        Args:
            method: HTTP method
            path: URL path
            headers: Headers dict
            body: Optional body

        Returns:
            Raw HTTP request bytes
        """
        request_line = f"{method} {path} HTTP/1.1\r\n"
        header_lines = "".join(
            f"{k}: {v}\r\n" for k, v in headers.items()
        )

        if body:
            header_lines += f"Content-Length: {len(body)}\r\n"
            request = (
                request_line + header_lines + "\r\n"
            ).encode() + body
        else:
            request = (request_line + header_lines + "\r\n").encode()

        return request

    def _parse_http_response(
        self,
        raw: bytes,
    ) -> tuple[int, dict[str, str], bytes]:
        """Parse raw HTTP response.

        Args:
            raw: Raw HTTP response bytes

        Returns:
            Tuple of (status_code, headers_dict, body_bytes)

        Raises:
            ValueError: If response is malformed
        """
        try:
            # Split on double CRLF
            parts = raw.split(b"\r\n\r\n", 1)
            if len(parts) != 2:
                raise ValueError("Malformed response: no body separator")

            headers_text, body = parts

            # Parse status line
            lines = headers_text.split(b"\r\n")
            status_line = lines[0].decode("utf-8", errors="replace")

            parts = status_line.split(" ", 2)
            if len(parts) < 2:
                raise ValueError(f"Malformed status line: {status_line}")

            try:
                status_code = int(parts[1])
            except ValueError:
                raise ValueError(f"Invalid status code: {parts[1]}")

            # Parse headers
            response_headers = {}
            for line in lines[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    response_headers[
                        key.decode("utf-8", errors="replace").strip()
                    ] = value.decode("utf-8", errors="replace").strip()

            return status_code, response_headers, body

        except Exception as e:
            logger.error(f"HTTP response parse error: {e}")
            raise ValueError(f"Response parse error: {e}") from e

    async def health_check(
        self,
        timeout_sec: float = 5.0,
    ) -> HealthStatus:
        """Check Sprites proxy health."""
        try:
            response = await self.request(
                "GET",
                "/internal/health",
                timeout_sec=timeout_sec,
            )
            if response.status_code == 200:
                return HealthStatus.HEALTHY
            else:
                return HealthStatus.DEGRADED
        except asyncio.TimeoutError:
            return HealthStatus.UNAVAILABLE
        except Exception as e:
            logger.error(f"Sprites health check error: {e}")
            return HealthStatus.ERROR
