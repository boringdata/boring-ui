"""Modal deployment entrypoint for control plane.

Deploy with: ``modal deploy modal_app.py``
Run locally: ``modal serve modal_app.py``
"""

from __future__ import annotations

import modal

# --- Modal App Configuration ---

app = modal.App(
    name="boring-ui",
    secrets=[
        modal.Secret.from_name("anthropic-key", required_keys=["ANTHROPIC_API_KEY"]),
        modal.Secret.from_name("sprite-bearer", required_keys=["SPRITE_BEARER_TOKEN"]),
        modal.Secret.from_name("supabase-creds", required_keys=[
            "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        ]),
        # Optional HS256 local-dev fallback; RS256 JWKS mode only needs SUPABASE_URL.
        modal.Secret.from_name("jwt-secret"),
        modal.Secret.from_name("session-config", required_keys=["SESSION_SECRET"]),
    ],
)

# --- Container Image ---

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.23.0",
        "ptyprocess>=0.7.0",
        "websockets>=11.0",
        "aiofiles>=23.0.0",
        "PyJWT[crypto]>=2.8.0",
        "structlog>=24.1.0",
        "prometheus-client>=0.20.0",
        "httpx>=0.24.0",
    )
    .env({"PYTHONPATH": "/app/src"})
    # Keep local code mount last (Modal requirement) to avoid rebuild loops.
    .add_local_dir("src/control_plane", "/app/src/control_plane")
)


def _build_control_plane_app():
    """Build control-plane app for auth/workspace APIs."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from control_plane.app.agent.sessions import (
        InMemoryAgentSessionRepository,
        create_agent_session_router,
    )
    from control_plane.app.config.environment import load_environment_config
    from control_plane.app.identity.loader import IdentityConfigError, load_identity_config
    from control_plane.app.identity.resolver import AppConfig, AppIdentityResolver
    from control_plane.app.provisioning.job_service import (
        InMemoryProvisioningJobRepository,
        ProvisioningService,
    )
    from control_plane.app.routes.app_config import create_app_config_router
    from control_plane.app.routes.auth import SessionConfig, create_auth_router
    from control_plane.app.routes.me import router as me_router
    from control_plane.app.routes.members import (
        InMemoryMemberRepository,
        create_member_router,
    )
    from control_plane.app.routes.provisioning import (
        InMemoryProvisioningEventRepository,
        create_provisioning_router,
    )
    from control_plane.app.routes.session import (
        InMemorySessionRepository,
        create_session_router,
    )
    from control_plane.app.routes.workspaces import (
        InMemoryWorkspaceRepository,
        create_workspace_router,
    )
    from control_plane.app.routing.dispatcher import RouteDispatchMiddleware
    from control_plane.app.security.auth_guard import AuthGuardMiddleware
    from control_plane.app.security.secrets import load_control_plane_secrets
    from control_plane.app.security.token_verify import create_token_verifier
    from control_plane.app.sharing.access import create_share_access_router
    from control_plane.app.sharing.model import InMemoryShareLinkRepository
    from control_plane.app.sharing.routes import create_share_router

    class _MemberRepoMembershipChecker:
        def __init__(self, member_repo: InMemoryMemberRepository) -> None:
            self._member_repo = member_repo

        async def is_active_member(self, workspace_id: str, user_id: str) -> bool:
            return await self._member_repo.is_member(workspace_id, user_id)

    env_cfg = load_environment_config()
    secrets = load_control_plane_secrets(require_sprite_bearer=False)
    token_verifier = create_token_verifier(
        supabase_url=secrets.supabase_url or None,
        jwt_secret=secrets.supabase_jwt_secret or None,
    )

    session_cfg = SessionConfig(
        session_secret=secrets.session_secret,
        cookie_secure=env_cfg.cookie_secure,
    )

    ws_repo = InMemoryWorkspaceRepository()
    member_repo = InMemoryMemberRepository()
    session_repo = InMemorySessionRepository()
    job_repo = InMemoryProvisioningJobRepository()
    event_repo = InMemoryProvisioningEventRepository()
    provisioning_service = ProvisioningService(job_repo)
    share_repo = InMemoryShareLinkRepository()
    agent_session_repo = InMemoryAgentSessionRepository()
    membership = _MemberRepoMembershipChecker(member_repo)

    try:
        identity_resolver = load_identity_config()
    except IdentityConfigError:
        identity_resolver = AppIdentityResolver(
            host_map={"*": "boring-ui"},
            app_configs={
                "boring-ui": AppConfig(
                    app_id="boring-ui",
                    name="Boring UI",
                    logo="",
                    default_release_id="",
                )
            },
            default_app_id="boring-ui",
        )

    app = FastAPI(
        title="Boring UI Control Plane API",
        version="0.1.0",
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "plane": "control"}

    app.include_router(create_auth_router(token_verifier, session_cfg))
    app.include_router(me_router)
    app.include_router(create_app_config_router(identity_resolver))
    app.include_router(create_workspace_router(ws_repo, member_repo=member_repo))
    app.include_router(create_member_router(member_repo, workspace_exists_fn=ws_repo.get))
    app.include_router(create_session_router(session_repo))
    app.include_router(
        create_provisioning_router(
            job_repo=job_repo,
            provisioning_service=provisioning_service,
            event_repo=event_repo,
        )
    )
    app.include_router(create_share_router(share_repo, membership))
    app.include_router(create_share_access_router(share_repo))
    app.include_router(create_agent_session_router(agent_session_repo, membership))

    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=token_verifier,
        session_secret=secrets.session_secret,
    )
    app.add_middleware(RouteDispatchMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(env_cfg.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

# --- FastAPI ASGI App ---


@app.function(
    image=image,
    cpu=2.0,
    memory=1024,
    timeout=600,
    min_containers=0,  # Scale to zero when idle
    max_containers=10,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def control_plane_web_app():
    """Modal ASGI entry point for control-plane APIs."""
    return _build_control_plane_app()


# --- CLI Commands ---

@app.local_entrypoint()
def main():
    """Local entrypoint for testing and development."""
    print("Boring UI - Modal Deployment")
    print("=" * 50)
    print()
    print("Commands:")
    print("  modal deploy modal_app.py      - Deploy control-plane endpoint")
    print("  modal serve modal_app.py       - Run locally with hot reload")
    print()
    print("ASGI Endpoints:")
    print("  - control_plane_web_app: auth/workspace/member/session/control-plane APIs")
    print()
    print("Environment:")
    print("  - Python path: /app/src")
    print()
