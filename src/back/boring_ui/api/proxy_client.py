"""SpritesProxyClient for forwarding HTTP requests to workspace service.

Provides strict forwarding of file/git/session/search requests to the
workspace service running inside a sprite with:
  - Allowlist-based target, path, and method validation
  - HMAC-SHA256 auth token injection
  - Header sanitization (request and response)
  - Response size enforcement
  - Error normalization (upstream -> browser-safe)
  - No redirect following (SSRF prevention)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import SandboxConfig
from .internal_auth import generate_auth_token
from .proxy_guardrails import (
    ProxyGuardrailConfig,
    ProxyRequestDenied,
    ResponseTooLarge,
    sanitize_request_headers,
    sanitize_response_headers,
    validate_proxy_method,
    validate_proxy_path,
    validate_proxy_target,
    validate_response_size,
)
from .startup_checks import build_workspace_service_url
from .workspace_contract import (
    CURRENT_VERSION,
    WORKSPACE_API_VERSION_HEADER,
    map_upstream_error,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


@dataclass
class ProxyResponse:
    """Normalized response from a proxied request."""
    status_code: int
    headers: dict[str, str]
    body: bytes
    json_body: dict | list | None = None
    text_body: str = ''

    def json(self) -> dict | list:
        if self.json_body is not None:
            return self.json_body
        return {}

    @property
    def text(self) -> str:
        return self.text_body


class ProxyError(Exception):
    """Raised when a proxy request fails in a way that maps to an HTTP error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f'Proxy error {status_code}: {detail}')


class SpritesProxyClient:
    """Client for forwarding HTTP requests to the workspace service.

    Provides the same interface as StubProxyClient:
      - request(method, path, *, headers, params, json, content) -> response

    Plus security features:
      - SSRF guardrails (allowlisted targets/paths/methods)
      - Auth token injection
      - Header sanitization
      - Response size caps
      - Error normalization
    """

    def __init__(
        self,
        sandbox_config: SandboxConfig,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        guardrail_config: ProxyGuardrailConfig | None = None,
    ) -> None:
        self._config = sandbox_config
        self._base_url = build_workspace_service_url(sandbox_config)
        self._timeout = timeout
        self._guardrails = guardrail_config or ProxyGuardrailConfig()
        self._target = sandbox_config.service_target

    @property
    def base_url(self) -> str:
        return self._base_url

    def _auth_headers(self) -> dict[str, str]:
        """Generate internal auth and version headers."""
        token = generate_auth_token(self._config.api_token)
        return {
            'X-Workspace-Internal-Auth': token,
            WORKSPACE_API_VERSION_HEADER: CURRENT_VERSION,
        }

    def _validate_request(self, method: str, path: str) -> None:
        """Validate request against proxy guardrails.

        Raises ProxyRequestDenied if the request is not allowed.
        """
        validate_proxy_target(self._target.host, self._target.port, self._guardrails)
        validate_proxy_path(path, self._guardrails)
        validate_proxy_method(method, self._guardrails)

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict | None = None,
        content: bytes | None = None,
    ) -> ProxyResponse:
        """Execute a proxied HTTP request to the workspace service.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            path: Request path (e.g., '/api/tree')
            headers: Additional request headers
            params: Query parameters
            json: JSON request body
            content: Raw request body

        Returns:
            ProxyResponse with normalized status, headers, and body

        Raises:
            ProxyRequestDenied: If the request violates guardrails
            ProxyError: If the request fails with a mappable error
        """
        method = method.upper()
        self._validate_request(method, path)

        # Build request headers: auth + sanitized caller headers
        req_headers = self._auth_headers()
        if headers:
            sanitized = sanitize_request_headers(headers)
            req_headers.update(sanitized)

        url = f'{self._base_url}{path}'

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
            ) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=req_headers,
                    params=params or {},
                    json=json,
                    content=content,
                )
        except httpx.ConnectError:
            raise ProxyError(503, 'Workspace service unreachable')
        except httpx.TimeoutException:
            raise ProxyError(504, 'Workspace service timeout')
        except Exception as exc:
            logger.error('Unexpected proxy error: %s', exc)
            raise ProxyError(502, 'Proxy transport error')

        # Check for redirect (SSRF prevention)
        if 300 <= resp.status_code < 400:
            raise ProxyError(502, 'Redirect not allowed')

        # Validate response size
        content_length = resp.headers.get('content-length')
        if content_length:
            try:
                validate_response_size(int(content_length), self._guardrails)
            except ResponseTooLarge:
                raise ProxyError(502, 'Response too large')

        # Read body with size check
        body = resp.content
        if len(body) > self._guardrails.max_response_bytes:
            raise ProxyError(502, 'Response too large')

        # Sanitize response headers
        resp_headers = sanitize_response_headers(dict(resp.headers))

        # Parse JSON if content-type indicates it
        json_body = None
        text_body = ''
        ct = resp.headers.get('content-type', '')
        if 'json' in ct:
            try:
                json_body = resp.json()
            except Exception:
                text_body = body.decode('utf-8', errors='replace')
        else:
            text_body = body.decode('utf-8', errors='replace')

        # Map upstream errors to browser-safe status codes
        if resp.status_code >= 400:
            mapped_status, mapped_detail = map_upstream_error(resp.status_code)
            return ProxyResponse(
                status_code=mapped_status,
                headers=resp_headers,
                body=body,
                json_body=json_body or {'error': mapped_detail},
                text_body=text_body,
            )

        return ProxyResponse(
            status_code=resp.status_code,
            headers=resp_headers,
            body=body,
            json_body=json_body,
            text_body=text_body,
        )
