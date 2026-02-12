"""Opaque session tokens for exec attach flows.

Replaces raw provider identity exposure with signed opaque session_id
carrying bounded attach context and TTL.

Token format: base64url(json({header}).{payload}.{signature}))
Signature: HMAC-SHA256(secret, header_b64 + "." + payload_b64)

Tokens are:
  - Opaque to clients (base64url-encoded)
  - Bound to a specific exec session ID
  - Time-limited with configurable TTL
  - Renewable without disrupting active streams
  - Validated before exec attach
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_TTL = 3600  # 1 hour
DEFAULT_MAX_RENEWALS = 24  # Max renewals before requiring new session
TOKEN_VERSION = 1


class SessionTokenError(Exception):
    """Raised when session token validation fails."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f'Session token error: {reason}')


@dataclass(frozen=True)
class SessionTokenPayload:
    """Decoded and validated session token payload."""
    session_id: str
    template_id: str
    issued_at: float
    expires_at: float
    renewal_count: int
    version: int = TOKEN_VERSION

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        remaining = self.expires_at - time.time()
        return max(0.0, remaining)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def _sign(secret: str, message: str) -> str:
    return hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def issue_session_token(
    secret: str,
    session_id: str,
    template_id: str,
    *,
    ttl: int = DEFAULT_TOKEN_TTL,
    now: float | None = None,
) -> str:
    """Issue a new signed session token.

    Args:
        secret: HMAC signing secret (from SandboxConfig.session_token_secret)
        session_id: The exec session this token authorizes
        template_id: Template that created the session
        ttl: Token lifetime in seconds
        now: Override current time (for testing)

    Returns:
        Opaque base64url-encoded token string
    """
    current_time = now if now is not None else time.time()

    header = {'ver': TOKEN_VERSION, 'alg': 'HS256'}
    payload = {
        'sid': session_id,
        'tid': template_id,
        'iat': current_time,
        'exp': current_time + ttl,
        'rnw': 0,
    }

    header_b64 = _b64url_encode(json.dumps(header, sort_keys=True).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True).encode())
    message = f'{header_b64}.{payload_b64}'
    signature = _sign(secret, message)

    return f'{header_b64}.{payload_b64}.{signature}'


def validate_session_token(
    token: str,
    secret: str,
    *,
    now: float | None = None,
) -> SessionTokenPayload:
    """Validate and decode a session token.

    Args:
        token: The opaque token string
        secret: HMAC signing secret
        now: Override current time (for testing)

    Returns:
        SessionTokenPayload with decoded claims

    Raises:
        SessionTokenError: If token is invalid, expired, or tampered
    """
    parts = token.split('.')
    if len(parts) != 3:
        raise SessionTokenError('Malformed token: expected 3 parts')

    header_b64, payload_b64, signature = parts

    # Verify signature
    expected_sig = _sign(secret, f'{header_b64}.{payload_b64}')
    if not hmac.compare_digest(signature, expected_sig):
        raise SessionTokenError('Invalid token signature')

    # Decode header
    try:
        header = json.loads(_b64url_decode(header_b64))
    except Exception:
        raise SessionTokenError('Malformed token header')

    if header.get('ver') != TOKEN_VERSION:
        raise SessionTokenError(
            f'Unsupported token version: {header.get("ver")}'
        )

    # Decode payload
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise SessionTokenError('Malformed token payload')

    # Validate required fields
    required = ('sid', 'tid', 'iat', 'exp', 'rnw')
    for field in required:
        if field not in payload:
            raise SessionTokenError(f'Missing field: {field}')

    current_time = now if now is not None else time.time()
    if current_time > payload['exp']:
        raise SessionTokenError('Token expired')

    return SessionTokenPayload(
        session_id=payload['sid'],
        template_id=payload['tid'],
        issued_at=payload['iat'],
        expires_at=payload['exp'],
        renewal_count=payload['rnw'],
        version=header['ver'],
    )


def renew_session_token(
    token: str,
    secret: str,
    *,
    ttl: int = DEFAULT_TOKEN_TTL,
    max_renewals: int = DEFAULT_MAX_RENEWALS,
    now: float | None = None,
) -> str:
    """Renew a session token with a fresh TTL.

    Preserves the same session_id binding while updating issued_at/expires_at.
    Increments renewal_count to enforce bounded renewal policy.

    Args:
        token: Current valid token
        secret: HMAC signing secret
        ttl: New token lifetime in seconds
        max_renewals: Maximum allowed renewals
        now: Override current time (for testing)

    Returns:
        New opaque token string

    Raises:
        SessionTokenError: If token is invalid or max renewals exceeded
    """
    payload = validate_session_token(token, secret, now=now)

    if payload.renewal_count >= max_renewals:
        raise SessionTokenError(
            f'Maximum renewals ({max_renewals}) exceeded'
        )

    current_time = now if now is not None else time.time()

    header = {'ver': TOKEN_VERSION, 'alg': 'HS256'}
    new_payload = {
        'sid': payload.session_id,
        'tid': payload.template_id,
        'iat': current_time,
        'exp': current_time + ttl,
        'rnw': payload.renewal_count + 1,
    }

    header_b64 = _b64url_encode(json.dumps(header, sort_keys=True).encode())
    payload_b64 = _b64url_encode(json.dumps(new_payload, sort_keys=True).encode())
    message = f'{header_b64}.{payload_b64}'
    signature = _sign(secret, message)

    return f'{header_b64}.{payload_b64}.{signature}'
