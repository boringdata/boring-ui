"""Auth callback and session management routes.

Bead: bd-223o.7.2 (B2)

Implements:
  - ``GET /auth/callback`` — Supabase auth callback that verifies the
    access token and issues a secure app session cookie.
  - Session cookie with required security flags (design doc 13.1):
    - ``HttpOnly=true``
    - ``Secure=true`` (except explicit local-dev override)
    - ``SameSite=Lax``
    - Bounded TTL with rolling refresh.

Session storage:
  V0 uses a simple signed cookie approach — the session payload is
  a signed JWT issued by the control plane with the verified identity.
  This avoids server-side session storage in V0. Future versions may
  use Redis or database-backed sessions.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import jwt
from fastapi import APIRouter, Query, Request
from starlette.responses import JSONResponse, RedirectResponse

from control_plane.app.security.token_verify import (
    AuthIdentity,
    TokenVerificationError,
    TokenVerifier,
)

# ── Constants ─────────────────────────────────────────────────────────

SESSION_COOKIE_NAME = 'boring_session'
SESSION_TTL_SECONDS = 3600 * 24  # 24 hours
SESSION_ROLLING_THRESHOLD = 3600  # Refresh if <1 hour remaining
DEFAULT_REDIRECT_PATH = '/'

# ── Configuration ────────────────────────────────────────────────────


@dataclass
class SessionConfig:
    """Session cookie configuration.

    Args:
        session_secret: Secret key for signing session JWTs.
        cookie_secure: Whether to set Secure flag (False for local dev).
        cookie_domain: Optional domain for the cookie.
        session_ttl: Session TTL in seconds.
        redirect_path: Where to redirect after successful callback.
    """

    session_secret: str
    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_ttl: int = SESSION_TTL_SECONDS
    redirect_path: str = DEFAULT_REDIRECT_PATH

    @classmethod
    def for_local_dev(cls, session_secret: str | None = None) -> SessionConfig:
        """Create config suitable for local development."""
        return cls(
            session_secret=session_secret or secrets.token_urlsafe(32),
            cookie_secure=False,
            session_ttl=SESSION_TTL_SECONDS,
        )


# ── Session helpers ──────────────────────────────────────────────────


def create_session_token(
    identity: AuthIdentity,
    config: SessionConfig,
) -> str:
    """Create a signed session JWT from a verified identity.

    The session token is a lightweight JWT signed with the control plane's
    session secret (HS256). It contains the minimum claims needed for
    session validation.
    """
    now = int(time.time())
    payload = {
        'sub': identity.user_id,
        'email': identity.email,
        'role': identity.role,
        'iat': now,
        'exp': now + config.session_ttl,
        'type': 'session',
    }
    return jwt.encode(payload, config.session_secret, algorithm='HS256')


def verify_session_token(
    token: str,
    config: SessionConfig,
) -> dict:
    """Verify and decode a session JWT.

    Returns the decoded claims dict.

    Raises:
        jwt.InvalidTokenError: If verification fails.
    """
    return jwt.decode(
        token,
        config.session_secret,
        algorithms=['HS256'],
        options={
            'require': ['sub', 'exp', 'type'],
            'verify_exp': True,
        },
    )


def should_refresh_session(claims: dict, config: SessionConfig) -> bool:
    """Check if the session token should be refreshed (rolling expiry)."""
    exp = claims.get('exp', 0)
    remaining = exp - int(time.time())
    return remaining < SESSION_ROLLING_THRESHOLD


# ── Route factory ────────────────────────────────────────────────────


def create_auth_router(
    token_verifier: TokenVerifier,
    session_config: SessionConfig,
) -> APIRouter:
    """Create the auth router with callback and session routes.

    Args:
        token_verifier: Verifier for Supabase access tokens.
        session_config: Configuration for session cookies.

    Returns:
        FastAPI router with auth routes.
    """
    router = APIRouter(tags=['auth'])

    @router.get('/auth/callback')
    async def auth_callback(
        request: Request,
        access_token: str | None = Query(default=None),
    ):
        """Handle Supabase auth callback.

        The Supabase auth flow redirects here with the access token
        as a query parameter (or in the URL fragment for implicit flow).

        1. Extract the access token from query params.
        2. Verify the token using JWKS.
        3. Create a session JWT and set it as an HTTP-only cookie.
        4. Redirect to the app.
        """
        if not access_token:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'missing_token',
                    'detail': 'access_token query parameter is required',
                },
            )

        # Verify the Supabase access token.
        try:
            identity = token_verifier.verify(access_token)
        except TokenVerificationError as exc:
            return JSONResponse(
                status_code=401,
                content={
                    'error': 'auth_callback_failed',
                    'code': exc.code,
                    'detail': exc.detail,
                },
            )

        # Create session token.
        session_token = create_session_token(identity, session_config)

        # Build redirect response with session cookie.
        response = RedirectResponse(
            url=session_config.redirect_path,
            status_code=302,
        )

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            httponly=True,
            secure=session_config.cookie_secure,
            samesite='lax',
            max_age=session_config.session_ttl,
            path='/',
            domain=session_config.cookie_domain,
        )

        return response

    @router.get('/auth/session')
    async def get_session(request: Request):
        """Check current session status.

        Returns session info if a valid session cookie exists.
        Returns 401 if no session or invalid session.
        """
        session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_cookie:
            return JSONResponse(
                status_code=401,
                content={
                    'error': 'no_session',
                    'detail': 'No session cookie present',
                },
            )

        try:
            claims = verify_session_token(session_cookie, session_config)
        except jwt.ExpiredSignatureError:
            response = JSONResponse(
                status_code=401,
                content={
                    'error': 'session_expired',
                    'detail': 'Session has expired',
                },
            )
            response.delete_cookie(SESSION_COOKIE_NAME, path='/')
            return response
        except jwt.InvalidTokenError:
            response = JSONResponse(
                status_code=401,
                content={
                    'error': 'invalid_session',
                    'detail': 'Session cookie is invalid',
                },
            )
            response.delete_cookie(SESSION_COOKIE_NAME, path='/')
            return response

        result = {
            'user_id': claims['sub'],
            'email': claims.get('email', ''),
            'role': claims.get('role', 'authenticated'),
            'expires_at': claims['exp'],
        }

        # Rolling refresh: if session is close to expiry, issue new cookie.
        if should_refresh_session(claims, session_config):
            identity = AuthIdentity(
                user_id=claims['sub'],
                email=claims.get('email', ''),
                role=claims.get('role', 'authenticated'),
            )
            new_token = create_session_token(identity, session_config)
            response = JSONResponse(content=result)
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=new_token,
                httponly=True,
                secure=session_config.cookie_secure,
                samesite='lax',
                max_age=session_config.session_ttl,
                path='/',
                domain=session_config.cookie_domain,
            )
            return response

        return result

    @router.post('/auth/logout')
    async def logout(request: Request):
        """Clear the session cookie."""
        response = JSONResponse(
            content={'status': 'logged_out'},
        )
        response.delete_cookie(SESSION_COOKIE_NAME, path='/')
        return response

    return router
