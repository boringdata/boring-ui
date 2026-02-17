"""Tests for proxy security boundary enforcement.

Bead: bd-223o.11.3 (E3)

Validates that the private proxy correctly:
  - Strips untrusted identity headers from browser requests.
  - Injects Sprite bearer token server-side only.
  - Propagates X-Request-ID and session context to runtime.
  - Redacts sensitive headers from runtime responses.
  - Never leaks credentials to the browser.
"""

from __future__ import annotations

import pytest

from control_plane.app.routing.proxy_security import (
    ProxyHeaderConfig,
    _DEFAULT_STRIP_HEADERS,
    _RESPONSE_REDACT_HEADERS,
    build_proxy_config,
    redact_response_headers,
    sanitize_proxy_headers,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sprite_config() -> ProxyHeaderConfig:
    """Config with Sprite bearer injection."""
    return build_proxy_config(sprite_bearer_token='sprt_secret_123')


@pytest.fixture
def no_auth_config() -> ProxyHeaderConfig:
    """Config without Sprite bearer (local/test mode)."""
    return build_proxy_config(sprite_bearer_token=None)


# =====================================================================
# Header stripping — untrusted headers removed
# =====================================================================


class TestHeaderStripping:
    """Untrusted identity headers must be stripped before proxying."""

    @pytest.mark.parametrize('header', [
        'Authorization',
        'X-Forwarded-User',
        'X-Forwarded-Email',
        'X-Forwarded-Groups',
        'X-Workspace-Owner',
        'X-Runtime-Token',
        'X-Sprite-Bearer',
        'X-Service-Role',
        'X-Supabase-Auth',
    ])
    def test_untrusted_header_stripped(self, sprite_config, header):
        incoming = {header: 'spoofed_value', 'Accept': 'application/json'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=sprite_config,
        )
        # The spoofed header should not appear (case-insensitive).
        for k in result:
            assert k.lower() != header.lower() or k == 'Authorization', (
                f'Spoofed {header} should be stripped (Authorization replaced by inject)'
            )

    def test_safe_headers_preserved(self, sprite_config):
        incoming = {
            'Accept': 'application/json',
            'Content-Type': 'text/plain',
            'User-Agent': 'test/1.0',
        }
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=sprite_config,
        )
        assert result['Accept'] == 'application/json'
        assert result['Content-Type'] == 'text/plain'
        assert result['User-Agent'] == 'test/1.0'

    def test_case_insensitive_stripping(self, sprite_config):
        """Header matching is case-insensitive per HTTP spec."""
        incoming = {'x-forwarded-user': 'evil', 'X-FORWARDED-EMAIL': 'evil'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=sprite_config,
        )
        for k in result:
            assert k.lower() not in ('x-forwarded-user', 'x-forwarded-email')


# =====================================================================
# Sprite bearer injection
# =====================================================================


class TestBearerInjection:
    """Sprite bearer token must be injected server-side."""

    def test_bearer_injected_when_configured(self, sprite_config):
        result = sanitize_proxy_headers(
            incoming_headers={}, config=sprite_config,
        )
        assert result['Authorization'] == 'Bearer sprt_secret_123'

    def test_bearer_replaces_spoofed_auth(self, sprite_config):
        """A browser-provided Authorization header is overwritten."""
        incoming = {'Authorization': 'Bearer fake_token'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=sprite_config,
        )
        assert result['Authorization'] == 'Bearer sprt_secret_123'

    def test_no_bearer_in_local_mode(self, no_auth_config):
        result = sanitize_proxy_headers(
            incoming_headers={}, config=no_auth_config,
        )
        assert 'Authorization' not in result


# =====================================================================
# Context propagation
# =====================================================================


class TestContextPropagation:
    """X-Request-ID, X-Session-ID, and X-Workspace-ID propagated."""

    def test_request_id_propagated(self, sprite_config):
        result = sanitize_proxy_headers(
            incoming_headers={},
            config=sprite_config,
            request_id='req_abc',
        )
        assert result['X-Request-ID'] == 'req_abc'

    def test_session_id_propagated(self, sprite_config):
        result = sanitize_proxy_headers(
            incoming_headers={},
            config=sprite_config,
            session_id='sess_xyz',
        )
        assert result['X-Session-ID'] == 'sess_xyz'

    def test_workspace_id_propagated(self, sprite_config):
        result = sanitize_proxy_headers(
            incoming_headers={},
            config=sprite_config,
            workspace_id='ws_123',
        )
        assert result['X-Workspace-ID'] == 'ws_123'

    def test_none_context_not_set(self, sprite_config):
        result = sanitize_proxy_headers(
            incoming_headers={},
            config=sprite_config,
            request_id=None,
            session_id=None,
            workspace_id=None,
        )
        assert 'X-Request-ID' not in result
        assert 'X-Session-ID' not in result
        assert 'X-Workspace-ID' not in result


# =====================================================================
# Response header redaction
# =====================================================================


class TestResponseRedaction:
    """Sensitive headers must be removed from runtime responses."""

    def test_authorization_redacted(self, sprite_config):
        response_headers = {
            'Authorization': 'Bearer sprt_secret_123',
            'Content-Type': 'application/json',
        }
        result = redact_response_headers(response_headers, sprite_config)
        assert 'Authorization' not in result
        assert result['Content-Type'] == 'application/json'

    @pytest.mark.parametrize('header', [
        'Authorization',
        'X-Sprite-Bearer',
        'X-Runtime-Token',
        'X-Service-Role',
    ])
    def test_sensitive_response_header_redacted(self, sprite_config, header):
        result = redact_response_headers(
            {header: 'secret_value', 'X-Request-ID': 'req_1'},
            sprite_config,
        )
        for k in result:
            assert k.lower() != header.lower()

    def test_safe_response_headers_preserved(self, sprite_config):
        response_headers = {
            'Content-Type': 'text/html',
            'X-Request-ID': 'req_propagated',
            'Cache-Control': 'no-store',
        }
        result = redact_response_headers(response_headers, sprite_config)
        assert result == response_headers


# =====================================================================
# Configuration builder
# =====================================================================


class TestBuildProxyConfig:
    """build_proxy_config produces correct configuration."""

    def test_with_sprite_bearer(self):
        config = build_proxy_config(sprite_bearer_token='sprt_token_1')
        assert config.inject_headers == {'Authorization': 'Bearer sprt_token_1'}
        assert config.strip_headers == _DEFAULT_STRIP_HEADERS

    def test_without_sprite_bearer(self):
        config = build_proxy_config(sprite_bearer_token=None)
        assert config.inject_headers == {}

    def test_extra_strip_headers(self):
        config = build_proxy_config(
            extra_strip_headers=frozenset({'x-custom-dangerous'}),
        )
        assert 'x-custom-dangerous' in config.strip_headers
        # Default headers still present.
        assert 'authorization' in config.strip_headers

    def test_default_strip_covers_all_identity_headers(self):
        """All known identity spoofing vectors are in the default strip set."""
        for header in (
            'authorization', 'x-forwarded-user', 'x-forwarded-email',
            'x-forwarded-groups', 'x-workspace-owner', 'x-runtime-token',
            'x-sprite-bearer', 'x-service-role', 'x-supabase-auth',
        ):
            assert header in _DEFAULT_STRIP_HEADERS

    def test_response_redact_covers_credential_headers(self):
        """Credential headers are in the response redact set."""
        for header in (
            'authorization', 'x-sprite-bearer',
            'x-runtime-token', 'x-service-role',
        ):
            assert header in _RESPONSE_REDACT_HEADERS


# =====================================================================
# End-to-end: full proxy header flow
# =====================================================================


class TestEndToEndProxyFlow:
    """Complete request → sanitize → proxy → redact → response flow."""

    def test_full_flow(self):
        config = build_proxy_config(sprite_bearer_token='sprt_live_token')

        # Simulate browser request with spoofed headers.
        browser_headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer user_jwt_fake',
            'X-Forwarded-User': 'attacker@evil.com',
            'X-Sprite-Bearer': 'stolen_token',
            'Cookie': 'boring_session=abc123',
        }

        # Sanitize for proxy.
        proxy_headers = sanitize_proxy_headers(
            incoming_headers=browser_headers,
            config=config,
            request_id='req_e2e_1',
            session_id='sess_e2e_1',
            workspace_id='ws_target',
        )

        # Verify: spoofed identity headers removed.
        assert proxy_headers.get('X-Forwarded-User') is None
        assert proxy_headers.get('X-Sprite-Bearer') is None

        # Verify: server-side bearer injected.
        assert proxy_headers['Authorization'] == 'Bearer sprt_live_token'

        # Verify: context propagated.
        assert proxy_headers['X-Request-ID'] == 'req_e2e_1'
        assert proxy_headers['X-Session-ID'] == 'sess_e2e_1'
        assert proxy_headers['X-Workspace-ID'] == 'ws_target'

        # Verify: safe headers preserved.
        assert proxy_headers['Accept'] == 'application/json'
        assert proxy_headers['Cookie'] == 'boring_session=abc123'

        # Simulate runtime response with leaked credential.
        runtime_response = {
            'Content-Type': 'application/json',
            'X-Request-ID': 'req_e2e_1',
            'Authorization': 'Bearer sprt_live_token',
            'X-Runtime-Token': 'internal_only',
        }

        # Redact before returning to browser.
        browser_response = redact_response_headers(runtime_response, config)
        assert 'Authorization' not in browser_response
        assert 'X-Runtime-Token' not in browser_response
        assert browser_response['Content-Type'] == 'application/json'
        assert browser_response['X-Request-ID'] == 'req_e2e_1'
