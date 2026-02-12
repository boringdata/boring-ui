"""Deprecation signaling middleware (bd-1pwb.6.2).

Adds RFC 8594 Deprecation and Sunset headers to legacy API routes,
guiding clients to canonical /api/v1 endpoints.

Headers added:
- Deprecation: true
- Sunset: <ISO 8601 date> (configurable sunset date)
- Link: <canonical URL>; rel="successor-version"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Map legacy route prefixes → canonical v1 equivalents
LEGACY_ROUTE_MAP: dict[str, str] = {
    "/api/tree": "/api/v1/files/list",
    "/api/file": "/api/v1/files/read",
    "/api/search": "/api/v1/files/search",
    "/api/git/status": "/api/v1/git/status",
    "/api/git/diff": "/api/v1/git/diff",
    "/api/git/show": "/api/v1/git/show",
}

# Default sunset: 6 months from deployment
DEFAULT_SUNSET = "2026-08-01T00:00:00Z"


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware that adds deprecation headers to legacy routes."""

    def __init__(
        self,
        app,
        legacy_routes: dict[str, str] | None = None,
        sunset_date: str = DEFAULT_SUNSET,
    ):
        super().__init__(app)
        self._routes = legacy_routes or LEGACY_ROUTE_MAP
        self._sunset = sunset_date

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path

        for legacy_path, canonical_path in self._routes.items():
            if path == legacy_path or path.startswith(legacy_path + "/"):
                response.headers["Deprecation"] = "true"
                response.headers["Sunset"] = self._sunset
                response.headers["Link"] = f'<{canonical_path}>; rel="successor-version"'
                break

        return response


def add_deprecation_middleware(
    app: FastAPI,
    legacy_routes: dict[str, str] | None = None,
    sunset_date: str = DEFAULT_SUNSET,
) -> None:
    """Add deprecation signaling middleware to a FastAPI app."""
    app.add_middleware(
        DeprecationMiddleware,
        legacy_routes=legacy_routes,
        sunset_date=sunset_date,
    )
