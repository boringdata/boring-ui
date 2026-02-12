"""Stubbed provider clients for deterministic sandbox testing.

These stubs replace real SpritesProxyClient, SpritesExecClient, and
SpritesServicesClient in tests, providing canned responses without
network calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StubResponse:
    """A canned HTTP response for stubbed clients."""
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    json_body: dict | list | None = None
    text_body: str = ''
    error: Exception | None = None

    def json(self) -> dict | list:
        if self.json_body is not None:
            return self.json_body
        return {}

    @property
    def text(self) -> str:
        return self.text_body


class StubProxyClient:
    """Stub for SpritesProxyClient.

    Provides deterministic responses for HTTP proxy operations
    (file tree, file read/write, git, sessions, search).
    """

    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], StubResponse] = {}
        self._calls: list[dict] = []
        self._default_response = StubResponse(status_code=200, json_body={})

    def set_response(
        self, method: str, path: str, response: StubResponse,
    ) -> None:
        """Configure a canned response for a method+path pair."""
        self._responses[(method.upper(), path)] = response

    def set_default(self, response: StubResponse) -> None:
        """Set the fallback response for unmatched requests."""
        self._default_response = response

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict | None = None,
        content: bytes | None = None,
    ) -> StubResponse:
        """Execute a stubbed request."""
        call = {
            'method': method.upper(),
            'path': path,
            'headers': headers or {},
            'params': params or {},
            'json': json,
        }
        self._calls.append(call)

        resp = self._responses.get((method.upper(), path), self._default_response)
        if resp.error:
            raise resp.error
        return resp

    @property
    def calls(self) -> list[dict]:
        """Return list of recorded calls."""
        return list(self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def reset(self) -> None:
        """Clear all responses and recorded calls."""
        self._responses.clear()
        self._calls.clear()


class StubExecClient:
    """Stub for SpritesExecClient.

    Provides deterministic behavior for interactive session operations
    (create, attach, detach, terminate, resize, input).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._calls: list[dict] = []
        self._next_session_id = 1
        self._create_error: Exception | None = None

    def set_create_error(self, error: Exception) -> None:
        """Configure an error for the next create_session call."""
        self._create_error = error

    async def create_session(
        self, template_id: str, **kwargs,
    ) -> dict:
        """Create a stubbed exec session."""
        self._calls.append({
            'action': 'create',
            'template_id': template_id,
            **kwargs,
        })
        if self._create_error:
            err = self._create_error
            self._create_error = None
            raise err

        session_id = f'stub-session-{self._next_session_id}'
        self._next_session_id += 1
        self._sessions[session_id] = {
            'id': session_id,
            'template_id': template_id,
            'status': 'running',
        }
        return self._sessions[session_id]

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a stubbed session."""
        self._calls.append({'action': 'terminate', 'session_id': session_id})
        if session_id in self._sessions:
            self._sessions[session_id]['status'] = 'terminated'
            return True
        return False

    async def list_sessions(self) -> list[dict]:
        """List all stubbed sessions."""
        self._calls.append({'action': 'list'})
        return list(self._sessions.values())

    @property
    def calls(self) -> list[dict]:
        return list(self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def active_sessions(self) -> dict[str, dict]:
        return {
            k: v for k, v in self._sessions.items()
            if v.get('status') == 'running'
        }

    def reset(self) -> None:
        self._sessions.clear()
        self._calls.clear()
        self._next_session_id = 1
        self._create_error = None


class StubServicesClient:
    """Stub for SpritesServicesClient.

    Provides deterministic health/version/readiness responses.
    """

    def __init__(
        self,
        *,
        healthy: bool = True,
        version: str = '0.1.0',
        ready: bool = True,
    ) -> None:
        self._healthy = healthy
        self._version = version
        self._ready = ready
        self._calls: list[dict] = []

    async def check_health(self) -> dict:
        self._calls.append({'action': 'health'})
        status = 'ok' if self._healthy else 'unhealthy'
        return {'status': status}

    async def check_version(self) -> dict:
        self._calls.append({'action': 'version'})
        return {'version': self._version, 'compatible': True}

    async def is_ready(self) -> bool:
        self._calls.append({'action': 'ready'})
        return self._ready

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy

    def set_version(self, version: str) -> None:
        self._version = version

    def set_ready(self, ready: bool) -> None:
        self._ready = ready

    @property
    def calls(self) -> list[dict]:
        return list(self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def reset(self) -> None:
        self._calls.clear()
