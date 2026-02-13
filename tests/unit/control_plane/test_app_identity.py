"""Host → app_id resolver tests.

Bead: bd-223o.8.1 (I1)

Tests:
  - Exact host match (case-insensitive)
  - Port stripping (standard, high, IPv6)
  - Wildcard fallback
  - Default app_id fallback
  - No match raises KeyError
  - Config lookup by app_id
  - Resolution source tracking
  - Multiple apps on different hosts
"""

from __future__ import annotations

import pytest

from control_plane.app.identity.resolver import (
    AppConfig,
    AppIdentityResolver,
    AppResolution,
)

# ── Fixtures ──────────────────────────────────────────────────────────

BORING_CONFIG = AppConfig(
    app_id='boring-ui',
    name='Boring UI',
    logo='/assets/boring-ui-logo.svg',
    default_release_id='2026-02-13.1',
)

ACME_CONFIG = AppConfig(
    app_id='acme-app',
    name='Acme App',
    logo='/assets/acme-logo.png',
    default_release_id='2026-01-01.1',
)


@pytest.fixture
def resolver():
    return AppIdentityResolver(
        host_map={
            'boring-ui.example.com': 'boring-ui',
            'acme.example.com': 'acme-app',
            'localhost': 'boring-ui',
        },
        app_configs={
            'boring-ui': BORING_CONFIG,
            'acme-app': ACME_CONFIG,
        },
    )


@pytest.fixture
def wildcard_resolver():
    return AppIdentityResolver(
        host_map={
            '*': 'boring-ui',
        },
        app_configs={
            'boring-ui': BORING_CONFIG,
        },
    )


@pytest.fixture
def default_resolver():
    return AppIdentityResolver(
        host_map={},
        app_configs={'boring-ui': BORING_CONFIG},
        default_app_id='boring-ui',
    )


# =====================================================================
# Exact host match
# =====================================================================


class TestExactHostMatch:
    def test_exact_match(self, resolver):
        result = resolver.resolve('boring-ui.example.com')
        assert result.app_id == 'boring-ui'
        assert result.source == 'exact'
        assert result.config == BORING_CONFIG

    def test_case_insensitive(self, resolver):
        result = resolver.resolve('Boring-UI.Example.COM')
        assert result.app_id == 'boring-ui'
        assert result.source == 'exact'

    def test_different_host_resolves_different_app(self, resolver):
        result = resolver.resolve('acme.example.com')
        assert result.app_id == 'acme-app'
        assert result.config == ACME_CONFIG

    def test_localhost(self, resolver):
        result = resolver.resolve('localhost')
        assert result.app_id == 'boring-ui'


# =====================================================================
# Port stripping
# =====================================================================


class TestPortStripping:
    def test_strips_standard_port(self, resolver):
        result = resolver.resolve('boring-ui.example.com:443')
        assert result.app_id == 'boring-ui'

    def test_strips_high_port(self, resolver):
        result = resolver.resolve('localhost:5173')
        assert result.app_id == 'boring-ui'

    def test_strips_port_8080(self, resolver):
        result = resolver.resolve('boring-ui.example.com:8080')
        assert result.app_id == 'boring-ui'

    def test_ipv6_bracket_notation(self):
        resolver = AppIdentityResolver(
            host_map={'::1': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        result = resolver.resolve('[::1]:8080')
        assert result.app_id == 'boring-ui'

    def test_ipv6_without_port(self):
        resolver = AppIdentityResolver(
            host_map={'::1': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        result = resolver.resolve('[::1]')
        assert result.app_id == 'boring-ui'


# =====================================================================
# Wildcard fallback
# =====================================================================


class TestWildcardFallback:
    def test_wildcard_matches_any_host(self, wildcard_resolver):
        result = wildcard_resolver.resolve('anything.example.com')
        assert result.app_id == 'boring-ui'
        assert result.source == 'wildcard'

    def test_wildcard_matches_localhost(self, wildcard_resolver):
        result = wildcard_resolver.resolve('localhost:3000')
        assert result.app_id == 'boring-ui'
        assert result.source == 'wildcard'

    def test_exact_match_takes_precedence_over_wildcard(self):
        resolver = AppIdentityResolver(
            host_map={
                'specific.example.com': 'specific-app',
                '*': 'default-app',
            },
        )
        result = resolver.resolve('specific.example.com')
        assert result.app_id == 'specific-app'
        assert result.source == 'exact'

    def test_wildcard_used_when_no_exact_match(self):
        resolver = AppIdentityResolver(
            host_map={
                'specific.example.com': 'specific-app',
                '*': 'default-app',
            },
        )
        result = resolver.resolve('other.example.com')
        assert result.app_id == 'default-app'
        assert result.source == 'wildcard'


# =====================================================================
# Default fallback
# =====================================================================


class TestDefaultFallback:
    def test_default_when_no_match(self, default_resolver):
        result = default_resolver.resolve('unknown.example.com')
        assert result.app_id == 'boring-ui'
        assert result.source == 'default'
        assert result.config == BORING_CONFIG

    def test_default_with_port(self, default_resolver):
        result = default_resolver.resolve('unknown.example.com:9999')
        assert result.app_id == 'boring-ui'
        assert result.source == 'default'


# =====================================================================
# No match
# =====================================================================


class TestNoMatch:
    def test_raises_key_error_when_no_mapping(self):
        resolver = AppIdentityResolver(host_map={})
        with pytest.raises(KeyError, match='No app_id mapping'):
            resolver.resolve('unknown.example.com')

    def test_raises_key_error_with_host_in_message(self):
        resolver = AppIdentityResolver(host_map={})
        with pytest.raises(KeyError, match='unknown.example.com'):
            resolver.resolve('unknown.example.com')


# =====================================================================
# Config lookup
# =====================================================================


class TestConfigLookup:
    def test_get_config_by_app_id(self, resolver):
        config = resolver.get_config('boring-ui')
        assert config == BORING_CONFIG

    def test_get_config_unknown_returns_none(self, resolver):
        config = resolver.get_config('nonexistent')
        assert config is None

    def test_resolution_includes_config(self, resolver):
        result = resolver.resolve('acme.example.com')
        assert result.config is not None
        assert result.config.app_id == 'acme-app'
        assert result.config.name == 'Acme App'
        assert result.config.default_release_id == '2026-01-01.1'

    def test_resolution_without_config(self):
        resolver = AppIdentityResolver(
            host_map={'example.com': 'no-config-app'},
        )
        result = resolver.resolve('example.com')
        assert result.app_id == 'no-config-app'
        assert result.config is None


# =====================================================================
# Resolution result structure
# =====================================================================


class TestResolutionResult:
    def test_is_named_tuple(self, resolver):
        result = resolver.resolve('boring-ui.example.com')
        assert isinstance(result, AppResolution)
        assert isinstance(result, tuple)

    def test_unpacking(self, resolver):
        app_id, source, config = resolver.resolve('boring-ui.example.com')
        assert app_id == 'boring-ui'
        assert source == 'exact'
        assert config == BORING_CONFIG


# =====================================================================
# AppConfig dataclass
# =====================================================================


class TestAppConfig:
    def test_frozen(self):
        config = AppConfig(app_id='test', name='Test')
        with pytest.raises(AttributeError):
            config.app_id = 'other'

    def test_defaults(self):
        config = AppConfig(app_id='test', name='Test')
        assert config.logo == ''
        assert config.default_release_id == ''

    def test_equality(self):
        a = AppConfig(app_id='x', name='X', logo='l', default_release_id='r')
        b = AppConfig(app_id='x', name='X', logo='l', default_release_id='r')
        assert a == b


# =====================================================================
# Registered hosts inspection
# =====================================================================


class TestRegisteredHosts:
    def test_returns_copy(self, resolver):
        hosts = resolver.registered_hosts
        hosts['injected'] = 'should_not_affect_resolver'
        assert 'injected' not in resolver.registered_hosts

    def test_lists_all_hosts(self, resolver):
        hosts = resolver.registered_hosts
        assert 'boring-ui.example.com' in hosts
        assert 'acme.example.com' in hosts
        assert 'localhost' in hosts
