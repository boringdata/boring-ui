"""Test factory helpers for sandbox mode testing.

Provides convenience functions for creating test apps, configs,
and auth headers with sensible defaults.
"""
from __future__ import annotations

from pathlib import Path
from boring_ui.api.config import (
    SandboxConfig,
    SandboxServiceTarget,
    SpriteLayout,
    RuntimeConfig,
)
from boring_ui.api.internal_auth import generate_auth_token
from boring_ui.api.workspace_contract import INTERNAL_AUTH_HEADER


# Default test secret for internal auth.
TEST_AUTH_SECRET = 'test-secret-for-sandbox-testing-only!'


def sandbox_config_factory(
    *,
    base_url: str = 'https://sprites.test.internal',
    sprite_name: str = 'test-sprite',
    api_token: str = 'test-api-token-value-placeholder',
    session_token_secret: str = 'x' * 32,
    service_host: str = 'workspace-service',
    service_port: int = 8443,
    service_path: str = '/api/workspace',
    multi_tenant: bool = False,
    routing_mode: str = 'single_tenant',
) -> SandboxConfig:
    """Create a SandboxConfig with sensible test defaults."""
    return SandboxConfig(
        base_url=base_url,
        sprite_name=sprite_name,
        api_token=api_token,
        session_token_secret=session_token_secret,
        service_target=SandboxServiceTarget(
            host=service_host,
            port=service_port,
            path=service_path,
        ),
        multi_tenant=multi_tenant,
        routing_mode=routing_mode,
    )


def sandbox_runtime_config_factory(**kwargs) -> RuntimeConfig:
    """Create a RuntimeConfig in sandbox mode with test defaults."""
    return RuntimeConfig(
        workspace_mode='sandbox',
        sandbox=sandbox_config_factory(**kwargs),
    )


def auth_headers(
    secret: str = TEST_AUTH_SECRET,
    timestamp: float | None = None,
) -> dict[str, str]:
    """Generate internal auth headers for test requests."""
    token = generate_auth_token(secret, timestamp=timestamp)
    return {INTERNAL_AUTH_HEADER: token}


def sandbox_test_app(
    *,
    workspace_root: Path | None = None,
    runtime_config: RuntimeConfig | None = None,
    routers: list[str] | None = None,
):
    """Create a FastAPI test app configured for sandbox mode testing.

    Returns a FastAPI app with sandbox runtime config and minimal
    router set suitable for testing.
    """
    from boring_ui.api.app import create_app
    from boring_ui.api.config import APIConfig

    workspace_root = workspace_root or Path('/tmp/test-workspace')
    runtime_config = runtime_config or sandbox_runtime_config_factory()
    routers = routers or ['files', 'git']

    config = APIConfig(workspace_root=workspace_root)
    return create_app(
        config=config,
        runtime_config=runtime_config,
        routers=routers,
    )
