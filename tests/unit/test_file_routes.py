"""Unit tests for boring_ui.api.modules.files module."""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from boring_ui.api.config import APIConfig
from boring_ui.api.storage import LocalStorage
from boring_ui.api.modules.files import create_file_router
from fastapi import FastAPI


@pytest.fixture
def app(tmp_path):
    """Create test FastAPI app with file router."""
    config = APIConfig(workspace_root=tmp_path)
    storage = LocalStorage(tmp_path)

    # Create test files and directories
    (tmp_path / 'test.txt').write_text('test content')
    (tmp_path / 'file2.txt').write_text('content2')
    (tmp_path / 'subdir').mkdir()
    (tmp_path / 'subdir' / 'nested.txt').write_text('nested content')

    app = FastAPI()
    app.include_router(create_file_router(config, storage), prefix='/api')
    return app


@pytest.fixture
def tmp_path_ref(tmp_path):
    """Return tmp_path for tests that need direct access."""
    return tmp_path


class TestTreeEndpoint:
    """Tests for GET /tree endpoint."""

    @pytest.mark.asyncio
    async def test_get_tree_root(self, app):
        """Test listing root directory."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/tree?path=.')
            assert r.status_code == 200
            data = r.json()
            assert 'entries' in data
            assert 'path' in data
            assert data['path'] == '.'
            names = [e['name'] for e in data['entries']]
            assert 'test.txt' in names
            assert 'subdir' in names

    @pytest.mark.asyncio
    async def test_get_tree_subdir(self, app):
        """Test listing subdirectory."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/tree?path=subdir')
            assert r.status_code == 200
            data = r.json()
            names = [e['name'] for e in data['entries']]
            assert 'nested.txt' in names

    @pytest.mark.asyncio
    async def test_get_tree_default_path(self, app):
        """Test listing with default path."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/tree')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_get_tree_nonexistent(self, app):
        """Test listing non-existent directory returns empty."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/tree?path=nonexistent')
            assert r.status_code == 200
            data = r.json()
            assert data['entries'] == []


class TestFileReadEndpoint:
    """Tests for GET /file endpoint."""

    @pytest.mark.asyncio
    async def test_get_file(self, app):
        """Test reading file contents."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/file?path=test.txt')
            assert r.status_code == 200
            data = r.json()
            assert data['content'] == 'test content'
            assert data['path'] == 'test.txt'

    @pytest.mark.asyncio
    async def test_get_file_nested(self, app):
        """Test reading nested file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/file?path=subdir/nested.txt')
            assert r.status_code == 200
            assert r.json()['content'] == 'nested content'

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, app):
        """Test reading non-existent file returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/file?path=nonexistent.txt')
            assert r.status_code == 404
            assert 'not found' in r.json()['detail'].lower()


class TestFileWriteEndpoint:
    """Tests for PUT /file endpoint."""

    @pytest.mark.asyncio
    async def test_put_file_new(self, app, tmp_path_ref):
        """Test writing new file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.put('/api/file?path=new.txt', json={'content': 'new content'})
            assert r.status_code == 200
            data = r.json()
            assert data['success'] is True
            assert data['path'] == 'new.txt'
            assert (tmp_path_ref / 'new.txt').read_text() == 'new content'

    @pytest.mark.asyncio
    async def test_put_file_overwrite(self, app, tmp_path_ref):
        """Test overwriting existing file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.put('/api/file?path=test.txt', json={'content': 'updated'})
            assert r.status_code == 200
            assert (tmp_path_ref / 'test.txt').read_text() == 'updated'

    @pytest.mark.asyncio
    async def test_put_file_creates_parents(self, app, tmp_path_ref):
        """Test writing file creates parent directories."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.put('/api/file?path=new/deep/file.txt', json={'content': 'deep'})
            assert r.status_code == 200
            assert (tmp_path_ref / 'new' / 'deep' / 'file.txt').read_text() == 'deep'


class TestFileDeleteEndpoint:
    """Tests for DELETE /file endpoint."""

    @pytest.mark.asyncio
    async def test_delete_file(self, app, tmp_path_ref):
        """Test deleting file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete('/api/file?path=test.txt')
            assert r.status_code == 200
            assert r.json()['success'] is True
            assert not (tmp_path_ref / 'test.txt').exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, app):
        """Test deleting non-existent file returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete('/api/file?path=nonexistent.txt')
            assert r.status_code == 404


class TestRenameEndpoint:
    """Tests for POST /file/rename endpoint."""

    @pytest.mark.asyncio
    async def test_rename_file(self, app, tmp_path_ref):
        """Test renaming file."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/rename', json={
                'old_path': 'test.txt',
                'new_path': 'renamed.txt'
            })
            assert r.status_code == 200
            data = r.json()
            assert data['success'] is True
            assert data['old_path'] == 'test.txt'
            assert data['new_path'] == 'renamed.txt'
            assert not (tmp_path_ref / 'test.txt').exists()
            assert (tmp_path_ref / 'renamed.txt').exists()

    @pytest.mark.asyncio
    async def test_rename_not_found(self, app):
        """Test renaming non-existent file returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/rename', json={
                'old_path': 'nonexistent.txt',
                'new_path': 'new.txt'
            })
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_rename_target_exists(self, app):
        """Test renaming to existing file returns 409."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/rename', json={
                'old_path': 'test.txt',
                'new_path': 'file2.txt'
            })
            assert r.status_code == 409
            assert 'exists' in r.json()['detail'].lower()


class TestMoveEndpoint:
    """Tests for POST /file/move endpoint."""

    @pytest.mark.asyncio
    async def test_move_file(self, app, tmp_path_ref):
        """Test moving file to different directory."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/move', json={
                'src_path': 'test.txt',
                'dest_dir': 'subdir'
            })
            assert r.status_code == 200
            data = r.json()
            assert data['success'] is True
            assert data['old_path'] == 'test.txt'
            assert 'dest_path' in data
            assert not (tmp_path_ref / 'test.txt').exists()
            assert (tmp_path_ref / 'subdir' / 'test.txt').exists()

    @pytest.mark.asyncio
    async def test_move_not_found(self, app):
        """Test moving non-existent file returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/move', json={
                'src_path': 'nonexistent.txt',
                'dest_dir': 'subdir'
            })
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_move_dest_not_directory(self, app):
        """Test moving to non-directory returns 400."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/move', json={
                'src_path': 'test.txt',
                'dest_dir': 'file2.txt'
            })
            assert r.status_code == 400
            assert 'not a directory' in r.json()['detail'].lower()


class TestSearchEndpoint:
    """Tests for GET /search endpoint."""

    @pytest.mark.asyncio
    async def test_search_files(self, app):
        """Test searching files by pattern."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=*.txt')
            assert r.status_code == 200
            data = r.json()
            assert 'results' in data
            assert 'pattern' in data
            assert data['pattern'] == '*.txt'
            names = [m['name'] for m in data['results']]
            assert 'test.txt' in names
            assert 'nested.txt' in names

    @pytest.mark.asyncio
    async def test_search_specific_pattern(self, app):
        """Test searching with specific pattern."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=test*')
            assert r.status_code == 200
            names = [m['name'] for m in r.json()['results']]
            assert 'test.txt' in names

    @pytest.mark.asyncio
    async def test_search_in_subdir(self, app):
        """Test searching in specific subdirectory."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=*.txt&path=subdir')
            assert r.status_code == 200
            names = [m['name'] for m in r.json()['results']]
            assert 'nested.txt' in names
            assert 'test.txt' not in names

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, app, tmp_path_ref):
        """Test search is case-insensitive."""
        (tmp_path_ref / 'UPPER.TXT').write_text('upper')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=upper*')
            assert r.status_code == 200
            names = [m['name'] for m in r.json()['results']]
            assert 'UPPER.TXT' in names

    @pytest.mark.asyncio
    async def test_search_includes_dir_field(self, app):
        """Test search results include 'dir' field."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=nested.txt')
            assert r.status_code == 200
            results = r.json()['results']
            assert len(results) == 1
            assert 'dir' in results[0]
            assert results[0]['dir'] == 'subdir'


class TestPathTraversalRejection:
    """Security tests for path traversal prevention."""

    @pytest.mark.asyncio
    async def test_tree_traversal_rejected(self, app):
        """Test path traversal in tree is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/tree?path=../../../etc')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_file_read_traversal_rejected(self, app):
        """Test path traversal in file read is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/file?path=../../../etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_file_write_traversal_rejected(self, app):
        """Test path traversal in file write is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.put('/api/file?path=../../../tmp/malicious.txt',
                                 json={'content': 'bad'})
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_file_delete_traversal_rejected(self, app):
        """Test path traversal in file delete is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete('/api/file?path=../../../etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_rename_traversal_rejected(self, app):
        """Test path traversal in rename is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/rename', json={
                'old_path': '../../../etc/passwd',
                'new_path': 'stolen.txt'
            })
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_move_traversal_rejected(self, app):
        """Test path traversal in move is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/file/move', json={
                'src_path': 'test.txt',
                'dest_dir': '../../../tmp'
            })
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_search_traversal_rejected(self, app):
        """Test path traversal in search is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/search?q=*.txt&path=../../../etc')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self, app):
        """Test absolute paths outside workspace are rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/file?path=/etc/passwd')
            assert r.status_code == 400
            assert 'traversal' in r.json()['detail'].lower()
