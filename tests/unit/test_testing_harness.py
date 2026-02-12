"""Unit tests for the deterministic sandbox test harness."""
import json
import pytest
from pathlib import Path

from boring_ui.api.testing import (
    StubProxyClient,
    StubExecClient,
    StubServicesClient,
    StubResponse,
    FixtureRecorder,
    FixtureReplayer,
    RecordedExchange,
    sandbox_test_app,
    sandbox_config_factory,
    auth_headers,
)


class TestStubResponse:

    def test_defaults(self):
        r = StubResponse()
        assert r.status_code == 200
        assert r.json() == {}
        assert r.text == ''

    def test_json_body(self):
        r = StubResponse(json_body={'key': 'value'})
        assert r.json() == {'key': 'value'}

    def test_text_body(self):
        r = StubResponse(text_body='hello')
        assert r.text == 'hello'


class TestStubProxyClient:

    @pytest.mark.asyncio
    async def test_default_response(self):
        c = StubProxyClient()
        resp = await c.request('GET', '/api/tree')
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_configured_response(self):
        c = StubProxyClient()
        c.set_response('GET', '/api/tree', StubResponse(
            status_code=200,
            json_body={'entries': [], 'path': '.'},
        ))
        resp = await c.request('GET', '/api/tree')
        assert resp.json() == {'entries': [], 'path': '.'}

    @pytest.mark.asyncio
    async def test_records_calls(self):
        c = StubProxyClient()
        await c.request('GET', '/api/tree', params={'path': '.'})
        await c.request('PUT', '/api/file', json={'content': 'x'})
        assert c.call_count == 2
        assert c.calls[0]['method'] == 'GET'
        assert c.calls[1]['method'] == 'PUT'

    @pytest.mark.asyncio
    async def test_error_response(self):
        c = StubProxyClient()
        c.set_response('GET', '/bad', StubResponse(error=ConnectionError('refused')))
        with pytest.raises(ConnectionError):
            await c.request('GET', '/bad')

    @pytest.mark.asyncio
    async def test_reset(self):
        c = StubProxyClient()
        c.set_response('GET', '/api/tree', StubResponse(status_code=404))
        await c.request('GET', '/api/tree')
        c.reset()
        assert c.call_count == 0
        resp = await c.request('GET', '/api/tree')
        assert resp.status_code == 200  # Back to default

    @pytest.mark.asyncio
    async def test_custom_default(self):
        c = StubProxyClient()
        c.set_default(StubResponse(status_code=500))
        resp = await c.request('GET', '/anything')
        assert resp.status_code == 500


class TestStubExecClient:

    @pytest.mark.asyncio
    async def test_create_session(self):
        c = StubExecClient()
        session = await c.create_session('shell')
        assert session['id'].startswith('stub-session-')
        assert session['template_id'] == 'shell'
        assert session['status'] == 'running'

    @pytest.mark.asyncio
    async def test_create_increments_id(self):
        c = StubExecClient()
        s1 = await c.create_session('shell')
        s2 = await c.create_session('claude')
        assert s1['id'] != s2['id']

    @pytest.mark.asyncio
    async def test_terminate(self):
        c = StubExecClient()
        s = await c.create_session('shell')
        result = await c.terminate_session(s['id'])
        assert result is True
        assert c.active_sessions == {}

    @pytest.mark.asyncio
    async def test_terminate_nonexistent(self):
        c = StubExecClient()
        result = await c.terminate_session('nope')
        assert result is False

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        c = StubExecClient()
        await c.create_session('shell')
        await c.create_session('claude')
        sessions = await c.list_sessions()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_create_error(self):
        c = StubExecClient()
        c.set_create_error(RuntimeError('quota exceeded'))
        with pytest.raises(RuntimeError, match='quota exceeded'):
            await c.create_session('shell')
        # Error is consumed; next call works
        s = await c.create_session('shell')
        assert s['status'] == 'running'

    @pytest.mark.asyncio
    async def test_reset(self):
        c = StubExecClient()
        await c.create_session('shell')
        c.reset()
        assert c.call_count == 0
        sessions = await c.list_sessions()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_call_recording(self):
        c = StubExecClient()
        await c.create_session('shell')
        await c.list_sessions()
        assert c.calls[0]['action'] == 'create'
        assert c.calls[1]['action'] == 'list'


class TestStubServicesClient:

    @pytest.mark.asyncio
    async def test_healthy(self):
        c = StubServicesClient(healthy=True)
        h = await c.check_health()
        assert h['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_unhealthy(self):
        c = StubServicesClient(healthy=False)
        h = await c.check_health()
        assert h['status'] == 'unhealthy'

    @pytest.mark.asyncio
    async def test_version(self):
        c = StubServicesClient(version='0.2.0')
        v = await c.check_version()
        assert v['version'] == '0.2.0'

    @pytest.mark.asyncio
    async def test_ready(self):
        c = StubServicesClient(ready=True)
        assert await c.is_ready() is True

    @pytest.mark.asyncio
    async def test_not_ready(self):
        c = StubServicesClient(ready=False)
        assert await c.is_ready() is False

    @pytest.mark.asyncio
    async def test_mutable_state(self):
        c = StubServicesClient(healthy=True)
        c.set_healthy(False)
        h = await c.check_health()
        assert h['status'] == 'unhealthy'

    @pytest.mark.asyncio
    async def test_call_recording(self):
        c = StubServicesClient()
        await c.check_health()
        await c.check_version()
        await c.is_ready()
        assert c.call_count == 3

    @pytest.mark.asyncio
    async def test_reset(self):
        c = StubServicesClient()
        await c.check_health()
        c.reset()
        assert c.call_count == 0


class TestRecordedExchange:

    def test_to_stub_response(self):
        e = RecordedExchange(
            method='GET', path='/api/tree',
            response_status=200,
            response_json={'entries': []},
        )
        r = e.to_stub_response()
        assert r.status_code == 200
        assert r.json() == {'entries': []}


class TestFixtureRecorder:

    def test_record_and_count(self):
        rec = FixtureRecorder()
        rec.record(RecordedExchange(method='GET', path='/api/tree'))
        assert rec.count == 1

    def test_save_and_load(self, tmp_path):
        rec = FixtureRecorder()
        rec.record(RecordedExchange(
            method='GET', path='/api/tree',
            response_status=200,
            response_json={'entries': ['a', 'b']},
        ))
        fixture_path = tmp_path / 'test.json'
        rec.save(fixture_path)

        data = json.loads(fixture_path.read_text())
        assert len(data) == 1
        assert data[0]['method'] == 'GET'
        assert data[0]['response_json'] == {'entries': ['a', 'b']}

    def test_clear(self):
        rec = FixtureRecorder()
        rec.record(RecordedExchange(method='GET', path='/test'))
        rec.clear()
        assert rec.count == 0


class TestFixtureReplayer:

    def test_from_exchanges(self):
        exchanges = [
            RecordedExchange(method='GET', path='/api/tree', response_status=200),
        ]
        replayer = FixtureReplayer.from_exchanges(exchanges)
        assert replayer.count == 1

    def test_from_file(self, tmp_path):
        fixture_path = tmp_path / 'test.json'
        data = [{
            'method': 'GET',
            'path': '/api/tree',
            'response_status': 200,
            'response_json': {'entries': []},
        }]
        fixture_path.write_text(json.dumps(data))

        replayer = FixtureReplayer.from_file(fixture_path)
        assert replayer.count == 1

    @pytest.mark.asyncio
    async def test_to_stub_client(self):
        exchanges = [
            RecordedExchange(
                method='GET', path='/api/tree',
                response_status=200,
                response_json={'entries': ['file.txt']},
            ),
            RecordedExchange(
                method='GET', path='/api/file',
                response_status=200,
                response_json={'content': 'hello'},
            ),
        ]
        replayer = FixtureReplayer.from_exchanges(exchanges)
        client = replayer.to_stub_client()

        resp = await client.request('GET', '/api/tree')
        assert resp.json() == {'entries': ['file.txt']}

        resp = await client.request('GET', '/api/file')
        assert resp.json() == {'content': 'hello'}

    def test_roundtrip(self, tmp_path):
        rec = FixtureRecorder()
        rec.record(RecordedExchange(
            method='POST', path='/api/file/rename',
            response_status=200, response_json={'ok': True},
        ))
        fixture_path = tmp_path / 'rt.json'
        rec.save(fixture_path)

        replayer = FixtureReplayer.from_file(fixture_path)
        assert replayer.count == 1
        assert replayer.exchanges[0].path == '/api/file/rename'


class TestFactories:

    def test_sandbox_config_factory(self):
        cfg = sandbox_config_factory()
        assert cfg.sprite_name == 'test-sprite'
        assert cfg.service_target.host == 'workspace-service'

    def test_sandbox_config_custom(self):
        cfg = sandbox_config_factory(
            sprite_name='my-sprite',
            service_port=9090,
        )
        assert cfg.sprite_name == 'my-sprite'
        assert cfg.service_target.port == 9090

    def test_auth_headers(self):
        h = auth_headers()
        assert 'X-Workspace-Internal-Auth' in h
        assert h['X-Workspace-Internal-Auth'].startswith('hmac-sha256:')

    def test_sandbox_test_app(self, tmp_path):
        app = sandbox_test_app(workspace_root=tmp_path)
        assert app is not None
        # Should have sandbox runtime config
        assert app.state.runtime_config.workspace_mode == 'sandbox'
