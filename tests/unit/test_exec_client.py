"""Unit tests for SpritesExecClient."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from boring_ui.api.exec_client import (
    ExecClientError,
    ExecSession,
    SessionState,
    SpritesExecClient,
)
from boring_ui.api.exec_policy import (
    ExecTemplate,
    ExecTemplateRegistry,
    create_default_registry,
)
from boring_ui.api.config import SandboxConfig, SandboxServiceTarget, SpriteLayout


# ── Helpers ──


def _sandbox_config() -> SandboxConfig:
    return SandboxConfig(
        base_url='https://sprites.internal',
        sprite_name='test-sprite',
        api_token='a' * 64,
        session_token_secret='b' * 64,
        service_target=SandboxServiceTarget(
            host='localhost', port=9000, path='/workspace',
        ),
        sprite_layout=SpriteLayout(),
    )


def _registry() -> ExecTemplateRegistry:
    return create_default_registry()


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


def _patch_request(client, mock_response):
    """Patch the _request method on a client."""
    return patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response)


# ── SessionState tests ──


class TestSessionState:

    def test_created_not_active(self):
        s = ExecSession(
            id='s1', template_id='shell',
            state=SessionState.CREATED, created_at=time.time(),
        )
        assert not s.is_active

    def test_running_is_active(self):
        s = ExecSession(
            id='s1', template_id='shell',
            state=SessionState.RUNNING, created_at=time.time(),
        )
        assert s.is_active

    def test_attached_is_active(self):
        s = ExecSession(
            id='s1', template_id='shell',
            state=SessionState.ATTACHED, created_at=time.time(),
        )
        assert s.is_active

    def test_detached_not_active(self):
        s = ExecSession(
            id='s1', template_id='shell',
            state=SessionState.DETACHED, created_at=time.time(),
        )
        assert not s.is_active

    def test_terminated_not_active(self):
        s = ExecSession(
            id='s1', template_id='shell',
            state=SessionState.TERMINATED, created_at=time.time(),
        )
        assert not s.is_active


# ── create_session tests ──


class TestCreateSession:

    @pytest.mark.asyncio
    async def test_creates_session(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200, {'ok': True})

        with _patch_request(client, resp):
            result = await client.create_session('shell')

        assert result['template_id'] == 'shell'
        assert result['status'] == 'running'
        assert result['id'].startswith('exec-')

    @pytest.mark.asyncio
    async def test_tracks_session(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            result = await client.create_session('shell')

        session = client.get_session(result['id'])
        assert session is not None
        assert session.state == SessionState.RUNNING

    @pytest.mark.asyncio
    async def test_unknown_template_raises(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        with pytest.raises(ExecClientError, match='Unknown template'):
            await client.create_session('nonexistent')

    @pytest.mark.asyncio
    async def test_invalid_template_id_raises(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        with pytest.raises(Exception):
            await client.create_session('INVALID!!!')

    @pytest.mark.asyncio
    async def test_http_error_marks_session_error(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(500)

        with _patch_request(client, resp):
            with pytest.raises(ExecClientError, match='HTTP 500'):
                await client.create_session('shell')

        # Session should be tracked with error state
        assert client.session_count == 1

    @pytest.mark.asyncio
    async def test_transport_error(self):
        client = SpritesExecClient(_sandbox_config(), _registry())

        with patch.object(
            client, '_request',
            new_callable=AsyncMock,
            side_effect=ExecClientError('Workspace service unreachable'),
        ):
            with pytest.raises(ExecClientError):
                await client.create_session('shell')

    @pytest.mark.asyncio
    async def test_claude_template(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            result = await client.create_session('claude')

        assert result['template_id'] == 'claude'

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            r1 = await client.create_session('shell')
            r2 = await client.create_session('shell')

        assert r1['id'] != r2['id']
        assert client.session_count == 2


# ── terminate_session tests ──


class TestTerminateSession:

    @pytest.mark.asyncio
    async def test_terminates_existing(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        create_resp = _mock_response(200)
        delete_resp = _mock_response(200)

        with _patch_request(client, create_resp):
            result = await client.create_session('shell')

        with _patch_request(client, delete_resp):
            success = await client.terminate_session(result['id'])

        assert success is True
        session = client.get_session(result['id'])
        assert session.state == SessionState.TERMINATED

    @pytest.mark.asyncio
    async def test_terminate_unknown_returns_false(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        result = await client.terminate_session('nonexistent')
        assert result is False

    @pytest.mark.asyncio
    async def test_terminate_already_terminated(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        create_resp = _mock_response(200)
        delete_resp = _mock_response(200)

        with _patch_request(client, create_resp):
            result = await client.create_session('shell')

        with _patch_request(client, delete_resp):
            await client.terminate_session(result['id'])
            # Second terminate should return True without error
            success = await client.terminate_session(result['id'])

        assert success is True

    @pytest.mark.asyncio
    async def test_terminate_handles_transport_error(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        create_resp = _mock_response(200)

        with _patch_request(client, create_resp):
            result = await client.create_session('shell')

        with patch.object(
            client, '_request',
            new_callable=AsyncMock,
            side_effect=ExecClientError('unreachable'),
        ):
            # Should not raise, just log
            success = await client.terminate_session(result['id'])

        assert success is True  # Still marked as terminated locally


# ── list_sessions tests ──


class TestListSessions:

    @pytest.mark.asyncio
    async def test_empty(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        sessions = await client.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_lists_created_sessions(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            await client.create_session('shell')
            await client.create_session('claude')

        sessions = await client.list_sessions()
        assert len(sessions) == 2
        template_ids = {s['template_id'] for s in sessions}
        assert template_ids == {'shell', 'claude'}


# ── attach/detach tests ──


class TestAttachDetach:

    @pytest.mark.asyncio
    async def test_attach_running_session(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            result = await client.create_session('shell')

        session = client.attach_session(result['id'])
        assert session.state == SessionState.ATTACHED
        assert session.attached_at > 0

    @pytest.mark.asyncio
    async def test_attach_unknown_raises(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        with pytest.raises(ExecClientError, match='not found'):
            client.attach_session('nonexistent')

    @pytest.mark.asyncio
    async def test_attach_terminated_raises(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)
        delete_resp = _mock_response(200)

        with _patch_request(client, resp):
            result = await client.create_session('shell')
        with _patch_request(client, delete_resp):
            await client.terminate_session(result['id'])

        with pytest.raises(ExecClientError, match='not active'):
            client.attach_session(result['id'])

    @pytest.mark.asyncio
    async def test_detach_attached(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            result = await client.create_session('shell')

        client.attach_session(result['id'])
        session = client.detach_session(result['id'])
        assert session.state == SessionState.DETACHED
        assert session.detached_at > 0

    @pytest.mark.asyncio
    async def test_detach_unknown_raises(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        with pytest.raises(ExecClientError, match='not found'):
            client.detach_session('nonexistent')


# ── active_sessions tests ──


class TestActiveSessions:

    @pytest.mark.asyncio
    async def test_active_sessions(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)
        delete_resp = _mock_response(200)

        with _patch_request(client, resp):
            r1 = await client.create_session('shell')
            r2 = await client.create_session('shell')

        with _patch_request(client, delete_resp):
            await client.terminate_session(r1['id'])

        active = client.active_sessions
        assert len(active) == 1
        assert r2['id'] in active


# ── reset tests ──


class TestReset:

    @pytest.mark.asyncio
    async def test_reset_clears_sessions(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        resp = _mock_response(200)

        with _patch_request(client, resp):
            await client.create_session('shell')

        client.reset()
        assert client.session_count == 0
        assert client.active_sessions == {}


# ── Client properties tests ──


class TestClientProperties:

    def test_base_url(self):
        client = SpritesExecClient(_sandbox_config(), _registry())
        assert client.base_url == 'http://localhost:9000/workspace'
