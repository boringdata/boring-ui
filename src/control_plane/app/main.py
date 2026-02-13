"""Control plane FastAPI application factory.

Bead: bd-1joj.1 (CP0)

The create_app() factory is the single entry point for building the control-plane
ASGI application. It wires middleware (auth guard, request-ID, CORS), route dispatch,
and injects repository/provider implementations via dependency injection.

Usage:
    # Local development
    from control_plane.app import create_app, ControlPlaneSettings
    app = create_app(ControlPlaneSettings())

    # Non-local (Supabase repos injected)
    settings = ControlPlaneSettings.from_env()
    app = create_app(settings)

    # Testing (full DI control)
    app = create_app(settings, workspace_repo=mock_repo, ...)
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import ControlPlaneSettings
from .protocols import (
    AuditEmitter,
    JobRepository,
    MemberRepository,
    RuntimeMetadataStore,
    SandboxProvider,
    SessionRepository,
    ShareRepository,
    WorkspaceRepository,
)

logger = logging.getLogger(__name__)

# Auth-exempt paths: these never require a session/JWT.
# Exact matches and prefix matches (with path-boundary check) are supported.
AUTH_ALLOWLIST_EXACT: frozenset[str] = frozenset({
    "/health",
    "/api/v1/app-config",
})
AUTH_ALLOWLIST_PREFIX: tuple[str, ...] = (
    "/auth/",
)


@dataclass(frozen=True)
class AppDependencies:
    """Container for all injected repository/provider instances.

    Stored on ``app.state.deps`` so route handlers can access them.
    """

    workspace_repo: WorkspaceRepository
    member_repo: MemberRepository
    session_repo: SessionRepository
    share_repo: ShareRepository
    audit_emitter: AuditEmitter
    job_repo: JobRepository
    runtime_store: RuntimeMetadataStore
    sandbox_provider: SandboxProvider


def _build_inmemory_deps() -> AppDependencies:
    """Construct all-InMemory dependencies for local development."""
    from .inmemory import (
        InMemoryAuditEmitter,
        InMemoryJobRepository,
        InMemoryMemberRepository,
        InMemoryRuntimeMetadataStore,
        InMemorySandboxProvider,
        InMemorySessionRepository,
        InMemoryShareRepository,
        InMemoryWorkspaceRepository,
    )

    return AppDependencies(
        workspace_repo=InMemoryWorkspaceRepository(),
        member_repo=InMemoryMemberRepository(),
        session_repo=InMemorySessionRepository(),
        share_repo=InMemoryShareRepository(),
        audit_emitter=InMemoryAuditEmitter(),
        job_repo=InMemoryJobRepository(),
        runtime_store=InMemoryRuntimeMetadataStore(),
        sandbox_provider=InMemorySandboxProvider(),
    )


# ── Middleware ──────────────────────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID on every request."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to protected routes.

    Requests to paths in AUTH_ALLOWLIST are passed through.
    OPTIONS (CORS preflight) is always allowed.
    All other requests must carry a Supabase session cookie or
    Authorization Bearer token.  The actual token validation is
    delegated to downstream auth routes / Supabase client; this
    middleware only enforces that *some* credential is present.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Always allow preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check allowlist (exact match or prefix with path-boundary)
        path = request.url.path
        if path in AUTH_ALLOWLIST_EXACT:
            return await call_next(request)
        for prefix in AUTH_ALLOWLIST_PREFIX:
            if path.startswith(prefix):
                return await call_next(request)

        # Check for auth credential (cookie or bearer)
        has_cookie = bool(request.cookies.get("sb-access-token"))
        auth_header = request.headers.get("authorization", "")
        has_bearer = auth_header.lower().startswith("bearer ")

        if not has_cookie and not has_bearer:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.debug("[%s] Auth guard: no credential for %s", request_id, path)
            return JSONResponse(
                status_code=401,
                content={
                    "code": "AUTH_REQUIRED",
                    "message": "Authentication required",
                    "request_id": request_id,
                },
                headers={"WWW-Authenticate": 'Bearer realm="boring-ui-cp"'},
            )

        return await call_next(request)


# ── Route stubs ─────────────────────────────────────────────────────
# Minimal route stubs registered by the factory. Real implementations
# come from dedicated route modules (auth.py, workspaces.py, etc.)
# which are wired in downstream beads.


def _register_stub_routes(app: FastAPI, settings: ControlPlaneSettings) -> None:
    """Register placeholder routes for the section 5.3 routing contract.

    These return 501 until the real route modules are wired.  The route
    *paths* are registered now so that route-inventory tests pass.
    """
    from fastapi import APIRouter

    # Auth routes (allowlisted — no auth guard)
    auth_router = APIRouter(prefix="/auth", tags=["auth"])

    @auth_router.post("/login")
    async def auth_login():
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "AUTH0 pending"},
        )

    @auth_router.get("/callback")
    async def auth_callback():
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "AUTH0 pending"},
        )

    app.include_router(auth_router)

    # Control plane API routes
    api_router = APIRouter(prefix="/api/v1", tags=["control-plane"])

    @api_router.get("/app-config")
    async def app_config():
        return {
            "app_id": "boring-ui",
            "branding": {"name": "Boring UI"},
            "environment": settings.environment,
        }

    @api_router.get("/me")
    async def me(request: Request):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on AUTH0"},
        )

    @api_router.get("/workspaces")
    async def list_workspaces(request: Request):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB1"},
        )

    @api_router.post("/workspaces")
    async def create_workspace(request: Request):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB1"},
        )

    @api_router.get("/workspaces/{workspace_id}")
    async def get_workspace(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB1"},
        )

    @api_router.patch("/workspaces/{workspace_id}")
    async def update_workspace(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB1"},
        )

    @api_router.post("/workspaces/{workspace_id}/members")
    async def add_member(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB2"},
        )

    @api_router.get("/workspaces/{workspace_id}/members")
    async def list_members(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB2"},
        )

    @api_router.delete("/workspaces/{workspace_id}/members/{member_id}")
    async def remove_member(workspace_id: str, member_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB2"},
        )

    @api_router.get("/workspaces/{workspace_id}/runtime")
    async def get_runtime(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB6"},
        )

    @api_router.post("/workspaces/{workspace_id}/retry")
    async def retry_provisioning(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on PROV0"},
        )

    @api_router.post("/workspaces/{workspace_id}/shares")
    async def create_share(workspace_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB4"},
        )

    @api_router.delete("/workspaces/{workspace_id}/shares/{share_id}")
    async def delete_share(workspace_id: str, share_id: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB4"},
        )

    @api_router.get("/shares/{token}")
    async def get_share(token: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB4"},
        )

    @api_router.put("/shares/{token}")
    async def update_share(token: str):
        return JSONResponse(
            status_code=501,
            content={"code": "NOT_IMPLEMENTED", "message": "Depends on DB4"},
        )

    app.include_router(api_router)


# ── Factory ─────────────────────────────────────────────────────────


def create_app(
    settings: ControlPlaneSettings | None = None,
    *,
    workspace_repo: WorkspaceRepository | None = None,
    member_repo: MemberRepository | None = None,
    session_repo: SessionRepository | None = None,
    share_repo: ShareRepository | None = None,
    audit_emitter: AuditEmitter | None = None,
    job_repo: JobRepository | None = None,
    runtime_store: RuntimeMetadataStore | None = None,
    sandbox_provider: SandboxProvider | None = None,
) -> FastAPI:
    """Create a configured control-plane FastAPI application.

    Args:
        settings: Application settings. Defaults to local-dev settings.
        workspace_repo..sandbox_provider: Repository/provider overrides.
            When None, local mode uses InMemory implementations.
            Non-local mode raises if Supabase repos are not provided
            (Supabase wiring is done in DB0+ beads).

    Returns:
        Configured FastAPI application ready for uvicorn.run().

    Raises:
        ValueError: If settings validation fails (non-local without required config).
        ValueError: If non-local environment has no Supabase repos provided.
    """
    if settings is None:
        settings = ControlPlaneSettings()

    # Validate settings
    errors = settings.validate()
    if errors:
        raise ValueError(
            "Control plane settings validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Build or validate dependencies
    if settings.is_local:
        # Local mode: fill any missing repos with InMemory
        defaults = _build_inmemory_deps()
        deps = AppDependencies(
            workspace_repo=workspace_repo or defaults.workspace_repo,
            member_repo=member_repo or defaults.member_repo,
            session_repo=session_repo or defaults.session_repo,
            share_repo=share_repo or defaults.share_repo,
            audit_emitter=audit_emitter or defaults.audit_emitter,
            job_repo=job_repo or defaults.job_repo,
            runtime_store=runtime_store or defaults.runtime_store,
            sandbox_provider=sandbox_provider or defaults.sandbox_provider,
        )
    else:
        # Non-local: all repos must be explicitly provided (Supabase)
        missing = []
        if workspace_repo is None:
            missing.append("workspace_repo")
        if member_repo is None:
            missing.append("member_repo")
        if session_repo is None:
            missing.append("session_repo")
        if share_repo is None:
            missing.append("share_repo")
        if audit_emitter is None:
            missing.append("audit_emitter")
        if job_repo is None:
            missing.append("job_repo")
        if runtime_store is None:
            missing.append("runtime_store")
        if sandbox_provider is None:
            missing.append("sandbox_provider")

        if missing:
            raise ValueError(
                f"Non-local environment ({settings.environment}) requires all "
                f"repositories to be explicitly provided. Missing: {', '.join(missing)}"
            )

        deps = AppDependencies(
            workspace_repo=workspace_repo,  # type: ignore[arg-type]
            member_repo=member_repo,  # type: ignore[arg-type]
            session_repo=session_repo,  # type: ignore[arg-type]
            share_repo=share_repo,  # type: ignore[arg-type]
            audit_emitter=audit_emitter,  # type: ignore[arg-type]
            job_repo=job_repo,  # type: ignore[arg-type]
            runtime_store=runtime_store,  # type: ignore[arg-type]
            sandbox_provider=sandbox_provider,  # type: ignore[arg-type]
        )

    # Lifespan
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Control plane startup (environment=%s)", settings.environment)
        yield
        logger.info("Control plane shutdown")

    # Build app
    app = FastAPI(
        title="Boring UI Control Plane",
        description="Control plane API for workspace management and provisioning",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store deps and settings on app state
    app.state.deps = deps
    app.state.settings = settings

    # ── Middleware stack (applied in reverse order) ──────────────
    # Order of execution: RequestID -> AuthGuard -> CORS -> route handler

    # CORS (outermost after middleware chain)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth guard (after request-ID so we can include it in 401 responses)
    app.add_middleware(AuthGuardMiddleware)

    # Request-ID generation/propagation (innermost = runs first)
    app.add_middleware(RequestIDMiddleware)

    # ── Routes ──────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "environment": settings.environment,
        }

    # Register section 5.3 route contract stubs
    _register_stub_routes(app, settings)

    # Real route modules (replace stubs as beads are completed)
    from .routes.session import create_session_router
    app.include_router(create_session_router())

    return app


# For uvicorn, use --factory flag:
#   uvicorn control_plane.app.main:create_app --factory
# This avoids executing create_app() at import time.
