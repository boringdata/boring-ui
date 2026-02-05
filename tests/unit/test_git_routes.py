"""Unit tests for boring_ui.api.modules.git module."""
import subprocess
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from boring_ui.api.config import APIConfig
from boring_ui.api.modules.git import create_git_router
from fastapi import FastAPI


@pytest.fixture
def git_repo(tmp_path):
    """Create a git repository with test commits."""
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

    # Create and commit a file
    (tmp_path / 'file.txt').write_text('original content')
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=tmp_path, capture_output=True, check=True
    )

    # Modify file (unstaged change)
    (tmp_path / 'file.txt').write_text('modified content')

    return tmp_path


@pytest.fixture
def app(git_repo):
    """Create test FastAPI app with git router."""
    config = APIConfig(workspace_root=git_repo)
    app = FastAPI()
    app.include_router(create_git_router(config), prefix='/api/git')
    return app


@pytest.fixture
def non_git_app(tmp_path):
    """Create test app in a non-git directory."""
    # Create some files but don't init git
    (tmp_path / 'file.txt').write_text('not in repo')
    config = APIConfig(workspace_root=tmp_path)
    app = FastAPI()
    app.include_router(create_git_router(config), prefix='/api/git')
    return app


class TestStatusEndpoint:
    """Tests for GET /status endpoint."""

    @pytest.mark.asyncio
    async def test_status_in_repo(self, app):
        """Test status returns repo info with modified files."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/status')
            assert r.status_code == 200
            data = r.json()
            assert data['is_repo'] is True
            assert data['available'] is True
            # Modified file should be in status
            assert 'file.txt' in data['files']
            # M for modified (unstaged)
            assert 'M' in data['files']['file.txt']

    @pytest.mark.asyncio
    async def test_status_not_a_repo(self, non_git_app):
        """Test status returns is_repo=False for non-git directory."""
        transport = ASGITransport(app=non_git_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/status')
            assert r.status_code == 200
            data = r.json()
            assert data['is_repo'] is False
            assert data['files'] == []

    @pytest.mark.asyncio
    async def test_status_clean_repo(self, git_repo):
        """Test status with clean working tree."""
        # Reset file to original content
        (git_repo / 'file.txt').write_text('original content')

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/status')
            assert r.status_code == 200
            data = r.json()
            assert data['is_repo'] is True
            # Should have no modified files
            assert 'file.txt' not in data['files']

    @pytest.mark.asyncio
    async def test_status_with_staged_file(self, git_repo):
        """Test status shows staged files."""
        # Stage the modified file
        subprocess.run(
            ['git', 'add', 'file.txt'],
            cwd=git_repo, capture_output=True, check=True
        )

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/status')
            assert r.status_code == 200
            data = r.json()
            assert 'file.txt' in data['files']
            # M in index position (staged)
            assert data['files']['file.txt'] in ['M', 'M ']

    @pytest.mark.asyncio
    async def test_status_with_untracked_file(self, git_repo):
        """Test status shows untracked files."""
        # Create untracked file
        (git_repo / 'untracked.txt').write_text('untracked')

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/status')
            assert r.status_code == 200
            data = r.json()
            assert 'untracked.txt' in data['files']
            # ?? for untracked
            assert data['files']['untracked.txt'] == '??'


class TestDiffEndpoint:
    """Tests for GET /diff endpoint."""

    @pytest.mark.asyncio
    async def test_diff_modified_file(self, app):
        """Test diff shows changes for modified file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/diff?path=file.txt')
            assert r.status_code == 200
            data = r.json()
            assert 'diff' in data
            assert data['path'] == 'file.txt'
            # Diff should show old and new content
            assert 'original' in data['diff']
            assert 'modified' in data['diff']

    @pytest.mark.asyncio
    async def test_diff_unmodified_file(self, git_repo):
        """Test diff returns empty for unmodified file."""
        # Reset file
        (git_repo / 'file.txt').write_text('original content')

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/diff?path=file.txt')
            assert r.status_code == 200
            data = r.json()
            assert data['diff'] == ''

    @pytest.mark.asyncio
    async def test_diff_untracked_file(self, git_repo):
        """Test diff handles untracked file gracefully."""
        # Create untracked file
        (git_repo / 'new.txt').write_text('new content')

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/diff?path=new.txt')
            assert r.status_code == 200
            data = r.json()
            # Should return empty diff with error message for untracked
            assert 'error' in data or data['diff'] == ''

    @pytest.mark.asyncio
    async def test_diff_path_traversal_rejected(self, app):
        """Test path traversal is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/diff?path=../../../etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()


class TestShowEndpoint:
    """Tests for GET /show endpoint."""

    @pytest.mark.asyncio
    async def test_show_tracked_file(self, app):
        """Test show returns file content at HEAD."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=file.txt')
            assert r.status_code == 200
            data = r.json()
            assert data['content'] == 'original content'
            assert data['path'] == 'file.txt'

    @pytest.mark.asyncio
    async def test_show_untracked_file(self, git_repo):
        """Test show returns null for untracked file."""
        # Create untracked file
        (git_repo / 'untracked.txt').write_text('untracked')

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=untracked.txt')
            assert r.status_code == 200
            data = r.json()
            assert data['content'] is None
            assert 'error' in data

    @pytest.mark.asyncio
    async def test_show_returns_committed_content(self, git_repo):
        """Test show returns committed content, not working tree."""
        # File has modified content but we want committed content
        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=file.txt')
            assert r.status_code == 200
            data = r.json()
            # Should return original committed content, not modified
            assert data['content'] == 'original content'
            assert 'modified' not in data['content']

    @pytest.mark.asyncio
    async def test_show_path_traversal_rejected(self, app):
        """Test path traversal is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=../../../etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_show_nested_file(self, git_repo):
        """Test show works with files in subdirectories."""
        # Create and commit a nested file
        (git_repo / 'subdir').mkdir()
        (git_repo / 'subdir' / 'nested.txt').write_text('nested content')
        subprocess.run(['git', 'add', '.'], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Add nested file'],
            cwd=git_repo, capture_output=True, check=True
        )

        config = APIConfig(workspace_root=git_repo)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix='/api/git')

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=subdir/nested.txt')
            assert r.status_code == 200
            data = r.json()
            assert data['content'] == 'nested content'


class TestPathSecurity:
    """Security tests for path validation in git routes."""

    @pytest.mark.asyncio
    async def test_absolute_path_diff_rejected(self, app):
        """Test absolute path in diff is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/diff?path=/etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_absolute_path_show_rejected(self, app):
        """Test absolute path in show is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/git/show?path=/etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()
