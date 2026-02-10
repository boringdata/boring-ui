"""Tests for SpritesClient: exceptions, retry, CRUD, exec, checkpoints.

Covers bd-1ni.1.1 through bd-1ni.1.5.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from boring_ui.api.modules.sandbox.providers.sprites_client import (
    SpritesAPIError,
    SpritesClient,
    SpritesClientError,
    SpritesCLINotFoundError,
    SpritesExecError,
)


# ─────────────────────── helpers ───────────────────────


def _make_client(**overrides) -> SpritesClient:
    """Create a SpritesClient with mocked CLI check."""
    defaults = {"token": "tok", "org": "test-org"}
    defaults.update(overrides)
    with patch("shutil.which", return_value="/usr/bin/sprite"):
        return SpritesClient(**defaults)


def _mock_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
    text: str = "",
    headers: dict | None = None,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text or str(json_data)
    resp.headers = headers or {}
    return resp


# ─────────────────────── Exception hierarchy ───────────────────────


class TestExceptionHierarchy:
    def test_base_error_is_exception(self):
        assert issubclass(SpritesClientError, Exception)

    def test_cli_not_found_inherits_base(self):
        assert issubclass(SpritesCLINotFoundError, SpritesClientError)

    def test_api_error_inherits_base(self):
        assert issubclass(SpritesAPIError, SpritesClientError)

    def test_exec_error_inherits_base(self):
        assert issubclass(SpritesExecError, SpritesClientError)

    def test_all_catchable_by_base(self):
        for exc_cls in (SpritesCLINotFoundError, SpritesAPIError, SpritesExecError):
            with pytest.raises(SpritesClientError):
                if exc_cls is SpritesAPIError:
                    raise exc_cls(500, "fail")
                elif exc_cls is SpritesExecError:
                    raise exc_cls(1, "", "fail")
                else:
                    raise exc_cls("missing")


class TestSpritesAPIError:
    def test_attributes(self):
        err = SpritesAPIError(404, "not found")
        assert err.status_code == 404
        assert err.message == "not found"

    def test_str_format(self):
        err = SpritesAPIError(500, "server error")
        assert "500" in str(err)
        assert "server error" in str(err)

    def test_various_codes(self):
        for code in (400, 401, 403, 404, 409, 422, 500, 502, 503):
            err = SpritesAPIError(code, f"error-{code}")
            assert err.status_code == code


class TestSpritesExecError:
    def test_attributes(self):
        err = SpritesExecError(1, "output", "error msg")
        assert err.return_code == 1
        assert err.stdout == "output"
        assert err.stderr == "error msg"

    def test_str_shows_stderr_when_present(self):
        err = SpritesExecError(2, "out", "some error")
        assert "some error" in str(err)
        assert "exit 2" in str(err)

    def test_str_shows_stdout_when_no_stderr(self):
        err = SpritesExecError(1, "some output", "")
        assert "some output" in str(err)

    def test_str_shows_no_output(self):
        err = SpritesExecError(1, "", "")
        assert "(no output)" in str(err)

    def test_truncates_long_stderr(self):
        long_err = "x" * 500
        err = SpritesExecError(1, "", long_err)
        assert len(str(err)) < 300


class TestSpritesCLINotFoundError:
    def test_is_catchable(self):
        with pytest.raises(SpritesCLINotFoundError):
            raise SpritesCLINotFoundError("not found")

    def test_message(self):
        err = SpritesCLINotFoundError("sprite not on PATH")
        assert "sprite not on PATH" in str(err)


# ─────────────────────── SpritesClient.__init__ ───────────────────────


class TestSpritesClientInit:
    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_creates_with_defaults(self, mock_which):
        client = SpritesClient(token="tok", org="my-org")
        assert client._token == "tok"
        assert client._org == "my-org"
        assert client._base_url == "https://api.sprites.dev"
        assert client._name_prefix == ""
        assert client._retry_strategy == "exponential"
        assert client._max_retries == 3

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_custom_params(self, mock_which):
        client = SpritesClient(
            token="t", org="o",
            base_url="https://custom.api.dev/",
            cli_path="/opt/sprite",
            name_prefix="sb-",
            retry_strategy="none",
            max_retries=5,
        )
        assert client._base_url == "https://custom.api.dev"
        assert client._cli_path == "/opt/sprite"
        assert client._name_prefix == "sb-"
        assert client._retry_strategy == "none"
        assert client._max_retries == 5

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_httpx_client_created(self, mock_which):
        client = SpritesClient(token="tok", org="my-org")
        assert client._http is not None
        assert client._http.headers["authorization"] == "Bearer tok"

    @patch("shutil.which", return_value=None)
    def test_raises_when_cli_missing(self, mock_which):
        with pytest.raises(SpritesCLINotFoundError, match="not found"):
            SpritesClient(token="tok", org="my-org")

    @patch("shutil.which", return_value=None)
    def test_cli_not_found_includes_install_hint(self, mock_which):
        with pytest.raises(SpritesCLINotFoundError, match="install.sh"):
            SpritesClient(token="tok", org="my-org")


# ─────────────────────── _prefixed_name ───────────────────────


class TestPrefixedName:
    def test_no_prefix(self):
        client = _make_client(name_prefix="")
        assert client._prefixed_name("alice") == "alice"

    def test_adds_prefix(self):
        client = _make_client(name_prefix="sb-")
        assert client._prefixed_name("alice") == "sb-alice"

    def test_no_double_prefix(self):
        client = _make_client(name_prefix="sb-")
        assert client._prefixed_name("sb-alice") == "sb-alice"


# ─────────────────────── Lifecycle ───────────────────────


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_close(self):
        client = _make_client()
        await client.close()
        assert client._http.is_closed

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with _make_client() as client:
            assert not client._http.is_closed
        assert client._http.is_closed

    @pytest.mark.asyncio
    async def test_context_manager_returns_self(self):
        client = _make_client()
        async with client as ctx:
            assert ctx is client


# ─────────────────────── Retry logic ───────────────────────


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        client = _make_client()
        client._http.request = AsyncMock(return_value=_mock_response(200, {"ok": True}))

        resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200
        assert client._http.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        client = _make_client(max_retries=3)
        client._http.request = AsyncMock(side_effect=[
            _mock_response(500, text="error"),
            _mock_response(500, text="error"),
            _mock_response(200, {"ok": True}),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200
        assert client._http.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_502(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(side_effect=[
            _mock_response(502, text="bad gateway"),
            _mock_response(200, {"ok": True}),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_retries_on_429_with_retry_after(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(side_effect=[
            _mock_response(429, text="rate limited", headers={"retry-after": "2"}),
            _mock_response(200, {"ok": True}),
        ])
        mock_sleep = AsyncMock()
        with patch("asyncio.sleep", mock_sleep):
            resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200
        # Should have used Retry-After value of 2.0
        mock_sleep.assert_called_once_with(2.0)

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        client = _make_client(max_retries=3)
        client._http.request = AsyncMock(return_value=_mock_response(404, text="not found"))

        with pytest.raises(SpritesAPIError) as exc_info:
            await client._request_with_retry("GET", "/test")
        assert exc_info.value.status_code == 404
        assert client._http.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(side_effect=[
            _mock_response(500, text="error"),
            _mock_response(500, text="error"),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SpritesAPIError) as exc_info:
                await client._request_with_retry("GET", "/test")
        assert exc_info.value.status_code == 500
        assert client._http.request.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_when_strategy_none(self):
        client = _make_client(retry_strategy="none", max_retries=3)
        client._http.request = AsyncMock(return_value=_mock_response(500, text="error"))

        with pytest.raises(SpritesAPIError):
            await client._request_with_retry("GET", "/test")
        assert client._http.request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_when_unsafe(self):
        client = _make_client(max_retries=3)
        client._http.request = AsyncMock(return_value=_mock_response(500, text="error"))

        with pytest.raises(SpritesAPIError):
            await client._request_with_retry("POST", "/test", safe_to_retry=False)
        assert client._http.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(side_effect=[
            httpx.ConnectError("refused"),
            _mock_response(200, {"ok": True}),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_connection_error_exhausted(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SpritesAPIError, match="Connection failed"):
                await client._request_with_retry("GET", "/test")

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        client = _make_client(max_retries=2)
        client._http.request = AsyncMock(side_effect=[
            httpx.TimeoutException("timed out"),
            _mock_response(200, {"ok": True}),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await client._request_with_retry("GET", "/test")
        assert resp.status_code == 200


class TestBackoffDelay:
    def test_first_attempt_base_delay(self):
        client = _make_client()
        with patch("random.uniform", return_value=0.0):
            delay = client._backoff_delay(1)
        assert delay == 1.0  # 2^0

    def test_second_attempt_doubles(self):
        client = _make_client()
        with patch("random.uniform", return_value=0.0):
            delay = client._backoff_delay(2)
        assert delay == 2.0  # 2^1

    def test_jitter_added(self):
        client = _make_client()
        with patch("random.uniform", return_value=0.25):
            delay = client._backoff_delay(1)
        assert delay == 1.25  # 1 + 0.25

    def test_retry_after_header_honored(self):
        client = _make_client()
        resp = _mock_response(429, headers={"retry-after": "5"})
        delay = client._backoff_delay(1, resp)
        assert delay == 5.0

    def test_retry_after_capped_at_60(self):
        client = _make_client()
        resp = _mock_response(429, headers={"retry-after": "120"})
        delay = client._backoff_delay(1, resp)
        assert delay == 60.0

    def test_invalid_retry_after_falls_back(self):
        client = _make_client()
        resp = _mock_response(429, headers={"retry-after": "not-a-number"})
        with patch("random.uniform", return_value=0.0):
            delay = client._backoff_delay(1, resp)
        assert delay == 1.0  # falls back to exponential


# ─────────────────────── Sprite CRUD ───────────────────────


class TestSpriteCRUD:
    @pytest.mark.asyncio
    async def test_create_sprite(self):
        client = _make_client(name_prefix="sb-")
        client._http.request = AsyncMock(
            return_value=_mock_response(200, {"name": "sb-alice", "status": "running"})
        )
        result = await client.create_sprite("alice")
        assert result == {"name": "sb-alice", "status": "running"}
        client._http.request.assert_called_once()
        call_args = client._http.request.call_args
        assert call_args[0] == ("POST", "/orgs/test-org/sprites")
        assert call_args[1]["json"] == {"name": "sb-alice"}

    @pytest.mark.asyncio
    async def test_get_sprite(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(200, {"name": "alice", "status": "running"})
        )
        result = await client.get_sprite("alice")
        assert result["name"] == "alice"
        call_args = client._http.request.call_args
        assert call_args[0] == ("GET", "/orgs/test-org/sprites/alice")

    @pytest.mark.asyncio
    async def test_get_sprite_not_found(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(404, text="not found")
        )
        with pytest.raises(SpritesAPIError) as exc_info:
            await client.get_sprite("missing")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_sprite(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(204)
        )
        await client.delete_sprite("alice")  # should not raise
        call_args = client._http.request.call_args
        assert call_args[0] == ("DELETE", "/orgs/test-org/sprites/alice")

    @pytest.mark.asyncio
    async def test_delete_sprite_404_ignored(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(404, text="not found")
        )
        await client.delete_sprite("gone")  # 404 treated as success

    @pytest.mark.asyncio
    async def test_delete_sprite_500_raises(self):
        client = _make_client(retry_strategy="none")
        client._http.request = AsyncMock(
            return_value=_mock_response(500, text="server error")
        )
        with pytest.raises(SpritesAPIError):
            await client.delete_sprite("alice")

    @pytest.mark.asyncio
    async def test_list_sprites(self):
        client = _make_client()
        sprites = [{"name": "a"}, {"name": "b"}]
        client._http.request = AsyncMock(
            return_value=_mock_response(200, sprites)
        )
        result = await client.list_sprites()
        assert result == sprites
        call_args = client._http.request.call_args
        assert call_args[0] == ("GET", "/orgs/test-org/sprites")


# ─────────────────────── Exec ───────────────────────


class TestExec:
    @pytest.mark.asyncio
    async def test_exec_success(self):
        client = _make_client(name_prefix="sb-")
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"hello\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            rc, out, err = await client.exec("alice", "echo hello")

        assert rc == 0
        assert out == "hello\n"
        assert err == ""
        # Verify CLI args
        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        assert args[0] == "sprite"  # cli_path
        assert "sb-alice" in args  # prefixed name
        assert "echo hello" in args

    @pytest.mark.asyncio
    async def test_exec_nonzero_raises(self):
        client = _make_client()
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"command not found")
        mock_proc.returncode = 127

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(SpritesExecError) as exc_info:
                await client.exec("alice", "badcmd")
        assert exc_info.value.return_code == 127
        assert "command not found" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_exec_timeout(self):
        client = _make_client()
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(asyncio.TimeoutError):
                await client.exec("alice", "sleep 999", timeout=1.0)
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_exec_uses_org_flag(self):
        client = _make_client(org="my-org")
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"ok", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client.exec("alice", "ls")

        args = mock_create.call_args[0]
        # Find --org flag and its value
        org_idx = list(args).index("--org")
        assert args[org_idx + 1] == "my-org"


# ─────────────────────── Checkpoints ───────────────────────


class TestCheckpoints:
    @pytest.mark.asyncio
    async def test_create_checkpoint(self):
        client = _make_client(name_prefix="sb-")
        client._http.request = AsyncMock(
            return_value=_mock_response(200, {"id": "chk-1", "label": "before refactor"})
        )
        result = await client.create_checkpoint("alice", label="before refactor")
        assert result["id"] == "chk-1"
        call_args = client._http.request.call_args
        assert call_args[0] == ("POST", "/orgs/test-org/sprites/sb-alice/checkpoints")
        assert call_args[1]["json"] == {"label": "before refactor"}

    @pytest.mark.asyncio
    async def test_create_checkpoint_no_label(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(200, {"id": "chk-1"})
        )
        await client.create_checkpoint("alice")
        call_args = client._http.request.call_args
        assert call_args[1]["json"] == {}

    @pytest.mark.asyncio
    async def test_create_checkpoint_not_retried(self):
        """create_checkpoint is not safe to retry (safe_to_retry=False)."""
        client = _make_client(max_retries=3)
        client._http.request = AsyncMock(
            return_value=_mock_response(500, text="error")
        )
        with pytest.raises(SpritesAPIError):
            await client.create_checkpoint("alice")
        # Only 1 attempt because safe_to_retry=False
        assert client._http.request.call_count == 1

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        client = _make_client()
        checkpoints = [{"id": "chk-1"}, {"id": "chk-2"}]
        client._http.request = AsyncMock(
            return_value=_mock_response(200, checkpoints)
        )
        result = await client.list_checkpoints("alice")
        assert len(result) == 2
        call_args = client._http.request.call_args
        assert call_args[0] == ("GET", "/orgs/test-org/sprites/alice/checkpoints")

    @pytest.mark.asyncio
    async def test_restore_checkpoint(self):
        client = _make_client()
        client._http.request = AsyncMock(
            return_value=_mock_response(200, {"status": "restored"})
        )
        result = await client.restore_checkpoint("alice", "chk-1")
        assert result["status"] == "restored"
        call_args = client._http.request.call_args
        assert call_args[0] == (
            "POST", "/orgs/test-org/sprites/alice/checkpoints/chk-1/restore"
        )

    @pytest.mark.asyncio
    async def test_restore_checkpoint_not_retried(self):
        """restore_checkpoint is not safe to retry (safe_to_retry=False)."""
        client = _make_client(max_retries=3)
        client._http.request = AsyncMock(
            return_value=_mock_response(500, text="error")
        )
        with pytest.raises(SpritesAPIError):
            await client.restore_checkpoint("alice", "chk-1")
        assert client._http.request.call_count == 1
