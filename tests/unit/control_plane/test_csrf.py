"""CSRF protection unit and integration tests.

Bead: bd-3499 (B6)

Tests:
  - Token generation entropy and uniqueness
  - Timing-safe validation (all failure modes)
  - Middleware: safe methods pass through
  - Middleware: mutations without token → 403
  - Middleware: mutations with wrong token → 403
  - Middleware: mutations with valid token → 200
  - Middleware: exempt paths bypass validation
  - Middleware: exempt_check callable bypass
  - Middleware: missing session token → 403
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from control_plane.app.security.csrf import (
    CSRF_TOKEN_HEADER,
    CSRFError,
    CSRFMiddleware,
    generate_csrf_token,
    validate_csrf_token,
)

# =====================================================================
# Token generation
# =====================================================================


class TestGenerateCSRFToken:
    """Token generation must produce unique, high-entropy tokens."""

    def test_returns_string(self):
        token = generate_csrf_token()
        assert isinstance(token, str)

    def test_nonzero_length(self):
        token = generate_csrf_token()
        assert len(token) > 0

    def test_minimum_entropy(self):
        """256-bit token_urlsafe produces ~43 chars."""
        token = generate_csrf_token()
        assert len(token) >= 40

    def test_tokens_are_unique(self):
        """Sequential tokens must differ (probabilistic but near-certain)."""
        tokens = {generate_csrf_token() for _ in range(100)}
        assert len(tokens) == 100


# =====================================================================
# Token validation
# =====================================================================


class TestValidateCSRFToken:
    """Timing-safe validation must reject all invalid inputs."""

    def test_valid_token_passes(self):
        token = generate_csrf_token()
        validate_csrf_token(token, token)  # Should not raise.

    def test_missing_session_token(self):
        with pytest.raises(CSRFError, match='no_session_token'):
            validate_csrf_token(None, 'some_token')

    def test_missing_client_token(self):
        with pytest.raises(CSRFError, match='missing_csrf_token'):
            validate_csrf_token('expected', None)

    def test_empty_client_token(self):
        with pytest.raises(CSRFError, match='empty_csrf_token'):
            validate_csrf_token('expected', '')

    def test_mismatched_tokens(self):
        with pytest.raises(CSRFError, match='csrf_token_mismatch'):
            validate_csrf_token('token_a', 'token_b')

    def test_csrf_error_has_reason(self):
        err = CSRFError('test_reason')
        assert err.reason == 'test_reason'
        assert 'test_reason' in str(err)


# =====================================================================
# Middleware integration (FastAPI + httpx)
# =====================================================================


class _FakeSessionMiddleware(BaseHTTPMiddleware):
    """Test helper: sets csrf_token on request.state before CSRF check."""

    def __init__(self, app, token: str | None = None):
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        request.state.csrf_token = self._token
        return await call_next(request)


def _build_app(
    session_token: str | None = None,
    exempt_paths: tuple[str, ...] = (),
    exempt_check=None,
) -> FastAPI:
    """Build a minimal FastAPI app with CSRF middleware for testing.

    Middleware order (outermost first): FakeSession → CSRF → routes.
    """
    app = FastAPI()

    # add_middleware stacks: last added = outermost.
    # CSRF must be inner (added first), session must be outer (added last).
    app.add_middleware(
        CSRFMiddleware,
        exempt_paths=exempt_paths,
        exempt_check=exempt_check,
    )
    app.add_middleware(_FakeSessionMiddleware, token=session_token)

    @app.get('/api/resource')
    async def get_resource(request: Request):
        return {'status': 'ok'}

    @app.post('/api/resource')
    async def create_resource(request: Request):
        return {'status': 'created'}

    @app.put('/api/resource')
    async def update_resource(request: Request):
        return {'status': 'updated'}

    @app.patch('/api/resource')
    async def patch_resource(request: Request):
        return {'status': 'patched'}

    @app.delete('/api/resource')
    async def delete_resource(request: Request):
        return {'status': 'deleted'}

    @app.post('/auth/callback')
    async def auth_callback(request: Request):
        return {'status': 'authenticated'}

    @app.post('/api/service')
    async def service_endpoint(request: Request):
        return {'status': 'service_ok'}

    return app


@pytest.fixture
def csrf_token():
    return generate_csrf_token()


class TestCSRFMiddlewareSafeMethods:
    """GET/HEAD/OPTIONS must always pass through."""

    @pytest.mark.asyncio
    async def test_get_always_passes(self):
        app = _build_app(session_token=None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/resource')
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_options_always_passes(self):
        app = _build_app(session_token=None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.options('/api/resource')
            # FastAPI returns 405 for OPTIONS on routes without CORS,
            # but the CSRF middleware itself does not block it.
            assert resp.status_code != 403

    @pytest.mark.asyncio
    async def test_head_always_passes(self):
        app = _build_app(session_token=None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.head('/api/resource')
            # HEAD is a safe method — CSRF middleware must not block it.
            # FastAPI may return 200 (auto-HEAD from GET) or 405.
            assert resp.status_code != 403


class TestCSRFMiddlewareMutationBlocking:
    """Mutations without a valid CSRF token must be rejected."""

    @pytest.mark.asyncio
    async def test_post_without_token_returns_403(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post('/api/resource')
            assert resp.status_code == 403
            body = resp.json()
            assert body['error'] == 'csrf_validation_failed'
            assert body['reason'] == 'missing_csrf_token'

    @pytest.mark.asyncio
    async def test_put_without_token_returns_403(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.put('/api/resource')
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_without_token_returns_403(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.patch('/api/resource')
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_without_token_returns_403(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete('/api/resource')
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_token_returns_403(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                '/api/resource',
                headers={CSRF_TOKEN_HEADER: 'wrong_token'},
            )
            assert resp.status_code == 403
            body = resp.json()
            assert body['reason'] == 'csrf_token_mismatch'


class TestCSRFMiddlewareValidToken:
    """Mutations with a valid CSRF token must pass through."""

    @pytest.mark.asyncio
    async def test_post_with_valid_token(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                '/api/resource',
                headers={CSRF_TOKEN_HEADER: csrf_token},
            )
            assert resp.status_code == 200
            assert resp.json()['status'] == 'created'

    @pytest.mark.asyncio
    async def test_put_with_valid_token(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.put(
                '/api/resource',
                headers={CSRF_TOKEN_HEADER: csrf_token},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_with_valid_token(self, csrf_token):
        app = _build_app(session_token=csrf_token)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.delete(
                '/api/resource',
                headers={CSRF_TOKEN_HEADER: csrf_token},
            )
            assert resp.status_code == 200


class TestCSRFMiddlewareExemptions:
    """Exempt paths and custom checks must bypass validation."""

    @pytest.mark.asyncio
    async def test_exempt_path_bypasses_csrf(self, csrf_token):
        app = _build_app(
            session_token=csrf_token,
            exempt_paths=('/auth/',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post('/auth/callback')
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_non_exempt_path_still_checked(self, csrf_token):
        app = _build_app(
            session_token=csrf_token,
            exempt_paths=('/auth/',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post('/api/resource')
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_exempt_check_callable(self, csrf_token):
        """Custom exempt_check can bypass CSRF for service calls."""
        def is_service_call(request: Request) -> bool:
            return request.url.path.startswith('/api/service')

        app = _build_app(
            session_token=csrf_token,
            exempt_check=is_service_call,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            # Service path is exempt.
            resp = await client.post('/api/service')
            assert resp.status_code == 200

            # Non-service path still requires CSRF token.
            resp = await client.post('/api/resource')
            assert resp.status_code == 403


class TestCSRFMiddlewareNoSession:
    """When no session token is set, mutations must fail gracefully."""

    @pytest.mark.asyncio
    async def test_no_session_token_returns_403(self):
        app = _build_app(session_token=None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.post(
                '/api/resource',
                headers={CSRF_TOKEN_HEADER: 'some_token'},
            )
            assert resp.status_code == 403
            body = resp.json()
            assert body['reason'] == 'no_session_token'
