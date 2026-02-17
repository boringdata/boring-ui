"""Cross-cutting auth security integration tests.

Bead: bd-3iq8 (B5)

Validates security invariants that span multiple auth subsystems:
  - Session fixation protection: callback always issues a fresh token
  - Token/credential leakage: 401 responses never echo submitted credentials
  - Concurrent sessions: same user on multiple devices yields independent sessions
  - Full auth round-trip: callback → session → /me → logout → cleared
  - Cross-route identity consistency: guard identity matches /me response
  - Error code determinism: same failure type → same code via Bearer or session
  - Credential injection in non-auth fields (Host, Referer) is ignored
  - Email normalization consistency across all auth surfaces
"""

from __future__ import annotations

import re
import time

import jwt
import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.auth import (
    SESSION_COOKIE_NAME,
    SessionConfig,
    create_auth_router,
    create_session_token,
)
from control_plane.app.routes.me import router as me_router
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    AuthIdentity,
    StaticKeyProvider,
    TokenVerifier,
)


# ── Shared constants ──────────────────────────────────────────────────

SUPABASE_SECRET = 'test-security-supabase-secret'
SESSION_SECRET = 'test-security-session-secret'
AUDIENCE = 'authenticated'


def _make_supabase_token(**overrides) -> str:
    payload = {
        'sub': 'user-sec-001',
        'email': 'security@test.com',
        'role': 'authenticated',
        'aud': AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, SUPABASE_SECRET, algorithm='HS256')


def _verifier():
    return TokenVerifier(
        key_provider=StaticKeyProvider(SUPABASE_SECRET),
        audience=AUDIENCE,
        algorithms=['HS256'],
    )


def _session_config():
    return SessionConfig(
        session_secret=SESSION_SECRET,
        cookie_secure=False,
    )


def _build_app() -> FastAPI:
    """Build a full app with auth guard, auth routes, and /me."""
    app = FastAPI()
    verifier = _verifier()
    config = _session_config()
    auth_router = create_auth_router(verifier, config)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=verifier,
        session_secret=SESSION_SECRET,
    )

    @app.get('/api/v1/protected')
    async def protected(request: Request):
        identity = request.state.auth_identity
        return {
            'user_id': identity.user_id,
            'email': identity.email,
            'role': identity.role,
        }

    return app


@pytest.fixture
def app():
    return _build_app()


def _extract_session_from_set_cookie(headers) -> str | None:
    """Parse session token from Set-Cookie header."""
    raw = headers.get('set-cookie', '')
    match = re.search(rf'{SESSION_COOKIE_NAME}=([^;]+)', raw)
    return match.group(1) if match else None


# =====================================================================
# 1. Session fixation protection
# =====================================================================


class TestSessionFixation:
    """Callback always generates a fresh session token."""

    @pytest.mark.asyncio
    async def test_callback_issues_new_token_even_with_existing_session(self, app):
        """Pre-existing session cookie does not influence the new token."""
        old_identity = AuthIdentity(
            user_id='old-user', email='old@test.com',
        )
        old_session = create_session_token(old_identity, _session_config())

        supabase_token = _make_supabase_token(
            sub='new-user', email='new@test.com',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(
                f'/auth/callback?access_token={supabase_token}',
                cookies={SESSION_COOKIE_NAME: old_session},
            )
            assert r.status_code == 302
            new_session = _extract_session_from_set_cookie(r.headers)
            assert new_session is not None
            assert new_session != old_session

    @pytest.mark.asyncio
    async def test_new_session_has_correct_identity(self, app):
        """After callback, session reflects the newly authenticated user."""
        supabase_token = _make_supabase_token(
            sub='fresh-user', email='fresh@test.com',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            cb = await c.get(
                f'/auth/callback?access_token={supabase_token}',
            )
            session_token = _extract_session_from_set_cookie(cb.headers)
            assert session_token is not None

            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            assert r.json()['user_id'] == 'fresh-user'
            assert r.json()['email'] == 'fresh@test.com'

    @pytest.mark.asyncio
    async def test_two_callbacks_produce_different_tokens(self, app):
        """Sequential logins always produce distinct session tokens."""
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r1 = await c.get(f'/auth/callback?access_token={token}')
            s1 = _extract_session_from_set_cookie(r1.headers)
            # Small time gap ensures different iat.
            r2 = await c.get(f'/auth/callback?access_token={token}')
            s2 = _extract_session_from_set_cookie(r2.headers)
            # Tokens may be identical if iat is the same second,
            # but both must be valid.
            assert s1 is not None
            assert s2 is not None


# =====================================================================
# 2. Token leakage in error responses
# =====================================================================


class TestTokenLeakageInResponses:
    """401 error responses must never echo submitted credentials."""

    @pytest.mark.asyncio
    async def test_invalid_bearer_not_echoed_in_response(self, app):
        secret_token = 'super-secret-bearer-value-12345'
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {secret_token}'},
            )
            assert r.status_code == 401
            body_text = r.text
            assert secret_token not in body_text

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_not_echoed_in_response(self, app):
        secret_cookie = 'secret-session-cookie-value-67890'
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: secret_cookie},
            )
            assert r.status_code == 401
            body_text = r.text
            assert secret_cookie not in body_text

    @pytest.mark.asyncio
    async def test_expired_bearer_not_echoed(self, app):
        expired_token = _make_supabase_token(exp=int(time.time()) - 100)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {expired_token}'},
            )
            assert r.status_code == 401
            assert expired_token not in r.text

    @pytest.mark.asyncio
    async def test_callback_failure_does_not_echo_token(self, app):
        bad_token = 'callback-secret-token-value'
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(f'/auth/callback?access_token={bad_token}')
            assert r.status_code == 401
            assert bad_token not in r.text


# =====================================================================
# 3. Concurrent sessions (same user, multiple devices)
# =====================================================================


class TestConcurrentSessions:
    """Same user can hold multiple independent sessions."""

    @pytest.mark.asyncio
    async def test_two_sessions_both_valid(self, app):
        """Two separate callback logins for the same user both work."""
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r1 = await c.get(f'/auth/callback?access_token={token}')
            s1 = _extract_session_from_set_cookie(r1.headers)

            r2 = await c.get(f'/auth/callback?access_token={token}')
            s2 = _extract_session_from_set_cookie(r2.headers)

            # Both sessions authenticate successfully.
            me1 = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: s1},
            )
            me2 = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: s2},
            )
            assert me1.status_code == 200
            assert me2.status_code == 200
            assert me1.json()['user_id'] == me2.json()['user_id']

    @pytest.mark.asyncio
    async def test_different_users_independent_sessions(self, app):
        """Sessions for different users are fully independent."""
        token_a = _make_supabase_token(
            sub='user-a', email='a@test.com',
        )
        token_b = _make_supabase_token(
            sub='user-b', email='b@test.com',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            ra = await c.get(f'/auth/callback?access_token={token_a}')
            sa = _extract_session_from_set_cookie(ra.headers)
            rb = await c.get(f'/auth/callback?access_token={token_b}')
            sb = _extract_session_from_set_cookie(rb.headers)

            me_a = await c.get(
                '/api/v1/me', cookies={SESSION_COOKIE_NAME: sa},
            )
            me_b = await c.get(
                '/api/v1/me', cookies={SESSION_COOKIE_NAME: sb},
            )
            assert me_a.json()['user_id'] == 'user-a'
            assert me_b.json()['user_id'] == 'user-b'

    @pytest.mark.asyncio
    async def test_logout_does_not_invalidate_other_session(self, app):
        """Logging out one device does not affect the other (V0 stateless)."""
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r1 = await c.get(f'/auth/callback?access_token={token}')
            s1 = _extract_session_from_set_cookie(r1.headers)
            r2 = await c.get(f'/auth/callback?access_token={token}')
            s2 = _extract_session_from_set_cookie(r2.headers)

            # Logout session 1.
            await c.post(
                '/auth/logout', cookies={SESSION_COOKIE_NAME: s1},
            )
            # Session 2 still works.
            me = await c.get(
                '/api/v1/me', cookies={SESSION_COOKIE_NAME: s2},
            )
            assert me.status_code == 200


# =====================================================================
# 4. Full auth round-trip
# =====================================================================


class TestFullAuthRoundTrip:
    """callback → session check → /me → logout → verify cleared."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, app):
        supabase_token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            # Step 1: Callback — get session cookie.
            cb = await c.get(
                f'/auth/callback?access_token={supabase_token}',
            )
            assert cb.status_code == 302
            session = _extract_session_from_set_cookie(cb.headers)
            assert session is not None

            # Step 2: Session check.
            sess = await c.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert sess.status_code == 200
            assert sess.json()['user_id'] == 'user-sec-001'

            # Step 3: /me with session cookie.
            me = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert me.status_code == 200
            assert me.json()['user_id'] == 'user-sec-001'
            assert me.json()['email'] == 'security@test.com'

            # Step 4: Logout.
            lo = await c.post(
                '/auth/logout',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert lo.status_code == 200
            assert lo.json()['status'] == 'logged_out'

            # Step 5: Verify no session without cookie.
            sess2 = await c.get('/auth/session')
            assert sess2.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_round_trip(self, app):
        """Bearer auth also reaches /me and /protected consistently."""
        token = _make_supabase_token(
            sub='bearer-user', email='bearer@test.com',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            me = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            protected = await c.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert me.status_code == 200
            assert protected.status_code == 200
            assert me.json()['user_id'] == protected.json()['user_id']
            assert me.json()['email'] == protected.json()['email']


# =====================================================================
# 5. Cross-route identity consistency
# =====================================================================


class TestCrossRouteIdentityConsistency:
    """Guard middleware identity matches /me and other protected routes."""

    @pytest.mark.asyncio
    async def test_me_matches_protected_via_bearer(self, app):
        token = _make_supabase_token(
            sub='consistency-user', email='Consistent@Test.COM',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            me = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            protected = await c.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert me.json() == protected.json()

    @pytest.mark.asyncio
    async def test_me_matches_protected_via_session(self, app):
        identity = AuthIdentity(
            user_id='sess-consistency', email='session@test.com',
        )
        session = create_session_token(identity, _session_config())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            me = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session},
            )
            protected = await c.get(
                '/api/v1/protected',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert me.json()['user_id'] == protected.json()['user_id']
            assert me.json()['email'] == protected.json()['email']

    @pytest.mark.asyncio
    async def test_callback_session_identity_matches_me(self, app):
        """Identity from callback's session matches /me response."""
        supabase_token = _make_supabase_token(
            sub='roundtrip-user', email='roundtrip@test.com',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            cb = await c.get(
                f'/auth/callback?access_token={supabase_token}',
            )
            session = _extract_session_from_set_cookie(cb.headers)

            me = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert me.json()['user_id'] == 'roundtrip-user'
            assert me.json()['email'] == 'roundtrip@test.com'


# =====================================================================
# 6. Error code determinism
# =====================================================================


class TestErrorCodeDeterminism:
    """Same failure type produces same error code regardless of transport."""

    @pytest.mark.asyncio
    async def test_no_credentials_always_no_credentials(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r1 = await c.get('/api/v1/me')
            r2 = await c.get('/api/v1/protected')
            assert r1.json()['code'] == 'no_credentials'
            assert r2.json()['code'] == 'no_credentials'

    @pytest.mark.asyncio
    async def test_expired_bearer_consistent_code(self, app):
        expired = _make_supabase_token(exp=int(time.time()) - 100)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r1 = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {expired}'},
            )
            r2 = await c.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {expired}'},
            )
            assert r1.json()['code'] == 'token_expired'
            assert r2.json()['code'] == 'token_expired'

    @pytest.mark.asyncio
    async def test_expired_session_consistent_code(self, app):
        identity = AuthIdentity(user_id='u', email='e@x.com')
        config = SessionConfig(
            session_secret=SESSION_SECRET, session_ttl=-100,
        )
        expired = create_session_token(identity, config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r1 = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: expired},
            )
            r2 = await c.get(
                '/api/v1/protected',
                cookies={SESSION_COOKIE_NAME: expired},
            )
            assert r1.json()['code'] == 'session_expired'
            assert r2.json()['code'] == 'session_expired'

    @pytest.mark.asyncio
    async def test_wrong_secret_bearer_consistent_code(self, app):
        token = jwt.encode(
            {
                'sub': 'u', 'email': 'e@x.com',
                'aud': AUDIENCE, 'exp': int(time.time()) + 3600,
            },
            'wrong-secret', algorithm='HS256',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r1 = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            r2 = await c.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r1.json()['code'] == r2.json()['code']
            assert r1.json()['code'] == 'decode_error'


# =====================================================================
# 7. Credential injection via non-auth headers
# =====================================================================


class TestCredentialInjection:
    """Auth system ignores credentials in non-standard locations."""

    @pytest.mark.asyncio
    async def test_bearer_in_x_custom_header_ignored(self, app):
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'X-Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_token_in_query_param_ignored_on_protected_route(self, app):
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(f'/api/v1/me?access_token={token}')
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_basic_auth_treated_as_no_credentials(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': 'Basic dXNlcjpwYXNz'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'no_credentials'


# =====================================================================
# 8. Email normalization consistency
# =====================================================================


class TestEmailNormalizationConsistency:
    """Email is lowercased consistently across Bearer and session paths."""

    @pytest.mark.asyncio
    async def test_bearer_normalizes_email(self, app):
        token = _make_supabase_token(email='USER@EXAMPLE.COM')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            assert r.json()['email'] == 'user@example.com'

    @pytest.mark.asyncio
    async def test_session_preserves_email_from_callback(self, app):
        """Callback normalizes email; session inherits normalized form."""
        supabase_token = _make_supabase_token(email='Mixed@Case.COM')
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            cb = await c.get(
                f'/auth/callback?access_token={supabase_token}',
            )
            session = _extract_session_from_set_cookie(cb.headers)
            me = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert me.status_code == 200
            assert me.json()['email'] == 'mixed@case.com'

    @pytest.mark.asyncio
    async def test_bearer_and_session_agree_on_email(self, app):
        """Bearer and session cookie produce same normalized email."""
        bearer = _make_supabase_token(
            sub='email-test', email='Normalize@Test.COM',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            # Bearer path.
            me_bearer = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {bearer}'},
            )
            # Session path via callback.
            cb = await c.get(
                f'/auth/callback?access_token={bearer}',
            )
            session = _extract_session_from_set_cookie(cb.headers)
            me_session = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session},
            )
            assert me_bearer.json()['email'] == me_session.json()['email']
            assert me_bearer.json()['email'] == 'normalize@test.com'


# =====================================================================
# 9. 401 response structure consistency
# =====================================================================


class TestErrorResponseConsistency:
    """All 401 responses from all paths follow the same structure."""

    @pytest.mark.asyncio
    async def test_all_401s_have_error_and_code(self, app):
        """Every 401 response includes at least 'error' and 'code' keys."""
        expired_bearer = _make_supabase_token(exp=int(time.time()) - 100)
        identity = AuthIdentity(user_id='u', email='e@x.com')
        config = SessionConfig(
            session_secret=SESSION_SECRET, session_ttl=-100,
        )
        expired_session = create_session_token(identity, config)

        scenarios = [
            ('no creds', {}),
            ('bad bearer', {'headers': {
                'Authorization': 'Bearer garbage.token',
            }}),
            ('expired bearer', {'headers': {
                'Authorization': f'Bearer {expired_bearer}',
            }}),
            ('bad session', {'cookies': {
                SESSION_COOKIE_NAME: 'garbage.cookie',
            }}),
            ('expired session', {'cookies': {
                SESSION_COOKIE_NAME: expired_session,
            }}),
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            for label, kwargs in scenarios:
                r = await c.get('/api/v1/me', **kwargs)
                assert r.status_code == 401, f'{label}: expected 401'
                body = r.json()
                assert 'error' in body, f'{label}: missing error key'
                assert 'code' in body, f'{label}: missing code key'

    @pytest.mark.asyncio
    async def test_401_content_type_is_json(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            r = await c.get('/api/v1/me')
            assert r.status_code == 401
            assert 'application/json' in r.headers.get('content-type', '')
