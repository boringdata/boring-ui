"""Tests for hosted client payload semantics (bd-2j57.4.1).

Verifies that file content and command payloads are sent in request body
instead of query parameters to prevent:
- URL length truncation (browsers/servers limit URLs to ~8KB)
- Content leakage into access logs
- Special character encoding issues
"""

import pytest
from unittest.mock import AsyncMock, Mock, call
from boring_ui.api.modules.sandbox.hosted_client import (
    HostedSandboxClient,
    SandboxClientConfig,
)


class TestWriteFilePayloadSemantics:
    """Tests for write_file payload location."""

    @pytest.mark.asyncio
    async def test_write_file_sends_content_in_json_body(self):
        """File content is sent in JSON body, not query params."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Mock the _request method to capture call args
        client._request = AsyncMock(return_value={"path": "test.txt", "size": 5, "written": True})

        await client.write_file(
            path="test.txt",
            content="hello",
            capability_token="token123",
            request_id="req1",
        )

        # Verify _request was called with json_body, NOT params
        client._request.assert_called_once()
        call_args = client._request.call_args

        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/internal/v1/files/write"

        # Content should be in json_body
        assert call_args[1]["json_body"] == {"path": "test.txt", "content": "hello"}

        # Content should NOT be in params
        assert call_args[1].get("params") is None

    @pytest.mark.asyncio
    async def test_write_file_large_content(self):
        """Large content (>8KB) is handled correctly in request body."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Create large content (10KB)
        large_content = "x" * 10240

        client._request = AsyncMock(
            return_value={"path": "large.txt", "size": 10240, "written": True}
        )

        await client.write_file(
            path="large.txt",
            content=large_content,
            capability_token="token123",
        )

        # Verify content is in json_body (not params which would truncate)
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["content"] == large_content
        assert len(call_args[1]["json_body"]["content"]) == 10240

    @pytest.mark.asyncio
    async def test_write_file_special_characters(self):
        """Special characters are properly encoded in JSON body."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Content with special chars that would break URL encoding
        special_content = 'Line 1\nLine 2\tTab\r\nWindows\n"Quotes"\n\'Singles\'\n&amp;&lt;&gt;'

        client._request = AsyncMock(
            return_value={"path": "special.txt", "size": len(special_content), "written": True}
        )

        await client.write_file(
            path="special.txt",
            content=special_content,
            capability_token="token123",
        )

        # Verify special chars are preserved in json_body
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["content"] == special_content
        assert "\n" in call_args[1]["json_body"]["content"]
        assert "\t" in call_args[1]["json_body"]["content"]

    @pytest.mark.asyncio
    async def test_write_file_unicode_content(self):
        """Unicode content is properly handled in JSON body."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Unicode content
        unicode_content = "Hello 世界 🌍 مرحبا שלום"

        client._request = AsyncMock(
            return_value={"path": "unicode.txt", "size": len(unicode_content), "written": True}
        )

        await client.write_file(
            path="unicode.txt",
            content=unicode_content,
            capability_token="token123",
        )

        # Verify unicode is preserved
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["content"] == unicode_content

    @pytest.mark.asyncio
    async def test_write_file_empty_content(self):
        """Empty content is handled correctly."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        client._request = AsyncMock(
            return_value={"path": "empty.txt", "size": 0, "written": True}
        )

        await client.write_file(
            path="empty.txt",
            content="",
            capability_token="token123",
        )

        # Verify empty string is in json_body
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["content"] == ""


class TestExecRunPayloadSemantics:
    """Tests for exec_run payload location."""

    @pytest.mark.asyncio
    async def test_exec_run_sends_command_in_json_body(self):
        """Command is sent in JSON body, not query params."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        client._request = AsyncMock(
            return_value={
                "command": "echo hello",
                "exit_code": 0,
                "stdout": "hello",
                "stderr": "",
            }
        )

        await client.exec_run(
            command="echo hello",
            timeout_seconds=30,
            capability_token="token123",
        )

        # Verify _request was called with json_body, NOT params
        call_args = client._request.call_args

        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/internal/v1/exec/run"

        # Command should be in json_body
        assert call_args[1]["json_body"] == {
            "command": "echo hello",
            "timeout_seconds": 30,
        }

        # Command should NOT be in params
        assert call_args[1].get("params") is None

    @pytest.mark.asyncio
    async def test_exec_run_long_command(self):
        """Long commands are handled correctly in request body."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Long command that would exceed URL limits
        long_command = "python -c '" + "x" * 9000 + "'"

        client._request = AsyncMock(
            return_value={
                "command": long_command,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
            }
        )

        await client.exec_run(
            command=long_command,
            timeout_seconds=60,
            capability_token="token123",
        )

        # Verify long command is in json_body
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["command"] == long_command
        assert len(call_args[1]["json_body"]["command"]) > 9000

    @pytest.mark.asyncio
    async def test_exec_run_command_with_special_chars(self):
        """Commands with special characters are properly encoded."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        # Command with shell special chars
        special_command = 'bash -c "echo \\"hello\\" && ls -la | grep .txt"'

        client._request = AsyncMock(
            return_value={
                "command": special_command,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
            }
        )

        await client.exec_run(
            command=special_command,
            timeout_seconds=30,
            capability_token="token123",
        )

        # Verify special chars are preserved
        call_args = client._request.call_args
        assert call_args[1]["json_body"]["command"] == special_command


class TestReadFilePayloadSemantics:
    """Tests for read_file payload location (path in query is OK)."""

    @pytest.mark.asyncio
    async def test_read_file_path_in_query_params(self):
        """Read operations can use query params since path is short."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        client._request = AsyncMock(
            return_value={"path": "test.txt", "content": "hello", "size": 5}
        )

        await client.read_file(
            path="test.txt",
            capability_token="token123",
        )

        # For GET requests, params are acceptable (no large payload)
        call_args = client._request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[1]["params"] == {"path": "test.txt"}


class TestListFilesPayloadSemantics:
    """Tests for list_files payload location (path in query is OK)."""

    @pytest.mark.asyncio
    async def test_list_files_path_in_query_params(self):
        """List operations can use query params since path is short."""
        config = SandboxClientConfig(internal_url="http://test:8000")
        client = HostedSandboxClient(config)

        client._request = AsyncMock(
            return_value={"path": ".", "files": [{"name": "test.txt", "type": "file"}]}
        )

        await client.list_files(
            path=".",
            capability_token="token123",
        )

        # For GET requests, params are acceptable
        call_args = client._request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[1]["params"] == {"path": "."}
