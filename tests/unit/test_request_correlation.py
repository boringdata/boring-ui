"""Unit tests for request correlation ID propagation."""
import logging
import uuid

import pytest

from boring_ui.api.request_correlation import (
    REQUEST_ID_HEADER,
    UPSTREAM_REQUEST_ID_HEADER,
    CorrelationLogFilter,
    RequestCorrelationMiddleware,
    current_request_id,
    extract_request_id,
    generate_request_id,
    get_or_create_request_id,
    inject_request_id,
)


class TestGenerateRequestId:

    def test_is_uuid4(self):
        rid = generate_request_id()
        parsed = uuid.UUID(rid)
        assert parsed.version == 4

    def test_unique(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100


class TestGetOrCreateRequestId:

    def test_returns_provided(self):
        assert get_or_create_request_id('my-id') == 'my-id'

    def test_strips_whitespace(self):
        assert get_or_create_request_id('  my-id  ') == 'my-id'

    def test_generates_when_none(self):
        rid = get_or_create_request_id(None)
        uuid.UUID(rid)  # Valid UUID

    def test_generates_when_empty(self):
        rid = get_or_create_request_id('')
        uuid.UUID(rid)

    def test_generates_when_whitespace(self):
        rid = get_or_create_request_id('   ')
        uuid.UUID(rid)


class TestExtractRequestId:

    def test_found(self):
        assert extract_request_id({'X-Request-ID': 'abc-123'}) == 'abc-123'

    def test_case_insensitive(self):
        assert extract_request_id({'x-request-id': 'abc'}) == 'abc'

    def test_not_found(self):
        assert extract_request_id({'Other': 'value'}) is None

    def test_empty_value(self):
        assert extract_request_id({'X-Request-ID': ''}) is None

    def test_strips_whitespace(self):
        assert extract_request_id({'X-Request-ID': '  abc  '}) == 'abc'


class TestInjectRequestId:

    def test_adds_header(self):
        h = inject_request_id({}, 'req-1')
        assert h[REQUEST_ID_HEADER] == 'req-1'

    def test_preserves_existing(self):
        h = inject_request_id({'Accept': 'json'}, 'req-1')
        assert h['Accept'] == 'json'
        assert h[REQUEST_ID_HEADER] == 'req-1'

    def test_upstream_mode(self):
        h = inject_request_id({}, 'req-1', as_upstream=True)
        assert h[REQUEST_ID_HEADER] == 'req-1'
        assert h[UPSTREAM_REQUEST_ID_HEADER] == 'req-1'

    def test_no_upstream_by_default(self):
        h = inject_request_id({}, 'req-1')
        assert UPSTREAM_REQUEST_ID_HEADER not in h

    def test_does_not_mutate_input(self):
        original = {'Content-Type': 'json'}
        inject_request_id(original, 'req-1')
        assert REQUEST_ID_HEADER not in original


class TestContextVar:

    def test_default_empty(self):
        assert current_request_id.get() == ''

    def test_set_and_get(self):
        token = current_request_id.set('test-id')
        try:
            assert current_request_id.get() == 'test-id'
        finally:
            current_request_id.reset(token)


class TestRequestCorrelationMiddleware:

    @pytest.fixture
    def app_untrusted(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get('/test')
        async def test_route():
            return {'request_id': current_request_id.get()}

        app.add_middleware(RequestCorrelationMiddleware, trust_incoming=False)
        return app

    @pytest.fixture
    def app_trusted(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get('/test')
        async def test_route():
            return {'request_id': current_request_id.get()}

        app.add_middleware(RequestCorrelationMiddleware, trust_incoming=True)
        return app

    @pytest.mark.asyncio
    async def test_generates_id(self, app_untrusted):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app_untrusted), base_url='http://test',
        ) as c:
            resp = await c.get('/test')
        assert resp.status_code == 200
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid is not None
        uuid.UUID(rid)  # Valid UUID

    @pytest.mark.asyncio
    async def test_ignores_client_id_when_untrusted(self, app_untrusted):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app_untrusted), base_url='http://test',
        ) as c:
            resp = await c.get(
                '/test',
                headers={REQUEST_ID_HEADER: 'client-id'},
            )
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid != 'client-id'

    @pytest.mark.asyncio
    async def test_trusts_client_id_when_configured(self, app_trusted):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app_trusted), base_url='http://test',
        ) as c:
            resp = await c.get(
                '/test',
                headers={REQUEST_ID_HEADER: 'client-id'},
            )
        assert resp.headers.get(REQUEST_ID_HEADER) == 'client-id'
        assert resp.json()['request_id'] == 'client-id'

    @pytest.mark.asyncio
    async def test_contextvar_set_in_handler(self, app_untrusted):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app_untrusted), base_url='http://test',
        ) as c:
            resp = await c.get('/test')
        body_rid = resp.json()['request_id']
        header_rid = resp.headers.get(REQUEST_ID_HEADER)
        assert body_rid == header_rid

    @pytest.mark.asyncio
    async def test_contextvar_reset_after_request(self, app_untrusted):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app_untrusted), base_url='http://test',
        ) as c:
            await c.get('/test')
        # After request completes, ContextVar should be back to default
        assert current_request_id.get() == ''


class TestCorrelationLogFilter:

    def test_adds_request_id_to_record(self):
        f = CorrelationLogFilter()
        token = current_request_id.set('log-test-id')
        try:
            record = logging.LogRecord(
                'test', logging.INFO, '', 0, 'message', None, None,
            )
            f.filter(record)
            assert record.request_id == 'log-test-id'  # type: ignore[attr-defined]
        finally:
            current_request_id.reset(token)

    def test_empty_when_no_context(self):
        f = CorrelationLogFilter()
        record = logging.LogRecord(
            'test', logging.INFO, '', 0, 'message', None, None,
        )
        f.filter(record)
        assert record.request_id == ''  # type: ignore[attr-defined]

    def test_always_returns_true(self):
        f = CorrelationLogFilter()
        record = logging.LogRecord(
            'test', logging.INFO, '', 0, 'message', None, None,
        )
        assert f.filter(record) is True
