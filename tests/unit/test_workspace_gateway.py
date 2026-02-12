"""Unit tests for workspace gateway mode dispatch."""

import pytest

from boring_ui.api.config import APIConfig, RuntimeConfig
from boring_ui.api.storage import LocalStorage
from boring_ui.api.testing import StubExecClient, StubProxyClient, StubServicesClient
from boring_ui.api.testing.factories import sandbox_runtime_config_factory
from boring_ui.api.workspace_gateway import (
    LocalWorkspaceGateway,
    SandboxWorkspaceGateway,
    create_workspace_gateway,
)


def test_create_workspace_gateway_local_mode(tmp_path):
    config = APIConfig(workspace_root=tmp_path)
    storage = LocalStorage(tmp_path)
    runtime = RuntimeConfig(workspace_mode='local', sandbox=None)

    gateway = create_workspace_gateway(config, runtime, storage)

    assert isinstance(gateway, LocalWorkspaceGateway)
    assert gateway.is_local is True
    assert gateway.is_sandbox is False
    assert gateway.describe()['mode'] == 'local'


@pytest.mark.asyncio
async def test_create_workspace_gateway_sandbox_mode_with_injected_clients(tmp_path):
    config = APIConfig(workspace_root=tmp_path)
    storage = LocalStorage(tmp_path)
    runtime = sandbox_runtime_config_factory()

    services = StubServicesClient(ready=True)
    proxy = StubProxyClient()
    exec_client = StubExecClient()

    gateway = create_workspace_gateway(
        config,
        runtime,
        storage,
        services_client=services,  # type: ignore[arg-type]
        proxy_client=proxy,        # type: ignore[arg-type]
        exec_client=exec_client,   # type: ignore[arg-type]
    )

    assert isinstance(gateway, SandboxWorkspaceGateway)
    assert gateway.is_sandbox is True
    assert gateway.is_local is False
    assert await gateway.check_ready() is True
    desc = gateway.describe()
    assert desc['mode'] == 'sandbox'
    assert desc['sprite_name'] == runtime.sandbox.sprite_name


@pytest.mark.asyncio
async def test_sandbox_gateway_ready_reflects_services_client(tmp_path):
    config = APIConfig(workspace_root=tmp_path)
    storage = LocalStorage(tmp_path)
    runtime = sandbox_runtime_config_factory()

    services = StubServicesClient(ready=False)

    gateway = create_workspace_gateway(
        config,
        runtime,
        storage,
        services_client=services,  # type: ignore[arg-type]
        proxy_client=StubProxyClient(),  # type: ignore[arg-type]
        exec_client=StubExecClient(),    # type: ignore[arg-type]
    )

    assert await gateway.check_ready() is False
