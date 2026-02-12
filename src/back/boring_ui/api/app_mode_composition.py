"""Mode-specific app composition helpers for create_app()."""

from __future__ import annotations

import os
import time as _time
from logging import Logger

from fastapi import FastAPI, Request

from .auth import OIDCVerifier
from .auth_middleware import AuthContext, add_oidc_auth_middleware
from .capability_tokens import CapabilityTokenIssuer
from .config import APIConfig, is_dev_auth_bypass_enabled, is_local_parity_mode
from .local_api import create_local_api_router
from .sandbox_auth import CapabilityAuthContext
from .auth import ServiceTokenSigner
from .target_resolver import StaticTargetResolver
from .transport import HTTPInternalTransport, SpritesProxyTransport
from .v1_hosted_backend import HostedExecBackend, HostedFilesBackend, HostedGitBackend
from .v1_local_backend import LocalFilesBackend, LocalGitBackend
from .v1_router import create_v1_router
from .modules.sandbox.hosted_client import HostedSandboxClient, SandboxClientConfig


def get_routers_for_mode(
    run_mode: str,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = False,
    include_companion: bool = False,
) -> set[str]:
    """Determine routers mounted for each run mode."""
    enabled = {"files", "git"}

    if run_mode == "local":
        if include_pty:
            enabled.add("pty")
        if include_stream:
            enabled.add("chat_claude_code")
        if include_approval:
            enabled.add("approval")
        if include_sandbox:
            enabled.add("sandbox")
        if include_companion:
            enabled.add("companion")
        return enabled

    if run_mode == "hosted":
        enabled = {"approval"}
        if is_dev_auth_bypass_enabled():
            enabled.update({"pty", "chat_claude_code"})
        return enabled

    raise ValueError(f"Unknown run mode: {run_mode}")


def resolve_enabled_routers(
    run_mode: str,
    logger: Logger,
    routers: list[str] | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = False,
    include_companion: bool = False,
) -> set[str]:
    """Resolve router set from explicit list or mode defaults."""
    if routers is not None:
        enabled_routers = set(routers)
        if run_mode == "hosted":
            privileged = {"files", "git", "pty", "chat_claude_code", "sandbox", "companion"}
            requested_privileged = privileged & enabled_routers
            if requested_privileged:
                raise ValueError(
                    "SECURITY: Hosted mode cannot mount privileged routers. "
                    f"Requested: {', '.join(sorted(requested_privileged))}. "
                    "These operations must be routed through Hosted Auth and Sandbox APIs (phases 2-5)."
                )
        return enabled_routers

    enabled_routers = get_routers_for_mode(
        run_mode,
        include_pty=include_pty,
        include_stream=include_stream,
        include_approval=include_approval,
        include_sandbox=include_sandbox,
        include_companion=include_companion,
    )
    if run_mode == "hosted":
        local_routers = get_routers_for_mode(
            "local",
            include_pty=include_pty,
            include_stream=include_stream,
            include_approval=include_approval,
            include_sandbox=include_sandbox,
            include_companion=include_companion,
        )
        deferred = local_routers - enabled_routers
        if deferred:
            logger.info(
                "HOSTED mode defers privileged routers to later phases: %s. Control plane uses only: %s.",
                ", ".join(sorted(deferred)),
                ", ".join(sorted(enabled_routers or ["capabilities"])),
            )
    return enabled_routers


def configure_mode_auth(app: FastAPI, config: APIConfig, logger: Logger) -> None:
    """Attach auth middleware appropriate for run mode."""
    if config.run_mode.value == "local":

        @app.middleware("http")
        async def local_capability_context(request: Request, call_next):
            if request.url.path.startswith("/internal/v1"):
                now = int(_time.time())
                request.state.capability_context = CapabilityAuthContext(
                    workspace_id="local",
                    operations={"*"},
                    jti="local-bypass",
                    issued_at=now,
                    expires_at=now + 3600,
                )
            return await call_next(request)

        logger.debug("LOCAL mode: full-access capability context injected for /internal/v1")
        return

    if config.run_mode.value != "hosted":
        return

    if is_dev_auth_bypass_enabled():
        logger.warning(
            "DEV_AUTH_BYPASS is enabled. Hosted auth is bypassed for local development only."
        )

        @app.middleware("http")
        async def dev_auth_bypass(request, call_next):
            if request.url.path != "/health" and request.method != "OPTIONS":
                request.state.auth_context = AuthContext(
                    user_id="dev-local-user",
                    workspace_id="default",
                    permissions={
                        "*",
                        "files:read",
                        "files:write",
                        "git:read",
                        "exec:run",
                    },
                    claims={"dev_bypass": True},
                )
            return await call_next(request)

        return

    oidc_verifier = OIDCVerifier.from_env()
    add_oidc_auth_middleware(app, oidc_verifier)


def mount_mode_v1_routes(
    app: FastAPI,
    config: APIConfig,
    storage,
    enabled_features: dict[str, bool],
    logger: Logger,
) -> None:
    """Mount canonical /api/v1 route family based on run mode."""
    if config.run_mode.value == "local":
        _mount_local_v1_routes(app, config, storage, logger)
        return

    if config.run_mode.value == "hosted":
        _mount_hosted_v1_routes(app, config, enabled_features, logger)


def mount_local_private_api_if_needed(app: FastAPI, config: APIConfig, logger: Logger) -> None:
    """Mount or configure local_api private plane for LOCAL mode."""
    if config.run_mode.value != "local":
        return

    if is_local_parity_mode():
        parity_port = int(os.environ.get("LOCAL_PARITY_PORT", "2469"))
        parity_url = f"http://127.0.0.1:{parity_port}"
        logger.info(
            "LOCAL PARITY MODE: routing /internal/v1 through HTTP transport at %s. "
            "Start local-api server separately: LOCAL_API_PORT=%d python -m boring_ui.api.local_api",
            parity_url,
            parity_port,
        )
        app.state.local_parity_url = parity_url
        return

    local_api_router = create_local_api_router(config.workspace_root)
    app.include_router(local_api_router)
    logger.debug("LOCAL mode: local_api router mounted at /internal/v1")


def _mount_local_v1_routes(app: FastAPI, config: APIConfig, storage, logger: Logger) -> None:
    if is_local_parity_mode():
        parity_port = int(os.environ.get("LOCAL_PARITY_PORT", "2469"))
        parity_url = f"http://127.0.0.1:{parity_port}"

        parity_private_key = os.environ.get("CAPABILITY_PRIVATE_KEY", "")
        if parity_private_key:
            parity_private_key = parity_private_key.replace("\\n", "\n")
            parity_capability_issuer = CapabilityTokenIssuer(parity_private_key)
        else:
            from cryptography.hazmat.primitives import serialization as _ser
            from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

            parity_key = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
            parity_priv = parity_key.private_bytes(
                _ser.Encoding.PEM, _ser.PrivateFormat.PKCS8, _ser.NoEncryption()
            ).decode()
            parity_capability_issuer = CapabilityTokenIssuer(parity_priv)
            logger.warning(
                "LOCAL PARITY: CAPABILITY_PRIVATE_KEY not set; using ephemeral key. "
                "Set CAPABILITY_PRIVATE_KEY for stable parity keying."
            )

        parity_transport = HTTPInternalTransport(base_url=parity_url)
        parity_client_config = SandboxClientConfig(
            internal_url=parity_url,
            transport=parity_transport,
        )
        parity_hosted_client = HostedSandboxClient(config=parity_client_config)

        v1_router = create_v1_router(
            files_backend=HostedFilesBackend(parity_hosted_client, parity_capability_issuer),
            git_backend=HostedGitBackend(parity_hosted_client, parity_capability_issuer),
            exec_backend=HostedExecBackend(parity_hosted_client, parity_capability_issuer),
        )
        app.include_router(v1_router, prefix="/api/v1")
        logger.info(
            "LOCAL PARITY: /api/v1 routed through HTTP transport at %s (exercises hosted code path)",
            parity_url,
        )
        return

    from .modules.files.service import FileService
    from .modules.git.service import GitService

    file_service = FileService(config, storage)
    git_service = GitService(config)
    v1_router = create_v1_router(
        files_backend=LocalFilesBackend(file_service),
        git_backend=LocalGitBackend(git_service),
    )
    app.include_router(v1_router, prefix="/api/v1")


def _mount_hosted_v1_routes(
    app: FastAPI, config: APIConfig, enabled_features: dict[str, bool], logger: Logger
) -> None:
    capability_private_key = os.environ.get("CAPABILITY_PRIVATE_KEY", "")
    if not capability_private_key:
        logger.warning(
            "Hosted mode running without CAPABILITY_PRIVATE_KEY; sandbox proxy routes are disabled."
        )
        return

    capability_private_key = capability_private_key.replace("\\n", "\n")
    capability_issuer = CapabilityTokenIssuer(capability_private_key)

    service_signer = None
    service_private_key = os.environ.get("SERVICE_PRIVATE_KEY", "")
    if service_private_key:
        service_private_key = service_private_key.replace("\\n", "\n")
        service_signer = ServiceTokenSigner(
            private_key_pem=service_private_key,
            service_name="hosted-api",
        )

    target_resolver = StaticTargetResolver(provider=config.sandbox_provider.value)
    if config.sandbox_provider.value == "sprites":
        sprites_token = os.environ.get("SPRITES_TOKEN", "")
        transport = SpritesProxyTransport(
            sprites_token=sprites_token,
            sprite_name=target_resolver.sprite_name,
            local_api_port=target_resolver.local_api_port,
        )
        transport_target = f"sprites:{target_resolver.sprite_name}:{target_resolver.local_api_port}"
    else:
        transport = HTTPInternalTransport(base_url=target_resolver.internal_base_url)
        transport_target = target_resolver.internal_base_url

    client_config = SandboxClientConfig(
        internal_url=transport_target,
        service_signer=service_signer,
        transport=transport,
    )
    hosted_client = HostedSandboxClient(config=client_config)
    hosted_v1_router = create_v1_router(
        files_backend=HostedFilesBackend(hosted_client, capability_issuer),
        git_backend=HostedGitBackend(hosted_client, capability_issuer),
        exec_backend=HostedExecBackend(hosted_client, capability_issuer),
    )
    app.include_router(hosted_v1_router, prefix="/api/v1")
    enabled_features["files"] = True
    enabled_features["git"] = True
