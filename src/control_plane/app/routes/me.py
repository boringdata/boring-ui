"""GET /api/v1/me — Authenticated identity endpoint.

Bead: bd-223o.7.3 (B3)

Returns the authenticated user's identity (user_id, email) as specified
in design doc section 11 item 3 and acceptance criteria 18.1.2:

    ``GET /api/v1/me`` returns ``200`` with stable user identity fields
    (``user_id``, ``email``) for an authenticated session.

Response format:
    {
        "user_id": "uuid-string",
        "email": "user@example.com",
        "role": "authenticated"
    }
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity

router = APIRouter(tags=['auth'])


@router.get('/api/v1/me')
async def get_me(
    identity: AuthIdentity = Depends(get_auth_identity),
) -> dict:
    """Return the authenticated user's identity.

    Requires a valid authentication credential (Bearer token or session).
    Returns 401 if not authenticated (enforced by auth guard middleware
    and the ``get_auth_identity`` dependency).
    """
    return {
        'user_id': identity.user_id,
        'email': identity.email,
        'role': identity.role,
    }
