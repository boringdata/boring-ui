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

__all__ = [
    'CreateShareRequest',
    'ShareLink',
    'ShareWriteRequest',
    'ShareLinkRepository',
    'InMemoryShareLinkRepository',
    'ShareLinkNotFound',
    'ShareLinkExpired',
    'ShareLinkRevoked',
    'create_share_access_router',
    'create_share_router',
    'hash_token',
    'generate_share_token',
    'normalize_share_path',
]
