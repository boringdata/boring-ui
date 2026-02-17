"""Tests for per-environment configuration and callback URL alignment.

Bead: bd-223o.3 (P3)

Validates:
  - EnvironmentConfig immutability and environment properties
  - load_environment_config from env vars and explicit args
  - Callback URL derivation: public_url + /auth/callback
  - Callback URL consistency validation
  - TLS enforcement: HTTPS required for non-local environments
  - CORS origin defaults per environment
  - Error handling for invalid configuration
  - Identity loader: app_identity.json → AppIdentityResolver
"""

from __future__ import annotations

import json
import os

import pytest

from control_plane.app.config.environment import (
    EnvironmentConfig,
    EnvironmentConfigError,
    derive_supabase_callback_url,
    load_environment_config,
    validate_callback_url_consistency,
)
from control_plane.app.identity.loader import (
    IdentityConfigError,
    load_identity_config,
)
from control_plane.app.identity.resolver import AppIdentityResolver


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def _clean_env(monkeypatch):
    """Remove all environment config vars for isolated tests."""
    for var in [
        'ENVIRONMENT',
        'PUBLIC_URL',
        'CORS_ORIGINS',
        'SUPABASE_CALLBACK_URL',
        'APP_IDENTITY_CONFIG',
    ]:
        monkeypatch.delenv(var, raising=False)


# =====================================================================
# 1. EnvironmentConfig immutability and properties
# =====================================================================


class TestEnvironmentConfig:

    def test_frozen_dataclass(self):
        cfg = EnvironmentConfig(
            environment='local',
            public_url='http://localhost:8000',
            supabase_callback_url='http://localhost:8000/auth/callback',
            cookie_secure=False,
            cors_origins=('http://localhost:5173',),
        )
        with pytest.raises(AttributeError):
            cfg.environment = 'production'

    def test_is_local(self):
        cfg = EnvironmentConfig(
            environment='local',
            public_url='http://localhost:8000',
            supabase_callback_url='http://localhost:8000/auth/callback',
            cookie_secure=False,
            cors_origins=(),
        )
        assert cfg.is_local is True
        assert cfg.is_production is False

    def test_is_production(self):
        cfg = EnvironmentConfig(
            environment='production',
            public_url='https://boring-ui.modal.run',
            supabase_callback_url='https://boring-ui.modal.run/auth/callback',
            cookie_secure=True,
            cors_origins=('https://boring-ui.modal.run',),
        )
        assert cfg.is_production is True
        assert cfg.is_local is False


# =====================================================================
# 2. Callback URL derivation
# =====================================================================


class TestCallbackUrlDerivation:

    def test_simple_derivation(self):
        url = derive_supabase_callback_url('https://boring-ui.modal.run')
        assert url == 'https://boring-ui.modal.run/auth/callback'

    def test_trailing_slash_stripped(self):
        url = derive_supabase_callback_url('https://boring-ui.modal.run/')
        assert url == 'https://boring-ui.modal.run/auth/callback'

    def test_localhost(self):
        url = derive_supabase_callback_url('http://localhost:8000')
        assert url == 'http://localhost:8000/auth/callback'

    def test_with_path_prefix(self):
        url = derive_supabase_callback_url('https://host.com/app')
        assert url == 'https://host.com/app/auth/callback'


# =====================================================================
# 3. Callback URL consistency validation
# =====================================================================


class TestCallbackUrlConsistency:

    def test_consistent_url_passes(self):
        validate_callback_url_consistency(
            'https://boring-ui.modal.run',
            'https://boring-ui.modal.run/auth/callback',
        )

    def test_inconsistent_url_raises(self):
        with pytest.raises(EnvironmentConfigError, match='mismatch'):
            validate_callback_url_consistency(
                'https://boring-ui.modal.run',
                'https://other-host.com/auth/callback',
            )

    def test_wrong_path_raises(self):
        with pytest.raises(EnvironmentConfigError, match='mismatch'):
            validate_callback_url_consistency(
                'https://boring-ui.modal.run',
                'https://boring-ui.modal.run/auth/other',
            )


# =====================================================================
# 4. load_environment_config — local defaults
# =====================================================================


class TestLoadLocalDefaults:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_defaults_to_local(self):
        cfg = load_environment_config()
        assert cfg.environment == 'local'
        assert cfg.public_url == 'http://localhost:8000'
        assert cfg.cookie_secure is False

    def test_local_cors_includes_dev_ports(self):
        cfg = load_environment_config()
        assert 'http://localhost:5173' in cfg.cors_origins
        assert 'http://localhost:3000' in cfg.cors_origins

    def test_local_callback_url(self):
        cfg = load_environment_config()
        assert cfg.supabase_callback_url == 'http://localhost:8000/auth/callback'


# =====================================================================
# 5. load_environment_config — from env vars
# =====================================================================


class TestLoadFromEnv:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_production_from_env(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'production')
        monkeypatch.setenv('PUBLIC_URL', 'https://boring-ui.modal.run')

        cfg = load_environment_config()
        assert cfg.environment == 'production'
        assert cfg.public_url == 'https://boring-ui.modal.run'
        assert cfg.cookie_secure is True
        assert cfg.supabase_callback_url == 'https://boring-ui.modal.run/auth/callback'

    def test_staging_from_env(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'staging')
        monkeypatch.setenv('PUBLIC_URL', 'https://staging.boring-ui.dev')

        cfg = load_environment_config()
        assert cfg.environment == 'staging'
        assert cfg.cookie_secure is True

    def test_cors_from_env(self, monkeypatch):
        monkeypatch.setenv('CORS_ORIGINS', 'https://a.com, https://b.com')

        cfg = load_environment_config()
        assert cfg.cors_origins == ('https://a.com', 'https://b.com')

    def test_callback_url_override(self, monkeypatch):
        monkeypatch.setenv('SUPABASE_CALLBACK_URL', 'https://custom.com/auth/callback')

        cfg = load_environment_config()
        assert cfg.supabase_callback_url == 'https://custom.com/auth/callback'

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'production')
        monkeypatch.setenv('PUBLIC_URL', 'https://env.com')

        cfg = load_environment_config(
            environment='staging',
            public_url='https://override.com',
        )
        assert cfg.environment == 'staging'
        assert cfg.public_url == 'https://override.com'


# =====================================================================
# 6. TLS enforcement
# =====================================================================


class TestTlsEnforcement:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_production_requires_https(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'production')
        monkeypatch.setenv('PUBLIC_URL', 'http://boring-ui.modal.run')

        with pytest.raises(EnvironmentConfigError, match='HTTPS'):
            load_environment_config()

    def test_staging_requires_https(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'staging')
        monkeypatch.setenv('PUBLIC_URL', 'http://staging.boring-ui.dev')

        with pytest.raises(EnvironmentConfigError, match='HTTPS'):
            load_environment_config()

    def test_local_allows_http(self):
        cfg = load_environment_config(
            environment='local',
            public_url='http://localhost:8000',
        )
        assert cfg.cookie_secure is False

    def test_production_sets_cookie_secure(self):
        cfg = load_environment_config(
            environment='production',
            public_url='https://boring-ui.modal.run',
        )
        assert cfg.cookie_secure is True


# =====================================================================
# 7. Error handling
# =====================================================================


class TestConfigErrors:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_invalid_environment_name(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'dev')
        with pytest.raises(EnvironmentConfigError, match='Invalid ENVIRONMENT'):
            load_environment_config()

    def test_missing_public_url_non_local(self, monkeypatch):
        monkeypatch.setenv('ENVIRONMENT', 'production')
        with pytest.raises(EnvironmentConfigError, match='PUBLIC_URL is required'):
            load_environment_config()

    def test_invalid_url_format(self):
        with pytest.raises(EnvironmentConfigError, match='scheme and host'):
            load_environment_config(
                environment='local',
                public_url='not-a-url',
            )


# =====================================================================
# 8. CORS origin defaults per environment
# =====================================================================


class TestCorsDefaults:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_local_default_cors(self):
        cfg = load_environment_config(environment='local')
        assert len(cfg.cors_origins) >= 2  # localhost + 127.0.0.1

    def test_production_cors_limited_to_public_url(self):
        cfg = load_environment_config(
            environment='production',
            public_url='https://boring-ui.modal.run',
        )
        assert cfg.cors_origins == ('https://boring-ui.modal.run',)

    def test_staging_cors_limited_to_public_url(self):
        cfg = load_environment_config(
            environment='staging',
            public_url='https://staging.boring-ui.dev',
        )
        assert cfg.cors_origins == ('https://staging.boring-ui.dev',)


# =====================================================================
# 9. Identity loader — from dict
# =====================================================================


class TestIdentityLoaderFromDict:

    def test_load_from_dict(self):
        data = {
            'host_mapping': {'*': 'my-app'},
            'apps': {
                'my-app': {
                    'app_id': 'my-app',
                    'name': 'My App',
                    'logo': 'M',
                    'default_release_id': 'v1',
                },
            },
        }
        resolver = load_identity_config(data=data)
        assert isinstance(resolver, AppIdentityResolver)
        result = resolver.resolve('any-host')
        assert result.app_id == 'my-app'
        assert result.config.name == 'My App'

    def test_multiple_hosts(self):
        data = {
            'host_mapping': {
                'prod.example.com': 'app-prod',
                'staging.example.com': 'app-staging',
            },
            'apps': {
                'app-prod': {'app_id': 'app-prod', 'name': 'Prod'},
                'app-staging': {'app_id': 'app-staging', 'name': 'Staging'},
            },
        }
        resolver = load_identity_config(data=data)
        assert resolver.resolve('prod.example.com').app_id == 'app-prod'
        assert resolver.resolve('staging.example.com').app_id == 'app-staging'

    def test_missing_app_config_fields_have_defaults(self):
        data = {
            'host_mapping': {'*': 'minimal'},
            'apps': {'minimal': {'name': 'Minimal'}},
        }
        resolver = load_identity_config(data=data)
        config = resolver.resolve('host').config
        assert config.app_id == 'minimal'
        assert config.logo == ''
        assert config.default_release_id == ''

    def test_empty_host_mapping(self):
        data = {'host_mapping': {}, 'apps': {}, 'default_app_id': 'fallback'}
        resolver = load_identity_config(data=data)
        # No host matches, but default_app_id is set.
        result = resolver.resolve('unknown')
        assert result.app_id == 'fallback'


# =====================================================================
# 10. Identity loader — from JSON file
# =====================================================================


class TestIdentityLoaderFromFile:

    def test_load_from_file(self, tmp_path):
        config = {
            'host_mapping': {'*': 'file-app'},
            'apps': {
                'file-app': {'app_id': 'file-app', 'name': 'File App'},
            },
        }
        config_file = tmp_path / 'app_identity.json'
        config_file.write_text(json.dumps(config))

        resolver = load_identity_config(path=config_file)
        assert resolver.resolve('any').app_id == 'file-app'

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(IdentityConfigError, match='not found'):
            load_identity_config(path=tmp_path / 'missing.json')

    def test_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / 'bad.json'
        bad_file.write_text('{invalid json')
        with pytest.raises(IdentityConfigError, match='Invalid JSON'):
            load_identity_config(path=bad_file)

    def test_non_dict_top_level_raises(self, tmp_path):
        list_file = tmp_path / 'list.json'
        list_file.write_text('[]')
        with pytest.raises(IdentityConfigError, match='Expected dict'):
            load_identity_config(path=list_file)

    def test_env_var_path(self, tmp_path, monkeypatch):
        config = {
            'host_mapping': {'*': 'env-app'},
            'apps': {'env-app': {'app_id': 'env-app', 'name': 'Env App'}},
        }
        config_file = tmp_path / 'env_identity.json'
        config_file.write_text(json.dumps(config))

        monkeypatch.setenv('APP_IDENTITY_CONFIG', str(config_file))
        resolver = load_identity_config()
        assert resolver.resolve('host').app_id == 'env-app'


# =====================================================================
# 11. Identity loader — error cases
# =====================================================================


class TestIdentityLoaderErrors:

    def test_invalid_host_mapping_type(self):
        with pytest.raises(IdentityConfigError, match='host_mapping'):
            load_identity_config(data={'host_mapping': 'not-a-dict', 'apps': {}})

    def test_invalid_apps_type(self):
        with pytest.raises(IdentityConfigError, match='apps must be'):
            load_identity_config(data={'host_mapping': {}, 'apps': 'string'})

    def test_invalid_app_entry_type(self):
        with pytest.raises(IdentityConfigError, match='must be a dict'):
            load_identity_config(
                data={'host_mapping': {}, 'apps': {'bad': 'not-dict'}},
            )
