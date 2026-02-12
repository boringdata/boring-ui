"""Integration tests for boring_ui.api.app.create_app factory.

These tests validate that all modules work together correctly when
assembled through the application factory.
"""
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig


@pytest.fixture
def workspace(tmp_path):
    """Create a test workspace with sample files."""
    # Create test files
    (tmp_path / 'README.md').write_text('# Test Project')
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'main.py').write_text('print("hello")')
    return tmp_path


@pytest.fixture
def app(workspace):
    """Create a full application with all routers enabled."""
    config = APIConfig(workspace_root=workspace)
    return create_app(config)


@pytest.fixture
def minimal_app(workspace):
    """Create a minimal application with only core routers."""
    config = APIConfig(workspace_root=workspace)
    return create_app(config, include_pty=False, include_stream=False, include_approval=False)


class TestAppFactory:
    """Tests for create_app factory function."""

    def test_creates_fastapi_app(self, app):
        """Test that create_app returns a FastAPI application."""
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)
        assert app.title == 'Boring UI API'

    def test_app_has_health_endpoint(self, app):
        """Test that health endpoint is available."""
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert '/health' in paths

    def test_app_has_api_config_endpoint(self, app):
        """Test that config endpoint is available."""
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert '/api/config' in paths

    def test_app_has_capabilities_endpoint(self, app):
        """Test that capabilities endpoint is available."""
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert '/api/capabilities' in paths


class TestHealthEndpoint:
    """Integration tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, app, workspace):
        """Test health endpoint returns status ok."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/health')
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'ok'
            assert data['workspace'] == str(workspace)

    @pytest.mark.asyncio
    async def test_health_includes_all_features(self, app):
        """Test health endpoint includes all enabled features."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/health')
            data = response.json()
            features = data['features']
            assert features['files'] is True
            assert features['git'] is True
            assert features['pty'] is True
            assert features['chat_claude_code'] is True
            assert features['approval'] is True

    @pytest.mark.asyncio
    async def test_minimal_app_features(self, minimal_app):
        """Test minimal app only has core features enabled."""
        transport = ASGITransport(app=minimal_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/health')
            data = response.json()
            features = data['features']
            assert features['files'] is True
            assert features['git'] is True
            assert features['pty'] is False
            assert features['chat_claude_code'] is False
            assert features['approval'] is False


class TestCapabilitiesEndpoint:
    """Integration tests for /api/capabilities endpoint."""

    @pytest.mark.asyncio
    async def test_capabilities_returns_json(self, app):
        """Test capabilities endpoint returns valid JSON."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/capabilities')
            assert response.status_code == 200
            assert response.headers['content-type'] == 'application/json'

    @pytest.mark.asyncio
    async def test_capabilities_has_version(self, app):
        """Test capabilities includes version field."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/capabilities')
            data = response.json()
            assert 'version' in data
            assert data['version'] == '0.1.0'

    @pytest.mark.asyncio
    async def test_capabilities_has_features(self, app):
        """Test capabilities includes features map."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/capabilities')
            data = response.json()
            assert 'features' in data
            assert isinstance(data['features'], dict)

    @pytest.mark.asyncio
    async def test_capabilities_has_routers(self, app):
        """Test capabilities includes router list."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/capabilities')
            data = response.json()
            assert 'routers' in data
            assert isinstance(data['routers'], list)
            router_names = [r['name'] for r in data['routers']]
            assert 'files' in router_names
            assert 'git' in router_names


class TestFileRoutes:
    """Integration tests for file endpoints through full app."""

    @pytest.mark.asyncio
    async def test_tree_endpoint(self, app, workspace):
        """Test /api/tree returns directory listing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/tree?path=.')
            assert response.status_code == 200
            data = response.json()
            names = [e['name'] for e in data['entries']]
            assert 'README.md' in names
            assert 'src' in names

    @pytest.mark.asyncio
    async def test_file_read_endpoint(self, app, workspace):
        """Test /api/file returns file contents."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/file?path=README.md')
            assert response.status_code == 200
            data = response.json()
            assert data['content'] == '# Test Project'

    @pytest.mark.asyncio
    async def test_file_write_endpoint(self, app, workspace):
        """Test PUT /api/file writes file contents."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.put(
                '/api/file?path=new.txt',
                json={'content': 'new content'}
            )
            assert response.status_code == 200
            assert (workspace / 'new.txt').read_text() == 'new content'


class TestConfigEndpoint:
    """Integration tests for /api/config endpoint."""

    @pytest.mark.asyncio
    async def test_config_returns_workspace(self, app, workspace):
        """Test config endpoint returns workspace root."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/config')
            assert response.status_code == 200
            data = response.json()
            assert data['workspace_root'] == str(workspace)

    @pytest.mark.asyncio
    async def test_config_lists_pty_providers(self, app):
        """Test config endpoint lists PTY providers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/api/config')
            data = response.json()
            assert 'pty_providers' in data
            assert 'shell' in data['pty_providers']


class TestRouterSelection:
    """Tests for selective router inclusion."""

    @pytest.mark.asyncio
    async def test_explicit_routers_list(self, workspace):
        """Test explicit routers list overrides include_* flags."""
        config = APIConfig(workspace_root=workspace)
        app = create_app(config, routers=['files'])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/health')
            data = response.json()
            assert data['features']['files'] is True
            assert data['features']['git'] is False

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_chat_claude_code_name_works(self, workspace):
        """Test chat_claude_code router enables chat feature."""
        config = APIConfig(workspace_root=workspace)
        app = create_app(config, routers=['files', 'chat_claude_code'])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.get('/health')
            data = response.json()
            assert data['features']['chat_claude_code'] is True


class TestWebSocketRoutes:
    """Integration tests for WebSocket route availability."""

    def test_pty_websocket_registered(self, app):
        """Test PTY WebSocket route is registered."""
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert '/ws/pty' in paths

    def test_stream_websocket_registered(self, app):
        """Test Claude stream WebSocket route is registered."""
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert '/ws/claude-stream' in paths

    def test_minimal_app_no_websockets(self, minimal_app):
        """Test minimal app doesn't have WebSocket routes."""
        paths = [r.path for r in minimal_app.routes if hasattr(r, 'path')]
        assert '/ws/pty' not in paths
        assert '/ws/claude-stream' not in paths
