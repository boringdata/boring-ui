"""Authenticated share links with exact-path scope (Epic F)."""

from .model import (
    ShareLink,
    ShareLinkRepository,
    InMemoryShareLinkRepository,
    ShareLinkNotFound,
    ShareLinkExpired,
    ShareLinkRevoked,
    hash_token,
    generate_share_token,
)
from .routes import (
    CreateShareRequest,
    create_share_router,
    normalize_share_path,
)
from .access import (
    ShareWriteRequest,
    create_share_access_router,
)
from .audit import (
    InMemoryShareAuditEmitter,
    ShareAuditEmitter,
    ShareAuditEvent,
    emit_share_accessed,
    emit_share_created,
    emit_share_denied,
    emit_share_revoked,
    emit_share_write,
    redact_string,
    redact_token,
)

__all__ = [
    'CreateShareRequest',
    'InMemoryShareAuditEmitter',
    'InMemoryShareLinkRepository',
    'ShareAuditEmitter',
    'ShareAuditEvent',
    'ShareLink',
    'ShareLinkExpired',
    'ShareLinkNotFound',
    'ShareLinkRepository',
    'ShareLinkRevoked',
    'ShareWriteRequest',
    'create_share_access_router',
    'create_share_router',
    'emit_share_accessed',
    'emit_share_created',
    'emit_share_denied',
    'emit_share_revoked',
    'emit_share_write',
    'generate_share_token',
    'hash_token',
    'normalize_share_path',
    'redact_string',
    'redact_token',
]
