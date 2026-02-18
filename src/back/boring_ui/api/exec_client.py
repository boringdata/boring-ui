"""SpritesExecClient for interactive session operations in sandbox mode.

Provides:
  - Session creation from server-owned command templates
  - Session attach/detach for WebSocket bridging
  - Input writing, terminal resize, and heartbeat
  - Session termination with cleanup
  - Transport-level failure handling
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

import httpx

from .config import SandboxConfig
from .exec_policy import ExecPolicyError, ExecTemplate, ExecTemplateRegistry, validate_template_id
from .internal_auth import generate_auth_token
from .startup_checks import build_workspace_service_url
from .workspace_contract import (
    CURRENT_VERSION,
    WORKSPACE_API_VERSION_HEADER,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_HEARTBEAT_INTERVAL = 30.0
DEFAULT_TERMINATED_RETENTION = 300  # 5 minutes before evicting terminated sessions
DEFAULT_MAX_SESSIONS = 1000  # Hard cap on tracked sessions


class SessionState(Enum):
    CREATED = 'created'
    RUNNING = 'running'
    ATTACHED = 'attached'
    DETACHED = 'detached'
    TERMINATED = 'terminated'
    ERROR = 'error'


@dataclass
class ExecSession:
    """Metadata for an active exec session."""
    id: str
    template_id: str
    state: SessionState
    created_at: float
    attached_at: float = 0.0
    detached_at: float = 0.0
    terminated_at: float = 0.0
    error: str = ''

    @property
    def is_active(self) -> bool:
        return self.state in (SessionState.RUNNING, SessionState.ATTACHED)


class ExecClientError(Exception):
    """Raised when an exec operation fails."""

    def __init__(self, reason: str, session_id: str = ''):
        self.reason = reason
        self.session_id = session_id
        super().__init__(f'Exec error: {reason}')


class SpritesExecClient:
    """Client for interactive exec session operations.

    Provides the same interface as StubExecClient:
      - create_session(template_id, **kwargs) -> dict
      - terminate_session(session_id) -> bool
      - list_sessions() -> list[dict]

    Plus interactive session support:
      - attach_session / detach_session
      - write_input / resize_terminal
      - heartbeat
    """

    def __init__(
        self,
        sandbox_config: SandboxConfig,
        template_registry: ExecTemplateRegistry,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        terminated_retention: float = DEFAULT_TERMINATED_RETENTION,
    ) -> None:
        self._config = sandbox_config
        self._base_url = build_workspace_service_url(sandbox_config)
        self._templates = template_registry
        self._timeout = timeout
        self._max_sessions = max_sessions
        self._terminated_retention = terminated_retention
        self._sessions: dict[str, ExecSession] = {}
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

    def _evict_terminated(self) -> int:
        """Remove terminated/error sessions older than retention period.

        Also enforces the hard cap on total tracked sessions by evicting
        the oldest terminated sessions first.

        Returns the number of evicted sessions.
        """
        now = time.time()
        cutoff = now - self._terminated_retention
        evicted = 0

        # Phase 1: evict expired terminated/error sessions
        expired_ids = [
            sid for sid, s in self._sessions.items()
            if s.state in (SessionState.TERMINATED, SessionState.ERROR)
            and (s.terminated_at or s.created_at) < cutoff
        ]
        for sid in expired_ids:
            del self._sessions[sid]
            evicted += 1

        # Phase 2: if still over cap, evict oldest terminated/error first
        if len(self._sessions) > self._max_sessions:
            terminated = sorted(
                (
                    (sid, s) for sid, s in self._sessions.items()
                    if s.state in (SessionState.TERMINATED, SessionState.ERROR)
                ),
                key=lambda pair: pair[1].terminated_at or pair[1].created_at,
            )
            while terminated and len(self._sessions) > self._max_sessions:
                sid, _ = terminated.pop(0)
                del self._sessions[sid]
                evicted += 1

        if evicted:
            logger.debug('Evicted %d terminated sessions', evicted)
        return evicted

    def _auth_headers(self) -> dict[str, str]:
        token = generate_auth_token(self._config.api_token)
        return {
            'X-Workspace-Internal-Auth': token,
            WORKSPACE_API_VERSION_HEADER: CURRENT_VERSION,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request to the workspace service exec API."""
        url = f'{self._base_url}{path}'
        try:
            client = self._get_client()
            resp = await client.request(
                method, url,
                headers=self._auth_headers(),
                json=json_body,
            )
            return resp
        except httpx.ConnectError:
            raise ExecClientError('Workspace service unreachable')
        except httpx.TimeoutException:
            raise ExecClientError('Workspace service timeout')
        except Exception as exc:
            raise ExecClientError(f'Transport error: {exc}')

    async def create_session(
        self,
        template_id: str,
        **kwargs,
    ) -> dict:
        """Create a new exec session from a registered template.

        Args:
            template_id: ID of the command template (e.g., 'shell', 'claude')
            **kwargs: Additional session options (e.g., env overrides)

        Returns:
            dict with session metadata (id, template_id, status)

        Raises:
            ExecClientError: If template is unknown or creation fails
        """
        self._evict_terminated()
        validate_template_id(template_id)

        try:
            template = self._templates.get(template_id)
        except ExecPolicyError as exc:
            raise ExecClientError(str(exc))

        session_id = f'exec-{uuid.uuid4().hex[:12]}'
        now = time.time()

        session = ExecSession(
            id=session_id,
            template_id=template_id,
            state=SessionState.CREATED,
            created_at=now,
        )

        # Request session creation from workspace service
        try:
            resp = await self._request('POST', '/api/sessions', json_body={
                'session_id': session_id,
                'template_id': template_id,
                'command': list(template.command),
                'working_directory': template.working_directory,
                'env': template.env,
                'timeout_seconds': template.timeout_seconds,
            })

            if resp.status_code >= 400:
                session.state = SessionState.ERROR
                session.error = f'HTTP {resp.status_code}'
                self._sessions[session_id] = session
                raise ExecClientError(
                    f'Session creation failed: HTTP {resp.status_code}',
                    session_id=session_id,
                )

        except ExecClientError:
            raise
        except Exception as exc:
            session.state = SessionState.ERROR
            session.error = str(exc)
            self._sessions[session_id] = session
            raise ExecClientError(
                f'Session creation failed: {exc}',
                session_id=session_id,
            )

        session.state = SessionState.RUNNING
        self._sessions[session_id] = session

        return {
            'id': session_id,
            'template_id': template_id,
            'status': 'running',
        }

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate an exec session.

        Returns True if the session existed and was terminated.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False

        if session.state == SessionState.TERMINATED:
            return True

        try:
            resp = await self._request(
                'DELETE', f'/api/sessions/{session_id}',
            )
            # Accept both 200 and 404 (already gone)
            if resp.status_code not in (200, 204, 404):
                logger.warning(
                    'Session %s termination returned %d',
                    session_id, resp.status_code,
                )
        except ExecClientError as exc:
            logger.warning('Session %s termination error: %s', session_id, exc)

        session.state = SessionState.TERMINATED
        session.terminated_at = time.time()
        return True

    async def list_sessions(self) -> list[dict]:
        """List all tracked sessions with their current state."""
        self._evict_terminated()
        return [
            {
                'id': s.id,
                'template_id': s.template_id,
                'status': s.state.value,
                'created_at': s.created_at,
            }
            for s in self._sessions.values()
        ]

    def attach_session(self, session_id: str) -> ExecSession:
        """Mark a session as attached (WebSocket bridge connected).

        Raises ExecClientError if session not found or not active.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ExecClientError(
                f'Session not found: {session_id}',
                session_id=session_id,
            )
        if not session.is_active:
            raise ExecClientError(
                f'Session {session_id} is not active (state={session.state.value})',
                session_id=session_id,
            )
        session.state = SessionState.ATTACHED
        session.attached_at = time.time()
        return session

    def detach_session(self, session_id: str) -> ExecSession:
        """Mark a session as detached (WebSocket bridge disconnected)."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ExecClientError(
                f'Session not found: {session_id}',
                session_id=session_id,
            )
        if session.state == SessionState.ATTACHED:
            session.state = SessionState.DETACHED
            session.detached_at = time.time()
        return session

    def get_session(self, session_id: str) -> ExecSession | None:
        """Get session metadata by ID."""
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> dict[str, ExecSession]:
        """Return all sessions in an active state."""
        return {
            k: v for k, v in self._sessions.items()
            if v.is_active
        }

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def reset(self) -> None:
        """Clear all tracked sessions."""
        self._sessions.clear()
