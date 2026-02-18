"""SpritesServicesClient for workspace service readiness and endpoint resolution.

Provides:
  - Health checks (/healthz) with bounded retries and jitter
  - Version checks (/__meta/version) with compatibility validation
  - Readiness state combining health + version
  - Short TTL cache for resolved endpoint state
  - Basic circuit breaker to avoid hammering a down service
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx

from .config import SandboxConfig
from .internal_auth import generate_auth_token
from .startup_checks import build_workspace_service_url
from .workspace_contract import (
    CURRENT_VERSION,
    HEALTHZ_ENDPOINT,
    VERSION_ENDPOINT,
    WORKSPACE_API_VERSION_HEADER,
    is_compatible,
)

logger = logging.getLogger(__name__)


# ── Configuration defaults ──

DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 0.5
DEFAULT_RETRY_MAX_DELAY = 5.0
DEFAULT_CACHE_TTL = 30.0
DEFAULT_CB_FAILURE_THRESHOLD = 5
DEFAULT_CB_RECOVERY_TIMEOUT = 30.0


# ── Circuit breaker ──


class CircuitState(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


@dataclass
class CircuitBreaker:
    """Simple circuit breaker to avoid hammering a failing service.

    States:
      CLOSED  - normal operation, requests go through
      OPEN    - too many failures, requests rejected immediately
      HALF_OPEN - recovery probe: one request allowed to test
    """
    failure_threshold: int = DEFAULT_CB_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_CB_RECOVERY_TIMEOUT
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0


# ── Cached result ──


@dataclass
class CachedResult:
    """A time-bounded cached value."""
    value: dict
    fetched_at: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.fetched_at > self.ttl


class ServiceUnavailableError(Exception):
    """Raised when the workspace service is unreachable or circuit is open."""


# ── Client ──


class SpritesServicesClient:
    """Client for workspace service health, version, and readiness.

    Provides the same interface as StubServicesClient:
      - check_health() -> dict
      - check_version() -> dict
      - is_ready() -> bool

    Plus operational features:
      - Bounded retries with exponential backoff and jitter
      - Short TTL cache for health/version results
      - Circuit breaker to fail fast when service is down
    """

    def __init__(
        self,
        sandbox_config: SandboxConfig,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        cb_failure_threshold: int = DEFAULT_CB_FAILURE_THRESHOLD,
        cb_recovery_timeout: float = DEFAULT_CB_RECOVERY_TIMEOUT,
    ) -> None:
        self._config = sandbox_config
        self._base_url = build_workspace_service_url(sandbox_config)
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._cache_ttl = cache_ttl

        self._circuit = CircuitBreaker(
            failure_threshold=cb_failure_threshold,
            recovery_timeout=cb_recovery_timeout,
        )
        self._health_cache: CachedResult | None = None
        self._version_cache: CachedResult | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared httpx client, creating it lazily."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client and release connections."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit.state

    def _auth_headers(self) -> dict[str, str]:
        """Generate internal auth and version headers."""
        token = generate_auth_token(self._config.api_token)
        return {
            'X-Workspace-Internal-Auth': token,
            WORKSPACE_API_VERSION_HEADER: CURRENT_VERSION,
        }

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request with retry, jitter, and circuit breaker."""
        if self._circuit.is_open:
            raise ServiceUnavailableError(
                f'Circuit breaker open for {self._base_url}'
            )

        url = f'{self._base_url}{path}'
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_client()
                resp = await client.request(method, url, headers=headers or {})
                self._circuit.record_success()
                return resp
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = exc
                self._circuit.record_failure()
                if attempt < self._max_retries:
                    delay = min(
                        self._retry_base_delay * (2 ** attempt),
                        self._retry_max_delay,
                    )
                    jitter = delay * random.uniform(0.0, 0.5)
                    await asyncio.sleep(delay + jitter)
            except Exception as exc:
                self._circuit.record_failure()
                raise ServiceUnavailableError(
                    f'Unexpected error reaching {url}: {exc}'
                ) from exc

        raise ServiceUnavailableError(
            f'Failed to reach {url} after {self._max_retries + 1} attempts: {last_error}'
        )

    async def check_health(self) -> dict:
        """Check workspace service health.

        Returns:
            dict with 'status' key ('ok', 'degraded', or 'unhealthy')
        """
        if self._health_cache and not self._health_cache.is_expired:
            return self._health_cache.value

        try:
            resp = await self._request_with_retry(
                'GET', HEALTHZ_ENDPOINT,
                headers=self._auth_headers(),
            )
            if resp.status_code != 200:
                result = {'status': 'unhealthy', 'detail': f'HTTP {resp.status_code}'}
            else:
                data = resp.json()
                status = data.get('status', 'unknown')
                if status in ('ok', 'degraded'):
                    result = {'status': status}
                else:
                    result = {'status': 'unhealthy', 'detail': f'Unknown status: {status}'}
        except ServiceUnavailableError as exc:
            result = {'status': 'unhealthy', 'detail': str(exc)}

        self._health_cache = CachedResult(
            value=result, fetched_at=time.monotonic(), ttl=self._cache_ttl,
        )
        return result

    async def check_version(self) -> dict:
        """Check workspace service version compatibility.

        Returns:
            dict with 'version' and 'compatible' keys
        """
        if self._version_cache and not self._version_cache.is_expired:
            return self._version_cache.value

        try:
            resp = await self._request_with_retry(
                'GET', VERSION_ENDPOINT,
                headers=self._auth_headers(),
            )
            if resp.status_code != 200:
                result = {
                    'version': '',
                    'compatible': False,
                    'detail': f'HTTP {resp.status_code}',
                }
            else:
                data = resp.json()
                version = data.get('version', '')
                if not version:
                    result = {
                        'version': '',
                        'compatible': False,
                        'detail': 'Missing version field',
                    }
                else:
                    compatible = is_compatible(version)
                    result = {'version': version, 'compatible': compatible}
                    if not compatible:
                        result['detail'] = (
                            f'Incompatible: upstream={version}, '
                            f'control_plane={CURRENT_VERSION}'
                        )
        except ServiceUnavailableError as exc:
            result = {'version': '', 'compatible': False, 'detail': str(exc)}

        self._version_cache = CachedResult(
            value=result, fetched_at=time.monotonic(), ttl=self._cache_ttl,
        )
        return result

    async def is_ready(self) -> bool:
        """Check if the workspace service is ready to accept requests.

        Service is ready when:
        - Health check returns 'ok' or 'degraded'
        - Version is compatible
        """
        health = await self.check_health()
        if health['status'] not in ('ok', 'degraded'):
            return False

        version = await self.check_version()
        return version.get('compatible', False) is True

    def invalidate_cache(self) -> None:
        """Clear all cached results, forcing fresh checks."""
        self._health_cache = None
        self._version_cache = None

    def reset_circuit(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._circuit.reset()
