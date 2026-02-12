"""Unit tests for boring_ui.api.config module."""
import sys

import pytest
from pathlib import Path
from boring_ui.api.config import APIConfig, ConfigValidationError, load_runtime_config


# Check if symlinks are supported (Windows requires admin privileges)
def _symlinks_supported():
    """Check if the platform supports symlinks without special privileges."""
    if sys.platform == 'win32':
        return False
    return True


class TestAPIConfig:
    """Tests for APIConfig dataclass."""

    def test_default_values(self, tmp_path):
        """Test default configuration values."""
        config = APIConfig(workspace_root=tmp_path)
        # Default includes multiple dev origins
        assert 'http://localhost:5173' in config.cors_origins
        assert 'http://localhost:5174' in config.cors_origins
        assert 'http://localhost:3000' in config.cors_origins
        assert '*' in config.cors_origins  # Allow all in dev
        assert 'shell' in config.pty_providers
        assert 'claude' in config.pty_providers
        assert config.pty_providers['shell'] == ['bash']

    def test_custom_cors_origins(self, tmp_path):
        """Test custom CORS origins."""
        origins = ['http://localhost:3000', 'https://example.com']
        config = APIConfig(workspace_root=tmp_path, cors_origins=origins)
        assert config.cors_origins == origins

    def test_custom_pty_providers(self, tmp_path):
        """Test custom PTY providers."""
        providers = {'custom': ['python', '-m', 'ptpython']}
        config = APIConfig(workspace_root=tmp_path, pty_providers=providers)
        assert config.pty_providers == providers


class TestValidatePath:
    """Tests for APIConfig.validate_path method."""

    def test_validate_path_within_workspace(self, tmp_path):
        """Test validating a path within workspace."""
        config = APIConfig(workspace_root=tmp_path)
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        result = config.validate_path('subdir')
        assert result == subdir

    def test_validate_path_nested(self, tmp_path):
        """Test validating a nested path."""
        config = APIConfig(workspace_root=tmp_path)
        nested = tmp_path / 'a' / 'b' / 'c'
        nested.mkdir(parents=True)
        result = config.validate_path('a/b/c')
        assert result == nested

    def test_validate_path_rejects_traversal(self, tmp_path):
        """Test that path traversal is rejected."""
        config = APIConfig(workspace_root=tmp_path)
        with pytest.raises(ValueError, match='traversal'):
            config.validate_path('../../../etc/passwd')

    def test_validate_path_rejects_absolute_escape(self, tmp_path):
        """Test that absolute paths outside workspace are rejected."""
        config = APIConfig(workspace_root=tmp_path)
        with pytest.raises(ValueError, match='traversal'):
            config.validate_path('/etc/passwd')

    def test_validate_path_handles_dots(self, tmp_path):
        """Test that . and .. in paths are normalized."""
        config = APIConfig(workspace_root=tmp_path)
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        result = config.validate_path('./subdir/../subdir')
        assert result == subdir

    def test_validate_path_accepts_string(self, tmp_path):
        """Test that string paths are accepted."""
        config = APIConfig(workspace_root=tmp_path)
        result = config.validate_path('.')
        assert result == tmp_path

    def test_validate_path_accepts_path_object(self, tmp_path):
        """Test that Path objects are accepted."""
        config = APIConfig(workspace_root=tmp_path)
        result = config.validate_path(Path('.'))
        assert result == tmp_path

    def test_validate_path_workspace_root_itself(self, tmp_path):
        """Test that workspace root is a valid path."""
        config = APIConfig(workspace_root=tmp_path)
        # Passing '.' should resolve to workspace_root
        result = config.validate_path('.')
        assert result == tmp_path.resolve()

    @pytest.mark.skipif(
        not _symlinks_supported(),
        reason='Symlinks require admin privileges on Windows'
    )
    def test_validate_path_symlink_escape(self, tmp_path):
        """Test that symlinks escaping workspace are rejected."""
        # Create a symlink that points outside workspace
        outside_dir = tmp_path.parent / 'outside'
        outside_dir.mkdir(exist_ok=True)

        symlink = tmp_path / 'escape_link'
        try:
            symlink.symlink_to(outside_dir)
        except OSError:
            pytest.skip('Symlink creation not supported on this system')

        try:
            config = APIConfig(workspace_root=tmp_path)
            with pytest.raises(ValueError, match='traversal'):
                config.validate_path('escape_link')
        finally:
            if symlink.exists():
                symlink.unlink()
            if outside_dir.exists():
                outside_dir.rmdir()


class TestRuntimeConfig:
    """Tests for startup/runtime environment validation."""

    def test_defaults_to_local_mode(self):
        """Default runtime mode should be local with no sandbox config."""
        runtime = load_runtime_config({})
        assert runtime.workspace_mode == 'local'
        assert runtime.sandbox is None

    def test_rejects_invalid_workspace_mode(self):
        """Unknown workspace modes should fail fast."""
        with pytest.raises(ConfigValidationError, match='WORKSPACE_MODE'):
            load_runtime_config({'WORKSPACE_MODE': 'remote'})

    def test_sandbox_requires_expected_env_vars(self):
        """Sandbox mode should list required env vars when missing."""
        with pytest.raises(ConfigValidationError) as exc:
            load_runtime_config({'WORKSPACE_MODE': 'sandbox'})

        message = str(exc.value)
        assert 'SPRITES_BASE_URL is required' in message
        assert 'SPRITES_SPRITE_NAME is required' in message
        assert 'SPRITES_API_TOKEN is required' in message
        assert 'SESSION_TOKEN_SECRET is required' in message
        assert 'SPRITES_WORKSPACE_SERVICE_HOST is required' in message
        assert 'SPRITES_WORKSPACE_SERVICE_PORT is required' in message

    def test_sandbox_valid_config_parses_cleanly(self):
        """Valid sandbox env should produce parsed runtime config."""
        runtime = load_runtime_config({
            'WORKSPACE_MODE': 'sandbox',
            'SPRITES_BASE_URL': 'https://sprites.example.internal',
            'SPRITES_SPRITE_NAME': 'workspace-a',
            'SPRITES_API_TOKEN': 'token-value',
            'SESSION_TOKEN_SECRET': 'x' * 32,
            'SPRITES_WORKSPACE_SERVICE_HOST': 'workspace-service',
            'SPRITES_WORKSPACE_SERVICE_PORT': '8443',
            'SPRITES_WORKSPACE_SERVICE_PATH': '/api/workspace',
            'MULTI_TENANT': 'false',
            'AUTH_IDENTITY_BINDING_ENABLED': 'false',
        })

        assert runtime.workspace_mode == 'sandbox'
        assert runtime.sandbox is not None
        assert runtime.sandbox.base_url == 'https://sprites.example.internal'
        assert runtime.sandbox.sprite_name == 'workspace-a'
        assert runtime.sandbox.service_target.host == 'workspace-service'
        assert runtime.sandbox.service_target.port == 8443
        assert runtime.sandbox.service_target.path == '/api/workspace'
        assert runtime.sandbox.multi_tenant is False

    def test_multi_tenant_requires_auth_identity_binding(self):
        """Multi-tenant indicators must be blocked without identity binding."""
        with pytest.raises(ConfigValidationError, match='Multi-tenant sandbox mode is not supported'):
            load_runtime_config({
                'WORKSPACE_MODE': 'sandbox',
                'SPRITES_BASE_URL': 'https://sprites.example.internal',
                'SPRITES_SPRITE_NAME': 'workspace-a',
                'SPRITES_API_TOKEN': 'token-value',
                'SESSION_TOKEN_SECRET': 'x' * 32,
                'SPRITES_WORKSPACE_SERVICE_HOST': 'workspace-service',
                'SPRITES_WORKSPACE_SERVICE_PORT': '8443',
                'MULTI_TENANT': 'true',
                'AUTH_IDENTITY_BINDING_ENABLED': 'false',
            })

    def test_per_user_routing_requires_auth_identity_binding(self):
        """Per-user routing mode must be blocked without identity binding."""
        with pytest.raises(ConfigValidationError, match='Multi-tenant sandbox mode is not supported'):
            load_runtime_config({
                'WORKSPACE_MODE': 'sandbox',
                'SPRITES_BASE_URL': 'https://sprites.example.internal',
                'SPRITES_SPRITE_NAME': 'workspace-a',
                'SPRITES_API_TOKEN': 'token-value',
                'SESSION_TOKEN_SECRET': 'x' * 32,
                'SPRITES_WORKSPACE_SERVICE_HOST': 'workspace-service',
                'SPRITES_WORKSPACE_SERVICE_PORT': '8443',
                'WORKSPACE_ROUTING_MODE': 'per_user',
                'AUTH_IDENTITY_BINDING_ENABLED': 'no',
            })

    def test_rejects_invalid_boolean_values(self):
        """Boolean-like env vars must use supported values only."""
        with pytest.raises(ConfigValidationError, match='AUTH_IDENTITY_BINDING_ENABLED must be a boolean'):
            load_runtime_config({
                'WORKSPACE_MODE': 'sandbox',
                'SPRITES_BASE_URL': 'https://sprites.example.internal',
                'SPRITES_SPRITE_NAME': 'workspace-a',
                'SPRITES_API_TOKEN': 'token-value',
                'SESSION_TOKEN_SECRET': 'x' * 32,
                'SPRITES_WORKSPACE_SERVICE_HOST': 'workspace-service',
                'SPRITES_WORKSPACE_SERVICE_PORT': '8443',
                'AUTH_IDENTITY_BINDING_ENABLED': 'sometimes',
            })
