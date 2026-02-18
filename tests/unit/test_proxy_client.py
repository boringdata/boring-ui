"""Unit tests for SpritesProxyClient."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from boring_ui.api.proxy_client import (
    ProxyError,
    ProxyResponse,
    SpritesProxyClient,
)
from boring_ui.api.proxy_guardrails import (
    AllowedTarget,
    ProxyGuardrailConfig,
    ProxyRequestDenied,
)
from boring_ui.api.config import SandboxConfig, SandboxServiceTarget, SpriteLayout


# ── Helpers ──


def _sandbox_config(**overrides) -> SandboxConfig:
    defaults = dict(
        base_url='https://sprites.internal',
        sprite_name='test-sprite',
        api_token='a' * 64,
        session_token_secret='b' * 64,
        service_target=SandboxServiceTarget(
            host='localhost', port=9000, path='/workspace',
        ),
        sprite_layout=SpriteLayout(),
    )
    defaults.update(overrides)
    return SandboxConfig(**defaults)


def _guardrails(**overrides) -> ProxyGuardrailConfig:
    defaults = dict(
        allowed_targets=(AllowedTarget('localhost', 9000),),
        allowed_path_prefixes=('/api/', '/healthz', '/__meta/'),
    )
    defaults.update(overrides)
    return ProxyGuardrailConfig(**defaults)


def _mock_httpx_response(
    status_code=200,
    json_data=None,
    text_data='',
    headers=None,
    content=None,
):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {'content-type': 'application/json'}
    resp.json.return_value = json_data if json_data is not None else {}
    resp.content = content or b'{}'
    resp.text = text_data or '{}'
    return resp


def _patch_httpx(mock_response):
    """Create a context manager that patches httpx.AsyncClient."""
    mock_cls = patch('boring_ui.api.proxy_client.httpx.AsyncClient')
    return mock_cls, mock_response


# ── ProxyResponse tests ──


class TestProxyResponse:

    def test_json(self):
        r = ProxyResponse(
            status_code=200, headers={}, body=b'{}',
            json_body={'key': 'value'},
        )
        assert r.json() == {'key': 'value'}

    def test_json_none(self):
        r = ProxyResponse(status_code=200, headers={}, body=b'')
        assert r.json() == {}

    def test_text(self):
        r = ProxyResponse(
            status_code=200, headers={}, body=b'hello',
            text_body='hello',
        )
        assert r.text == 'hello'


# ── Guardrail validation tests ──


class TestGuardrailValidation:

    def test_defaults_allow_configured_target(self):
        client = SpritesProxyClient(_sandbox_config())
        # Should use sandbox_config.service_target automatically.
        client._validate_request('GET', '/api/tree')

    def test_denies_unallowed_target(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(
                allowed_targets=(AllowedTarget('other-host', 8080),),
            ),
        )
        with pytest.raises(ProxyRequestDenied):
            client._validate_request('GET', '/api/tree')

    def test_denies_unallowed_path(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )
        with pytest.raises(ProxyRequestDenied):
            client._validate_request('GET', '/admin/secret')

    def test_denies_path_traversal(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )
        with pytest.raises(ProxyRequestDenied):
            client._validate_request('GET', '/api/../etc/passwd')

    def test_denies_unallowed_method(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )
        with pytest.raises(ProxyRequestDenied):
            client._validate_request('OPTIONS', '/api/tree')

    def test_allows_valid_request(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )
        # Should not raise
        client._validate_request('GET', '/api/tree')
        client._validate_request('POST', '/api/sessions')
        client._validate_request('PUT', '/api/file')
        client._validate_request('DELETE', '/api/file')


# ── Request execution tests ──


class TestRequestExecution:

    @pytest.fixture
    def client(self):
        return SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )

    @pytest.mark.asyncio
    async def test_successful_json_response(self, client):
        resp = _mock_httpx_response(200, json_data={'entries': []})
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            result = await client.request('GET', '/api/tree')
        assert result.status_code == 200
        assert result.json() == {'entries': []}

    @pytest.mark.asyncio
    async def test_sends_auth_headers(self, client):
        resp = _mock_httpx_response(200)
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            await client.request('GET', '/api/tree')

            call_args = mock_ctx.request.call_args
            headers = call_args.kwargs.get('headers', {})
            assert 'X-Workspace-Internal-Auth' in headers
            assert 'X-Workspace-API-Version' in headers

    @pytest.mark.asyncio
    async def test_strips_sensitive_request_headers(self, client):
        resp = _mock_httpx_response(200)
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            await client.request(
                'GET', '/api/tree',
                headers={'Authorization': 'Bearer token', 'X-Custom': 'keep'},
            )

            call_args = mock_ctx.request.call_args
            headers = call_args.kwargs.get('headers', {})
            # Authorization should be stripped
            assert 'Authorization' not in headers
            # Custom header should be preserved
            assert headers.get('X-Custom') == 'keep'

    @pytest.mark.asyncio
    async def test_passes_query_params(self, client):
        resp = _mock_httpx_response(200)
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            await client.request('GET', '/api/tree', params={'path': '/'})

            call_args = mock_ctx.request.call_args
            assert call_args.kwargs.get('params') == {'path': '/'}

    @pytest.mark.asyncio
    async def test_passes_json_body(self, client):
        resp = _mock_httpx_response(200)
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            await client.request(
                'PUT', '/api/file',
                json={'content': 'hello'},
            )

            call_args = mock_ctx.request.call_args
            assert call_args.kwargs.get('json') == {'content': 'hello'}

    @pytest.mark.asyncio
    async def test_no_redirect_following(self, client):
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            # Check that AsyncClient is called with follow_redirects=False
            await client.request('GET', '/api/tree') if False else None
            # Instead, check the constructor call
            mock_cls.assert_not_called()  # We haven't actually called yet

        # Verify follow_redirects=False by checking constructor args
        resp = _mock_httpx_response(200)
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            await client.request('GET', '/api/tree')
            mock_cls.assert_called_once_with(
                timeout=30.0,
                follow_redirects=False,
            )


# ── Error handling tests ──


class TestErrorHandling:

    @pytest.fixture
    def client(self):
        return SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )

    @pytest.mark.asyncio
    async def test_connection_error_raises_503(self, client):
        import httpx as httpx_mod
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(
                side_effect=httpx_mod.ConnectError('refused')
            )
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client.request('GET', '/api/tree')
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self, client):
        import httpx as httpx_mod
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(
                side_effect=httpx_mod.ReadTimeout('timeout')
            )
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client.request('GET', '/api/tree')
            assert exc.value.status_code == 504

    @pytest.mark.asyncio
    async def test_redirect_raises_502(self, client):
        resp = _mock_httpx_response(302, headers={
            'content-type': 'text/html',
            'location': 'http://evil.com',
        })
        resp.content = b''
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client.request('GET', '/api/tree')
            assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_upstream_500_maps_to_502(self, client):
        resp = _mock_httpx_response(500, json_data={'error': 'internal'})
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            result = await client.request('GET', '/api/tree')
        assert result.status_code == 502
        assert result.json() == {'error': 'Workspace service error'}
        assert b'internal' not in result.body

    @pytest.mark.asyncio
    async def test_upstream_404_passes_through(self, client):
        resp = _mock_httpx_response(404, json_data={'error': 'not found'})
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            result = await client.request('GET', '/api/file')
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_upstream_400_passes_through(self, client):
        resp = _mock_httpx_response(400, json_data={'error': 'bad request'})
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            result = await client.request('GET', '/api/file')
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_response_too_large_by_content_length(self, client):
        resp = _mock_httpx_response(200, headers={
            'content-type': 'application/json',
            'content-length': str(20 * 1024 * 1024),  # 20 MB
        })
        resp.content = b'x'  # small actual content
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client.request('GET', '/api/tree')
            assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_response_too_large_by_body(self, client):
        config = _guardrails()
        client_small = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=ProxyGuardrailConfig(
                allowed_targets=config.allowed_targets,
                allowed_path_prefixes=config.allowed_path_prefixes,
                max_response_bytes=10,
            ),
        )
        resp = _mock_httpx_response(200, headers={'content-type': 'text/plain'})
        resp.content = b'x' * 100
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client_small.request('GET', '/api/tree')
            assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_guardrail_denial_propagates(self, client):
        # Test with unallowed path
        with pytest.raises(ProxyRequestDenied):
            await client.request('GET', '/admin/nope')

    @pytest.mark.asyncio
    async def test_unexpected_error_raises_502(self, client):
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=RuntimeError('oops'))
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            with pytest.raises(ProxyError) as exc:
                await client.request('GET', '/api/tree')
            assert exc.value.status_code == 502


# ── Response header sanitization tests ──


class TestResponseHeaderSanitization:

    @pytest.fixture
    def client(self):
        return SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )

    @pytest.mark.asyncio
    async def test_strips_hop_by_hop_from_response(self, client):
        resp = _mock_httpx_response(
            200,
            json_data={'ok': True},
            headers={
                'content-type': 'application/json',
                'connection': 'keep-alive',
                'transfer-encoding': 'chunked',
                'x-custom': 'keep-this',
            },
        )
        with patch('boring_ui.api.proxy_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_ctx.is_closed = False
            mock_cls.return_value = mock_ctx

            result = await client.request('GET', '/api/tree')
        assert 'connection' not in result.headers
        assert 'transfer-encoding' not in result.headers
        assert result.headers.get('x-custom') == 'keep-this'


# ── Client properties tests ──


class TestClientProperties:

    def test_base_url(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            guardrail_config=_guardrails(),
        )
        assert client.base_url == 'http://localhost:9000/workspace'

    def test_custom_timeout(self):
        client = SpritesProxyClient(
            _sandbox_config(),
            timeout=10.0,
            guardrail_config=_guardrails(),
        )
        assert client._timeout == 10.0
