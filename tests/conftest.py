"""Pytest configuration for boring_ui tests."""
import pytest
from pathlib import Path


@pytest.fixture
def workspace_root(tmp_path):
    """Create a temporary workspace root for testing."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace
