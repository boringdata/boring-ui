"""Tests for capability-based route authorization (bd-1adh.6.2)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.testclient import TestClient
from boring_ui.api.capability_decorator import require_capability, get_capability_context
from boring_ui.api.sandbox_auth import CapabilityAuthContext


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    return FastAPI()


@pytest.fixture
def mock_context():
    """Create a mock capability context."""
    return CapabilityAuthContext(
        workspace_id="ws-123",
        operations={"files:read", "files:write", "git:*"},
        jti="token-123",
        issued_at=1234567890,
        expires_at=1234571490,
    )


class TestCapabilityDecorator:
    """Tests for @require_capability decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_with_capability(self, mock_context):
        """Decorator allows request with valid capability."""

        @require_capability("files:read")
        async def route_handler(request: Request):
            return {"status": "ok"}

        # Mock request with context
        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context
        request.method = "GET"
        request.url.path = "/files"

        result = await route_handler(request=request)

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_decorator_rejects_without_context(self):
        """Decorator rejects request without capability context."""

        @require_capability("files:read")
        async def route_handler(request: Request):
            return {"status": "ok"}

        # Mock request without context
        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = None
        request.method = "GET"
        request.url.path = "/files"

        with pytest.raises(HTTPException) as exc_info:
            await route_handler(request=request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_decorator_rejects_insufficient_operation(self, mock_context):
        """Decorator rejects request with insufficient operations."""
        # Update context to NOT have exec permission
        mock_context.operations = {"files:read", "git:read"}

        @require_capability("exec:*")
        async def route_handler(request: Request):
            return {"status": "ok"}

        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context
        request.method = "POST"
        request.url.path = "/exec"

        with pytest.raises(HTTPException) as exc_info:
            await route_handler(request=request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_decorator_allows_wildcard_operation(self, mock_context):
        """Decorator allows request with wildcard operation."""

        @require_capability("git:commit")
        async def route_handler(request: Request):
            return {"status": "ok"}

        # Context has git:* which covers git:commit
        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context
        request.method = "POST"
        request.url.path = "/git/commit"

        result = await route_handler(request=request)

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_decorator_allows_multiple_operations(self, mock_context):
        """Decorator allows request if any required operation matches."""

        @require_capability(["exec:*", "files:read"])
        async def route_handler(request: Request):
            return {"status": "ok"}

        # Context doesn't have exec but has files:read
        mock_context.operations = {"files:read", "git:read"}

        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context
        request.method = "GET"
        request.url.path = "/files"

        result = await route_handler(request=request)

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_decorator_no_operation_required(self, mock_context):
        """Decorator allows any capability when no operation specified."""

        @require_capability()
        async def route_handler(request: Request):
            return {"status": "ok"}

        request = AsyncMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context
        request.method = "GET"
        request.url.path = "/health"

        result = await route_handler(request=request)

        assert result == {"status": "ok"}


class TestGetCapabilityContext:
    """Tests for get_capability_context helper."""

    def test_get_context_success(self, mock_context):
        """Returns context when available."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = mock_context

        context = get_capability_context(request)

        assert context == mock_context

    def test_get_context_missing_raises_401(self):
        """Raises 401 when context not available."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.capability_context = None

        with pytest.raises(HTTPException) as exc_info:
            get_capability_context(request)

        assert exc_info.value.status_code == 401
