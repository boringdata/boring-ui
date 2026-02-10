"""Tests for SpritesClient base structure and exception hierarchy.

Covers bd-1ni.1.1: exception classes, __init__ validation,
name prefixing, lifecycle (close, context manager).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from boring_ui.api.modules.sandbox.providers.sprites_client import (
    SpritesAPIError,
    SpritesClient,
    SpritesClientError,
    SpritesCLINotFoundError,
    SpritesExecError,
)


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
        """All specific errors can be caught with SpritesClientError."""
        for exc_cls in (SpritesCLINotFoundError, SpritesAPIError, SpritesExecError):
            with pytest.raises(SpritesClientError):
                if exc_cls is SpritesAPIError:
                    raise exc_cls(500, "fail")
                elif exc_cls is SpritesExecError:
                    raise exc_cls(1, "", "fail")
                else:
                    raise exc_cls("missing")


# ─────────────────────── SpritesAPIError ───────────────────────


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


# ─────────────────────── SpritesExecError ───────────────────────


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
        # str() should truncate to 200 chars of detail
        assert len(str(err)) < 300


# ─────────────────────── SpritesCLINotFoundError ───────────────────────


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
            token="t",
            org="o",
            base_url="https://custom.api.dev/",
            cli_path="/opt/sprite",
            name_prefix="sb-",
            retry_strategy="none",
            max_retries=5,
        )
        assert client._base_url == "https://custom.api.dev"  # trailing slash stripped
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
    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_no_prefix(self, mock_which):
        client = SpritesClient(token="t", org="o", name_prefix="")
        assert client._prefixed_name("alice") == "alice"

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_adds_prefix(self, mock_which):
        client = SpritesClient(token="t", org="o", name_prefix="sb-")
        assert client._prefixed_name("alice") == "sb-alice"

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_no_double_prefix(self, mock_which):
        client = SpritesClient(token="t", org="o", name_prefix="sb-")
        assert client._prefixed_name("sb-alice") == "sb-alice"


# ─────────────────────── Lifecycle ───────────────────────


class TestLifecycle:
    @pytest.mark.asyncio
    @patch("shutil.which", return_value="/usr/bin/sprite")
    async def test_close(self, mock_which):
        client = SpritesClient(token="t", org="o")
        await client.close()
        assert client._http.is_closed

    @pytest.mark.asyncio
    @patch("shutil.which", return_value="/usr/bin/sprite")
    async def test_context_manager(self, mock_which):
        async with SpritesClient(token="t", org="o") as client:
            assert not client._http.is_closed
        assert client._http.is_closed

    @pytest.mark.asyncio
    @patch("shutil.which", return_value="/usr/bin/sprite")
    async def test_context_manager_returns_self(self, mock_which):
        client = SpritesClient(token="t", org="o")
        async with client as ctx:
            assert ctx is client
