"""Auth transport parity: Bearer token and session cookie.

Bead: bd-223o.7.4 (B4)

Ensures CLI/internal callers (Bearer token) and browser callers (session
cookie) receive identical treatment on all control-plane endpoints.

Design doc section 13.1:
  - Browser: session cookie.
  - CLI/internal: ``Authorization: Bearer <supabase_access_token>``.
  - Transport precedence: Bearer > session cookie.

This module provides:
  1. ``extract_credentials`` — unified credential extraction from request.
  2. ``AuthTransport`` enum tracking which transport was used.
  3. Tests can verify both transports produce identical ``AuthIdentity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import jwt as pyjwt
from starlette.requests import Request

from .token_verify import AuthIdentity, TokenVerificationError


class AuthTransport(Enum):
    """Which auth transport provided the credentials."""

    BEARER = 'bearer'
    SESSION_COOKIE = 'session_cookie'
    NONE = 'none'


@dataclass(frozen=True, slots=True)
class ExtractedCredentials:
    """Credentials extracted from a request."""

    token: str | None
    transport: AuthTransport


def extract_credentials(
    request: Request,
    session_cookie_name: str = 'boring_session',
) -> ExtractedCredentials:
    """Extract auth credentials from a request.

    Precedence: Bearer token > session cookie.

    Args:
        request: The incoming HTTP request.
        session_cookie_name: Name of the session cookie.

    Returns:
        Extracted credentials with transport type.
    """
    # 1. Bearer token (preferred for CLI/internal callers).
    auth_header = request.headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        if token:
            return ExtractedCredentials(
                token=token,
                transport=AuthTransport.BEARER,
            )

    # 2. Session cookie (browser callers).
    cookie = request.cookies.get(session_cookie_name)
    if cookie:
        return ExtractedCredentials(
            token=cookie,
            transport=AuthTransport.SESSION_COOKIE,
        )

    # 3. No credentials.
    return ExtractedCredentials(
        token=None,
        transport=AuthTransport.NONE,
    )


def identity_from_session_token(
    token: str,
    session_secret: str,
) -> AuthIdentity:
    """Verify a session JWT and extract AuthIdentity.

    This produces the same ``AuthIdentity`` shape as Bearer token
    verification, ensuring downstream code treats both transports
    identically.

    Args:
        token: The session JWT from the cookie.
        session_secret: The HS256 signing secret.

    Returns:
        AuthIdentity matching the same shape as Bearer verification.

    Raises:
        TokenVerificationError: If the session token is invalid.
    """
    try:
        claims = pyjwt.decode(
            token,
            session_secret,
            algorithms=['HS256'],
            options={
                'require': ['sub', 'exp', 'type'],
                'verify_exp': True,
            },
        )
    except pyjwt.ExpiredSignatureError:
        raise TokenVerificationError('session_expired')
    except pyjwt.InvalidTokenError as exc:
        raise TokenVerificationError('invalid_session', str(exc))

    if claims.get('type') != 'session':
        raise TokenVerificationError(
            'invalid_token_type',
            f'Expected type=session, got {claims.get("type")!r}',
        )

    return AuthIdentity(
        user_id=claims['sub'],
        email=claims.get('email', ''),
        role=claims.get('role', 'authenticated'),
        raw_claims=claims,
    )
