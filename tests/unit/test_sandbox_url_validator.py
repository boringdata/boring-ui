"""Tests for INTERNAL_SANDBOX_URL validation (bd-1adh.3.3)."""

import pytest
from unittest.mock import AsyncMock, patch
from boring_ui.api.sandbox_url_validator import (
    InternalSandboxURLValidator,
    SandboxURLValidationError,
)


class TestSandboxURLValidator:
    """Tests for INTERNAL_SANDBOX_URL validator."""

    def test_valid_http_url(self):
        """Valid HTTP URL initializes successfully."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")
        assert validator.sandbox_url == "http://internal.local:9000"

    def test_valid_https_url(self):
        """Valid HTTPS URL initializes successfully."""
        validator = InternalSandboxURLValidator("https://internal.local:9000")
        assert validator.sandbox_url == "https://internal.local:9000"

    def test_trailing_slash_removed(self):
        """Trailing slash is removed from URL."""
        validator = InternalSandboxURLValidator("http://internal.local:9000/")
        assert validator.sandbox_url == "http://internal.local:9000"

    def test_empty_url_rejected(self):
        """Empty URL is rejected."""
        with pytest.raises(SandboxURLValidationError, match="cannot be empty"):
            InternalSandboxURLValidator("")

    def test_missing_scheme_rejected(self):
        """URL without scheme is rejected."""
        with pytest.raises(SandboxURLValidationError, match="scheme"):
            InternalSandboxURLValidator("internal.local:9000")

    def test_invalid_scheme_rejected(self):
        """URL with non-http scheme is rejected."""
        with pytest.raises(SandboxURLValidationError, match="must be http or https"):
            InternalSandboxURLValidator("ftp://internal.local:9000")

    def test_missing_hostname_rejected(self):
        """URL without hostname is rejected."""
        with pytest.raises(SandboxURLValidationError, match="missing hostname"):
            InternalSandboxURLValidator("http://")

    def test_co_location_warning_public_domain(self, caplog):
        """Warning logged for public domain."""
        import logging

        caplog.set_level(logging.WARNING)

        validator = InternalSandboxURLValidator(
            "http://sandbox.example.com:9000"
        )

        # Explicitly call co-location check
        validator._validate_co_location_assumption()

        assert "public domain" in caplog.text.lower()

    def test_co_location_info_loopback(self, caplog):
        """Info logged for loopback."""
        import logging

        caplog.set_level(logging.INFO)

        validator = InternalSandboxURLValidator("http://127.0.0.1:9000")

        # Explicitly call co-location check
        validator._validate_co_location_assumption()

        assert "loopback" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check succeeds when service responds 200."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch("boring_ui.api.sandbox_url_validator.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            result = await validator.health_check()

            assert result is True
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure_non_200(self):
        """Health check fails when service returns non-200."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch("boring_ui.api.sandbox_url_validator.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.status_code = 503
            mock_client.get.return_value = mock_response

            result = await validator.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_timeout_raises_error(self):
        """Health check timeout raises SandboxURLValidationError."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch("boring_ui.api.sandbox_url_validator.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            import asyncio

            mock_client.get.side_effect = asyncio.TimeoutError()

            with pytest.raises(SandboxURLValidationError, match="timeout"):
                await validator.health_check()

    @pytest.mark.asyncio
    async def test_health_check_connection_error_raises_error(self):
        """Health check connection error raises SandboxURLValidationError."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch("boring_ui.api.sandbox_url_validator.httpx.AsyncClient") as mock_client_class:
            import httpx

            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.side_effect = httpx.ConnectError(
                "Cannot connect"
            )

            with pytest.raises(SandboxURLValidationError, match="Cannot connect"):
                await validator.health_check()

    @pytest.mark.asyncio
    async def test_validate_startup_success(self):
        """Full startup validation succeeds with reachable service."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch.object(validator, "health_check", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True

            # Should not raise
            await validator.validate_startup()

    @pytest.mark.asyncio
    async def test_validate_startup_fails_on_health_check_error(self):
        """Startup validation fails if health check fails."""
        validator = InternalSandboxURLValidator("http://internal.local:9000")

        with patch.object(validator, "health_check", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = False

            with pytest.raises(SandboxURLValidationError, match="health check failed"):
                await validator.validate_startup()

    def test_from_env_with_url(self):
        """from_env creates validator when URL is set."""
        env = {"INTERNAL_SANDBOX_URL": "http://internal.local:9000"}

        validator = InternalSandboxURLValidator.from_env(env)

        assert validator is not None
        assert validator.sandbox_url == "http://internal.local:9000"

    def test_from_env_without_url(self):
        """from_env returns None when URL is not set."""
        env = {}

        validator = InternalSandboxURLValidator.from_env(env)

        assert validator is None

    def test_from_env_empty_url(self):
        """from_env returns None when URL is empty string."""
        env = {"INTERNAL_SANDBOX_URL": ""}

        validator = InternalSandboxURLValidator.from_env(env)

        assert validator is None

    def test_from_env_whitespace_only(self):
        """from_env returns None when URL is whitespace only."""
        env = {"INTERNAL_SANDBOX_URL": "   "}

        validator = InternalSandboxURLValidator.from_env(env)

        assert validator is None
