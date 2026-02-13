"""Modal deployment entrypoint for the Feature 3 control plane.

Bead: bd-1joj.2 (CP1)

Canonical deploy:
  modal deploy src/control_plane/modal/modal_app.py
"""

from __future__ import annotations

import os

import modal


APP_NAME = "boring-ui-control-plane"
ARTIFACTS_VOLUME_NAME = "boring-ui-artifacts"
ARTIFACTS_MOUNT_PATH = "/mnt/artifacts"
CONTROL_PLANE_SECRET_NAME = "boring-ui-control-plane"

# Deployment sizing (plan defaults).
MIN_CONTAINERS = 0
MAX_CONTAINERS = 10
TIMEOUT_SECONDS = 600

# Env vars expected inside the Modal container via Modal Secret.
REQUIRED_ENV_VARS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "SESSION_SECRET",
    "SPRITE_BEARER_TOKEN",
)


def derive_jwks_url(supabase_url: str) -> str:
    """Derive Supabase JWKS URL from SUPABASE_URL per plan (no separate secret)."""
    base = supabase_url.rstrip("/")
    return f"{base}/auth/v1/certs"


def _build_control_plane_app():
    """Build the FastAPI app for Modal ASGI serving.

    Import inside function so `modal deploy` can analyze the module without
    importing app code at build time.
    """
    from control_plane.app.main import create_app
    from control_plane.app.settings import ControlPlaneSettings
    from control_plane.app.inmemory import InMemorySandboxProvider, InMemorySessionRepository
    from control_plane.app.db.supabase_client import SupabaseClient
    from control_plane.app.db.workspace_repo import SupabaseWorkspaceRepository
    from control_plane.app.db.member_repo import SupabaseMemberRepository
    from control_plane.app.db.share_repo import SupabaseShareLinkRepository
    from control_plane.app.db.audit_emitter import SupabaseAuditEmitter
    from control_plane.app.db.provisioning_repo import SupabaseProvisioningJobRepository
    from control_plane.app.db.runtime_store import SupabaseRuntimeMetadataStore

    settings = ControlPlaneSettings.from_env()

    # Make JWKS URL available for downstream auth verification (AUTH0).
    if settings.supabase_url:
        os.environ.setdefault("SUPABASE_JWKS_URL", derive_jwks_url(settings.supabase_url))

    client = SupabaseClient(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )

    # Note: Some components are still in-memory (session + sandbox provider)
    # until SESS0 / SPR0 land. DB7 will eventually forbid InMemory in non-local.
    return create_app(
        settings,
        workspace_repo=SupabaseWorkspaceRepository(client),
        member_repo=SupabaseMemberRepository(client),
        session_repo=InMemorySessionRepository(),
        share_repo=SupabaseShareLinkRepository(client),
        audit_emitter=SupabaseAuditEmitter(client),
        job_repo=SupabaseProvisioningJobRepository(client),
        runtime_store=SupabaseRuntimeMetadataStore(client),
        sandbox_provider=InMemorySandboxProvider(),
    )


IMAGE_PIP_DEPS: tuple[str, ...] = (
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "httpx>=0.24.0",
    "PyJWT>=2.8.0",
    "modal>=1.0.0",
)

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(*IMAGE_PIP_DEPS)
)

_artifacts_volume = modal.Volume.from_name(
    ARTIFACTS_VOLUME_NAME, create_if_missing=True
)

_secrets = [modal.Secret.from_name(CONTROL_PLANE_SECRET_NAME)]

app = modal.App(APP_NAME)


@app.function(
    image=_image,
    secrets=_secrets,
    volumes={ARTIFACTS_MOUNT_PATH: _artifacts_volume},
    min_containers=MIN_CONTAINERS,
    max_containers=MAX_CONTAINERS,
    timeout=TIMEOUT_SECONDS,
)
@modal.asgi_app()
def fastapi_app():
    return _build_control_plane_app()
