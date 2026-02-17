"""GET /api/v1/app-config route.

Bead: bd-223o.8.2 (I2)

Returns branding and release metadata for the resolved app identity.
The app_id is determined by the request hostname via the
``AppIdentityResolver`` (I1).

Response shape (design doc section 11, endpoint 9):
```json
{
    "app_id": "boring-ui",
    "name": "Boring UI",
    "logo": "/assets/boring-ui-logo.svg",
    "default_release_id": "2026-02-13.1"
}
```

Errors:
  - ``404 app_config_not_found``: No config registered for resolved app_id.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from control_plane.app.identity.resolver import AppIdentityResolver

router = APIRouter()


def create_app_config_router(resolver: AppIdentityResolver) -> APIRouter:
    """Create a router with the app-config endpoint bound to a resolver.

    Args:
        resolver: The configured ``AppIdentityResolver`` instance.

    Returns:
        A FastAPI ``APIRouter`` with the ``/api/v1/app-config`` route.
    """
    config_router = APIRouter()

    @config_router.get('/api/v1/app-config')
    async def get_app_config(request: Request):
        host = request.headers.get('host', '')

        try:
            resolution = resolver.resolve(host)
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'app_config_not_found',
                    'detail': 'No app identity could be resolved for this host.',
                },
            )

        config = resolution.config
        if config is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'app_config_not_found',
                    'detail': f'No config registered for app_id {resolution.app_id!r}.',
                },
            )

        return {
            'app_id': config.app_id,
            'name': config.name,
            'logo': config.logo,
            'default_release_id': config.default_release_id,
        }

    return config_router
