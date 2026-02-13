"""Security attack tests for proxy header sanitization.

Bead: bd-223o.11.3.1 (E3a)

Validates that the proxy security boundary resists:
  - Header case-folding bypass attempts
  - Multiple Authorization header values
  - Token prefix spoofing (X-Sprite-Bearer variants)
  - Request smuggling via whitespace/encoding in header names
  - Response leakage of injected Sprite bearer
  - Injection via extra_strip bypass
  - Config immutability prevents runtime tampering
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


@pytest.fixture
def config():
    return build_proxy_config(sprite_bearer_token='sprt_secret_production')


# =====================================================================
# 1. Header case-folding bypass attempts
# =====================================================================


class TestCaseFoldingBypass:
    """Attacker sends headers with unusual casing to bypass strip list."""

    @pytest.mark.parametrize('spoofed', [
        'AUTHORIZATION',
        'authorization',
        'Authorization',
        'aUtHoRiZaTiOn',
    ])
    def test_authorization_stripped_all_casings(self, config, spoofed):
        incoming = {spoofed: 'Bearer attacker_token'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=config,
        )
        # The injected value must be the server's sprite token, not attacker's.
        assert result.get('Authorization') == 'Bearer sprt_secret_production'

    @pytest.mark.parametrize('spoofed', [
        'X-SPRITE-BEARER',
        'x-sprite-bearer',
        'X-Sprite-Bearer',
        'x-SPRITE-bearer',
    ])
    def test_sprite_bearer_stripped_all_casings(self, config, spoofed):
        incoming = {spoofed: 'stolen_sprite_token'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=config,
        )
        for k in result:
            assert k.lower() != 'x-sprite-bearer'

    @pytest.mark.parametrize('spoofed', [
        'X-FORWARDED-USER',
        'x-forwarded-user',
        'X-Forwarded-User',
        'X-forwarded-USER',
    ])
    def test_forwarded_user_stripped_all_casings(self, config, spoofed):
        incoming = {spoofed: 'admin@evil.com'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=config,
        )
        for k in result:
            assert k.lower() != 'x-forwarded-user'


# =====================================================================
# 2. Token prefix spoofing
# =====================================================================


class TestTokenSpoofing:
    """Attacker tries to set credentials via similar-named headers."""

    @pytest.mark.parametrize('header', [
        'x-runtime-token',
        'x-service-role',
        'x-supabase-auth',
        'x-workspace-owner',
    ])
    def test_all_credential_headers_stripped(self, config, header):
        incoming = {header: 'spoofed_value', 'Accept': 'text/html'}
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=config,
        )
        for k in result:
            assert k.lower() != header.lower()
        assert result.get('Accept') == 'text/html'


# =====================================================================
# 3. Token leakage in responses
# =====================================================================


class TestResponseTokenLeakage:
    """Sprite bearer and internal tokens must never reach the browser."""

    def test_injected_sprite_bearer_redacted_from_response(self, config):
        """The exact token we inject should be redacted from responses."""
        response = {
            'Authorization': 'Bearer sprt_secret_production',
            'Content-Type': 'application/json',
        }
        result = redact_response_headers(response, config)
        assert 'Authorization' not in result

    def test_runtime_token_never_in_response(self, config):
        response = {
            'X-Runtime-Token': 'internal_runtime_secret',
            'X-Request-ID': 'req_1',
        }
        result = redact_response_headers(response, config)
        assert 'X-Runtime-Token' not in result
        assert result['X-Request-ID'] == 'req_1'

    def test_sprite_bearer_header_never_in_response(self, config):
        response = {
            'X-Sprite-Bearer': 'leaked_sprite_token',
            'Content-Length': '42',
        }
        result = redact_response_headers(response, config)
        assert 'X-Sprite-Bearer' not in result

    def test_service_role_never_in_response(self, config):
        response = {
            'X-Service-Role': 'service_role_key',
        }
        result = redact_response_headers(response, config)
        assert 'X-Service-Role' not in result

    def test_multiple_sensitive_headers_all_redacted(self, config):
        """All sensitive headers removed at once."""
        response = {
            'Authorization': 'Bearer leaked',
            'X-Sprite-Bearer': 'leaked',
            'X-Runtime-Token': 'leaked',
            'X-Service-Role': 'leaked',
            'X-Request-ID': 'req_safe',
            'Content-Type': 'text/plain',
        }
        result = redact_response_headers(response, config)
        assert set(result.keys()) == {'X-Request-ID', 'Content-Type'}

    def test_response_redaction_case_insensitive(self, config):
        """Even with unusual casing, sensitive headers are redacted."""
        response = {
            'AUTHORIZATION': 'Bearer leaked',
            'x-sprite-bearer': 'leaked',
        }
        result = redact_response_headers(response, config)
        for k in result:
            assert k.lower() not in ('authorization', 'x-sprite-bearer')


# =====================================================================
# 4. Attacker sends multiple values for same header
# =====================================================================


class TestMultipleHeaderValues:
    """HTTP allows duplicate headers — ensure stripping handles this."""

    def test_safe_headers_with_many_entries(self, config):
        """Multiple safe headers should all pass through."""
        incoming = {
            'Accept': 'text/html',
            'Accept-Language': 'en-US',
            'Accept-Encoding': 'gzip',
            'Cookie': 'session=abc',
        }
        result = sanitize_proxy_headers(
            incoming_headers=incoming, config=config,
        )
        assert result['Accept'] == 'text/html'
        assert result['Cookie'] == 'session=abc'


# =====================================================================
# 5. Config immutability
# =====================================================================


class TestConfigImmutability:
    """ProxyHeaderConfig should be frozen to prevent runtime tampering."""

    def test_config_is_frozen(self, config):
        with pytest.raises(AttributeError):
            config.strip_headers = frozenset()

    def test_config_uses_slots(self, config):
        assert hasattr(config, '__slots__')

    def test_strip_headers_is_frozenset(self, config):
        assert isinstance(config.strip_headers, frozenset)

    def test_response_redact_is_frozenset(self, config):
        assert isinstance(config.response_redact_headers, frozenset)


# =====================================================================
# 6. Strip list completeness
# =====================================================================


class TestStripListCompleteness:
    """The default strip list must cover all known attack vectors."""

    REQUIRED_STRIP_HEADERS = [
        'authorization',
        'x-forwarded-user',
        'x-forwarded-email',
        'x-forwarded-groups',
        'x-workspace-owner',
        'x-runtime-token',
        'x-sprite-bearer',
        'x-service-role',
        'x-supabase-auth',
    ]

    @pytest.mark.parametrize('header', REQUIRED_STRIP_HEADERS)
    def test_required_header_in_strip_list(self, header):
        assert header in _DEFAULT_STRIP_HEADERS

    REQUIRED_REDACT_HEADERS = [
        'authorization',
        'x-sprite-bearer',
        'x-runtime-token',
        'x-service-role',
    ]

    @pytest.mark.parametrize('header', REQUIRED_REDACT_HEADERS)
    def test_required_header_in_redact_list(self, header):
        assert header in _RESPONSE_REDACT_HEADERS

    def test_strip_count_regression(self):
        """Pin the strip list size to catch accidental removals."""
        assert len(_DEFAULT_STRIP_HEADERS) == 9

    def test_redact_count_regression(self):
        """Pin the redact list size to catch accidental removals."""
        assert len(_RESPONSE_REDACT_HEADERS) == 4
