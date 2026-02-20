"""Unit tests for boring_ui/api/git_routes.py

Tests the git operations router including:
- Git status endpoint
- Git diff endpoint
- Git show endpoint
- Path validation and security
"""
import pytest
import subprocess
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from boring_ui.api.config import APIConfig
from boring_ui.api.git_routes import create_git_router


def create_test_app(workspace_root: Path) -> FastAPI:
    """Create a test FastAPI app with git router."""
    app = FastAPI()
    config = APIConfig(workspace_root=workspace_root)
    app.include_router(create_git_router(config), prefix='/api/git')
    return app


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository with some files."""
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@test.com'],
        cwd=tmp_path, capture_output=True, check=True
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path, capture_output=True, check=True
    )

    # Create and commit a test file
    test_file = tmp_path / 'test.txt'
    test_file.write_text('original content\n')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=tmp_path, capture_output=True, check=True
    )

    return tmp_path


@pytest.fixture
def temp_non_git_dir(tmp_path):
    """Create a temporary directory without git."""
    (tmp_path / 'some_file.txt').write_text('content')
    return tmp_path


class TestGetStatus:
    """Tests for GET /api/git/status endpoint."""

    @pytest.mark.asyncio
    async def test_git_repo_clean(self, temp_git_repo):
        """Test status returns is_repo=True for clean git repo."""
        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/status')

        assert response.status_code == 200
        data = response.json()
        assert data['is_repo'] is True
        assert data['available'] is True
        assert data['files'] == {}  # Clean repo has no changes

    @pytest.mark.asyncio
    async def test_git_repo_with_changes(self, temp_git_repo):
        """Test status shows modified files."""
        # Modify the test file
        test_file = temp_git_repo / 'test.txt'
        test_file.write_text('modified content\n')

        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/status')

        assert response.status_code == 200
        data = response.json()
        assert data['is_repo'] is True
        assert 'test.txt' in data['files']
        assert data['files']['test.txt'] == 'M'  # Modified

    @pytest.mark.asyncio
    async def test_git_repo_with_untracked(self, temp_git_repo):
        """Test status shows untracked files."""
        # Create untracked file
        (temp_git_repo / 'new_file.txt').write_text('new content')

        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/status')

        assert response.status_code == 200
        data = response.json()
        assert 'new_file.txt' in data['files']
        assert data['files']['new_file.txt'] == 'U'  # Untracked (normalized)

    @pytest.mark.asyncio
    async def test_non_git_directory(self, temp_non_git_dir):
        """Test status returns is_repo=False for non-git directory."""
        app = create_test_app(temp_non_git_dir)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/status')

        assert response.status_code == 200
        data = response.json()
        assert data['is_repo'] is False
        assert data['files'] == []


class TestGetDiff:
    """Tests for GET /api/git/diff endpoint."""

    @pytest.mark.asyncio
    async def test_diff_modified_file(self, temp_git_repo):
        """Test diff returns changes for modified file."""
        # Modify the test file
        test_file = temp_git_repo / 'test.txt'
        test_file.write_text('modified content\n')

        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/diff', params={'path': 'test.txt'})

        assert response.status_code == 200
        data = response.json()
        assert data['path'] == 'test.txt'
        assert '-original content' in data['diff']
        assert '+modified content' in data['diff']

    @pytest.mark.asyncio
    async def test_diff_untracked_file(self, temp_git_repo):
        """Test diff returns empty for untracked file."""
        (temp_git_repo / 'new_file.txt').write_text('new content')

        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/diff', params={'path': 'new_file.txt'})

        assert response.status_code == 200
        data = response.json()
        assert data['diff'] == ''  # Empty diff for untracked

    @pytest.mark.asyncio
    async def test_diff_path_traversal_rejected(self, temp_git_repo):
        """Test that path traversal attempts are rejected."""
        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/diff', params={'path': '../../../etc/passwd'})

        assert response.status_code == 400


class TestGetShow:
    """Tests for GET /api/git/show endpoint."""

    @pytest.mark.asyncio
    async def test_show_tracked_file(self, temp_git_repo):
        """Test show returns file content at HEAD."""
        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/show', params={'path': 'test.txt'})

        assert response.status_code == 200
        data = response.json()
        assert data['path'] == 'test.txt'
        assert data['content'] == 'original content\n'

    @pytest.mark.asyncio
    async def test_show_untracked_file(self, temp_git_repo):
        """Test show returns null for untracked file."""
        (temp_git_repo / 'new_file.txt').write_text('new content')

        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/show', params={'path': 'new_file.txt'})

        assert response.status_code == 200
        data = response.json()
        assert data['content'] is None
        assert 'error' in data

    @pytest.mark.asyncio
    async def test_show_path_traversal_rejected(self, temp_git_repo):
        """Test that path traversal attempts are rejected."""
        app = create_test_app(temp_git_repo)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/git/show', params={'path': '../../../etc/passwd'})

        assert response.status_code == 400
