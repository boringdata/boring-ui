"""Pytest configuration for boring_ui tests."""
import sys
from pathlib import Path

# Add src/back and src/ to path for src-layout imports
_PROJECT_ROOT = Path(__file__).parent.parent
_SRC_BACK = _PROJECT_ROOT / 'src' / 'back'
if str(_SRC_BACK) not in sys.path:
    sys.path.insert(0, str(_SRC_BACK))
_SRC = _PROJECT_ROOT / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pytest


@pytest.fixture
def workspace_root(tmp_path):
    """Create a temporary workspace root for testing."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace
