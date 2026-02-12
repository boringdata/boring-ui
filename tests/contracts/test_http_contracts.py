"""Executable HTTP contract tests derived from http_contract_baseline.py.

These tests validate that the API's actual behavior matches the documented
contracts. They serve as a gate for sandbox rollout: any proxy or delegation
layer must preserve these contracts.

Run: python3 -m pytest tests/contracts/test_http_contracts.py -v
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig


# ── Fixtures ──


@pytest.fixture
def workspace(tmp_path):
    """Create a test workspace with sample files."""
    ws = tmp_path / 'workspace'
    ws.mkdir()
    (ws / 'README.md').write_text('# Test Project')
    (ws / 'src').mkdir()
    (ws / 'src' / 'main.py').write_text('print("hello")')
    (ws / 'empty.txt').write_text('')
    return ws


@pytest.fixture
def app(workspace):
    """Full app with all routers."""
    config = APIConfig(workspace_root=workspace)
    return create_app(config)


def _client(app):
    """Create an httpx AsyncClient for the app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url='http://test')


# ── 1. Capabilities & Discovery ──


class TestCapabilitiesContract:
    """Contract: GET /api/capabilities."""

    @pytest.mark.asyncio
    async def test_response_schema(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/capabilities')
        assert resp.status_code == 200
        data = resp.json()
        assert 'version' in data
        assert 'features' in data
        for key in ('files', 'git', 'pty', 'chat_claude_code', 'stream', 'approval'):
            assert key in data['features']
            assert isinstance(data['features'][key], bool)

    @pytest.mark.asyncio
    async def test_stream_and_chat_parity(self, app):
        """stream and chat_claude_code always have the same value."""
        async with _client(app) as c:
            resp = await c.get('/api/capabilities')
        assert resp.json()['features']['stream'] == resp.json()['features']['chat_claude_code']

    @pytest.mark.asyncio
    async def test_routers_array_present(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/capabilities')
        data = resp.json()
        assert 'routers' in data
        assert isinstance(data['routers'], list)
        for router in data['routers']:
            assert 'name' in router
            assert 'prefix' in router
            assert 'enabled' in router


class TestHealthContract:
    """Contract: GET /health."""

    @pytest.mark.asyncio
    async def test_response_schema(self, app):
        async with _client(app) as c:
            resp = await c.get('/health')
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert 'workspace' in data
        assert data['workspace_mode'] in ('local', 'sandbox')
        assert 'features' in data


class TestConfigContract:
    """Contract: GET /api/config."""

    @pytest.mark.asyncio
    async def test_response_schema(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/config')
        assert resp.status_code == 200
        data = resp.json()
        assert 'workspace_root' in data
        assert 'workspace_mode' in data
        assert isinstance(data['pty_providers'], list)
        assert data['paths']['files'] == '.'

    @pytest.mark.asyncio
    async def test_no_sandbox_block_in_local_mode(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/config')
        data = resp.json()
        assert data['workspace_mode'] == 'local'
        assert 'sandbox' not in data


class TestProjectContract:
    """Contract: GET /api/project."""

    @pytest.mark.asyncio
    async def test_response_schema(self, app, workspace):
        async with _client(app) as c:
            resp = await c.get('/api/project')
        assert resp.status_code == 200
        assert resp.json()['root'] == str(workspace)


# ── 2. File Operations ──


class TestFileTreeContract:
    """Contract: GET /api/tree."""

    @pytest.mark.asyncio
    async def test_default_lists_workspace_root(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/tree')
        assert resp.status_code == 200
        data = resp.json()
        assert 'entries' in data
        assert 'path' in data
        names = [e['name'] for e in data['entries']]
        assert 'README.md' in names
        assert 'src' in names

    @pytest.mark.asyncio
    async def test_entry_schema(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/tree')
        for entry in resp.json()['entries']:
            assert 'name' in entry
            assert 'path' in entry
            assert 'is_dir' in entry

    @pytest.mark.asyncio
    async def test_directories_first(self, app):
        """Entries sorted: directories first, then alphabetical."""
        async with _client(app) as c:
            resp = await c.get('/api/tree')
        entries = resp.json()['entries']
        dirs = [e for e in entries if e['is_dir']]
        files = [e for e in entries if not e['is_dir']]
        if dirs and files:
            dir_indices = [entries.index(d) for d in dirs]
            file_indices = [entries.index(f) for f in files]
            assert max(dir_indices) < min(file_indices)

    @pytest.mark.asyncio
    async def test_nonexistent_dir_returns_empty(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/tree', params={'path': 'does_not_exist'})
        assert resp.status_code == 200
        assert resp.json()['entries'] == []

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/tree', params={'path': '../../../etc'})
        assert resp.status_code == 400


class TestFileReadContract:
    """Contract: GET /api/file."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': 'README.md'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['content'] == '# Test Project'
        assert data['path'] == 'README.md'

    @pytest.mark.asyncio
    async def test_read_empty_file(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': 'empty.txt'})
        assert resp.status_code == 200
        assert resp.json()['content'] == ''

    @pytest.mark.asyncio
    async def test_read_not_found(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': 'nope.txt'})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_read_directory_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': 'src'})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': '../../../etc/passwd'})
        assert resp.status_code == 400


class TestFileWriteContract:
    """Contract: PUT /api/file."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, app):
        async with _client(app) as c:
            resp = await c.put(
                '/api/file',
                params={'path': 'new_file.txt'},
                json={'content': 'hello world'},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['path'] == 'new_file.txt'

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, app):
        async with _client(app) as c:
            resp = await c.put(
                '/api/file',
                params={'path': 'deep/nested/file.txt'},
                json={'content': 'nested'},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.put(
                '/api/file',
                params={'path': '../escape.txt'},
                json={'content': 'bad'},
            )
        assert resp.status_code == 400


class TestFileDeleteContract:
    """Contract: DELETE /api/file."""

    @pytest.mark.asyncio
    async def test_delete_existing_file(self, app):
        async with _client(app) as c:
            resp = await c.delete('/api/file', params={'path': 'empty.txt'})
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, app):
        async with _client(app) as c:
            resp = await c.delete('/api/file', params={'path': 'nope.txt'})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.delete('/api/file', params={'path': '../escape.txt'})
        assert resp.status_code == 400


class TestFileRenameContract:
    """Contract: POST /api/file/rename."""

    @pytest.mark.asyncio
    async def test_rename_file(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/file/rename',
                json={'old_path': 'README.md', 'new_path': 'README.txt'},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['old_path'] == 'README.md'
        assert data['new_path'] == 'README.txt'

    @pytest.mark.asyncio
    async def test_rename_not_found(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/file/rename',
                json={'old_path': 'nope.txt', 'new_path': 'still_nope.txt'},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rename_target_exists(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/file/rename',
                json={'old_path': 'README.md', 'new_path': 'empty.txt'},
            )
        assert resp.status_code == 409


class TestFileMoveContract:
    """Contract: POST /api/file/move."""

    @pytest.mark.asyncio
    async def test_move_file(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/file/move',
                json={'src_path': 'empty.txt', 'dest_dir': 'src'},
            )
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    @pytest.mark.asyncio
    async def test_move_not_found(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/file/move',
                json={'src_path': 'nope.txt', 'dest_dir': 'src'},
            )
        assert resp.status_code == 404


class TestFileSearchContract:
    """Contract: GET /api/search."""

    @pytest.mark.asyncio
    async def test_search_by_pattern(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/search', params={'q': '*.md'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'results' in data
        assert data['pattern'] == '*.md'
        names = [r['name'] for r in data['results']]
        assert 'README.md' in names

    @pytest.mark.asyncio
    async def test_result_schema(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/search', params={'q': '*.py'})
        for result in resp.json()['results']:
            assert 'name' in result
            assert 'path' in result
            assert 'dir' in result

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/search', params={'q': '*.py', 'path': '../..'})
        assert resp.status_code == 400


# ── 3. Git Operations ──


class TestGitStatusContract:
    """Contract: GET /api/git/status."""

    @pytest.mark.asyncio
    async def test_non_git_workspace(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/git/status')
        assert resp.status_code == 200
        data = resp.json()
        assert data['is_repo'] is False
        assert data['files'] == []


class TestGitDiffContract:
    """Contract: GET /api/git/diff."""

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/git/diff', params={'path': '../../../etc/passwd'})
        assert resp.status_code == 400


class TestGitShowContract:
    """Contract: GET /api/git/show."""

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/git/show', params={'path': '../../../etc/passwd'})
        assert resp.status_code == 400


# ── 4. Session Management ──


class TestSessionsContract:
    """Contract: GET/POST /api/sessions."""

    @pytest.mark.asyncio
    async def test_list_empty_sessions(self, app):
        async with _client(app) as c:
            resp = await c.get('/api/sessions')
        assert resp.status_code == 200
        data = resp.json()
        assert 'sessions' in data
        assert isinstance(data['sessions'], list)

    @pytest.mark.asyncio
    async def test_create_session_returns_uuid(self, app):
        async with _client(app) as c:
            resp = await c.post('/api/sessions')
        assert resp.status_code == 200
        uuid.UUID(resp.json()['session_id'])


# ── 5. Approval Workflow ──


class TestApprovalContract:
    """Contract: POST/GET /api/approval/*."""

    @pytest.mark.asyncio
    async def test_create_approval_request(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert 'request_id' in data
        assert data['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_list_pending(self, app):
        async with _client(app) as c:
            await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            resp = await c.get('/api/approval/pending')
        assert resp.status_code == 200
        data = resp.json()
        assert 'pending' in data
        assert 'count' in data
        assert data['count'] == len(data['pending'])
        assert data['count'] >= 1

    @pytest.mark.asyncio
    async def test_pending_entry_schema(self, app):
        async with _client(app) as c:
            await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            resp = await c.get('/api/approval/pending')
        entry = resp.json()['pending'][0]
        for key in ('id', 'status', 'tool_name', 'description', 'created_at'):
            assert key in entry
        assert entry['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_decision_approve(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            resp = await c.post(
                '/api/approval/decision',
                json={'request_id': request_id, 'decision': 'approve'},
            )
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        assert resp.json()['decision'] == 'approve'

    @pytest.mark.asyncio
    async def test_decision_deny(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            resp = await c.post(
                '/api/approval/decision',
                json={'request_id': request_id, 'decision': 'deny'},
            )
        assert resp.status_code == 200
        assert resp.json()['decision'] == 'deny'

    @pytest.mark.asyncio
    async def test_decision_invalid_value(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            resp = await c.post(
                '/api/approval/decision',
                json={'request_id': request_id, 'decision': 'maybe'},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_double_decision_returns_409(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            await c.post(
                '/api/approval/decision',
                json={'request_id': request_id, 'decision': 'approve'},
            )
            resp = await c.post(
                '/api/approval/decision',
                json={'request_id': request_id, 'decision': 'deny'},
            )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_decision_not_found(self, app):
        async with _client(app) as c:
            resp = await c.post(
                '/api/approval/decision',
                json={'request_id': str(uuid.uuid4()), 'decision': 'approve'},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_status_endpoint(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            resp = await c.get(f'/api/approval/status/{request_id}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['id'] == request_id
        assert data['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_status_not_found(self, app):
        async with _client(app) as c:
            resp = await c.get(f'/api/approval/status/{uuid.uuid4()}')
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_approval(self, app):
        async with _client(app) as c:
            create = await c.post(
                '/api/approval/request',
                json={'tool_name': 'bash', 'description': 'Run tests'},
            )
            request_id = create.json()['request_id']
            resp = await c.delete(f'/api/approval/{request_id}')
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, app):
        async with _client(app) as c:
            resp = await c.delete(f'/api/approval/{uuid.uuid4()}')
        assert resp.status_code == 404


# ── Cross-cutting: Path Validation ──


class TestPathValidationContract:
    """Cross-cutting: path traversal must return 400 on all file/git endpoints."""

    TRAVERSAL_PATHS = ['../../../etc/passwd', '/etc/passwd', '../../..']

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_tree_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.get('/api/tree', params={'path': path})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_file_read_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.get('/api/file', params={'path': path})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_file_write_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.put('/api/file', params={'path': path}, json={'content': 'x'})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_file_delete_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.delete('/api/file', params={'path': path})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_search_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.get('/api/search', params={'q': '*', 'path': path})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_git_diff_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.get('/api/git/diff', params={'path': path})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', TRAVERSAL_PATHS)
    async def test_git_show_rejects_traversal(self, app, path):
        async with _client(app) as c:
            resp = await c.get('/api/git/show', params={'path': path})
        assert resp.status_code == 400
