"""Pytest configuration for boring-ui tests."""
import pytest


@pytest.fixture
def workspace_root(tmp_path):
    """Create a temporary workspace root for testing."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace
