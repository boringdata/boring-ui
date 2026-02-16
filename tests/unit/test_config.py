"""Unit tests for boring_ui.api.config module."""
import os
import sys

import pytest
from pathlib import Path
from boring_ui.api.config import APIConfig


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

    def test_companion_url_from_env(self, tmp_path, monkeypatch):
        """Test companion_url reads from COMPANION_URL env var."""
        monkeypatch.setenv('COMPANION_URL', 'http://localhost:3456')
        config = APIConfig(workspace_root=tmp_path)
        assert config.companion_url == 'http://localhost:3456'

    def test_companion_url_none_when_unset(self, tmp_path, monkeypatch):
        """Test companion_url is None when COMPANION_URL is not set."""
        monkeypatch.delenv('COMPANION_URL', raising=False)
        config = APIConfig(workspace_root=tmp_path)
        assert config.companion_url is None

    def test_pi_url_from_env(self, tmp_path, monkeypatch):
        """Test pi_url reads from PI_URL env var."""
        monkeypatch.setenv('PI_URL', 'http://localhost:8787')
        config = APIConfig(workspace_root=tmp_path)
        assert config.pi_url == 'http://localhost:8787'

    def test_pi_url_none_when_unset(self, tmp_path, monkeypatch):
        """Test pi_url is None when PI_URL is not set."""
        monkeypatch.delenv('PI_URL', raising=False)
        config = APIConfig(workspace_root=tmp_path)
        assert config.pi_url is None


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
