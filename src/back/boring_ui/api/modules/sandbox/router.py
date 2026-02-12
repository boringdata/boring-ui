"""Sandbox lifecycle and target resolution routes."""

from __future__ import annotations

from fastapi import APIRouter

from .schemas import (
    ActiveSandboxResponse,
    CreateSandboxRequest,
    SandboxLifecycleResponse,
    SandboxMetadata,
    SandboxTargetResolution,
)
from .service import SandboxService, SandboxStore, TargetResolver


def create_sandbox_router(store: SandboxStore, resolver: TargetResolver) -> APIRouter:
    """Create router for sandbox management endpoints."""
    router = APIRouter(tags=['sandbox'])
    service = SandboxService(store)

    @router.get('', response_model=list[SandboxMetadata])
    async def list_sandboxes() -> list[SandboxMetadata]:
        return service.list()

    @router.post('', response_model=SandboxLifecycleResponse)
    async def create_sandbox(body: CreateSandboxRequest) -> SandboxLifecycleResponse:
        return service.create(body)

    @router.get('/active', response_model=ActiveSandboxResponse)
    async def get_active_sandbox() -> ActiveSandboxResponse:
        return service.get_active()

    @router.post('/{sandbox_id}/activate', response_model=ActiveSandboxResponse)
    async def activate_sandbox(sandbox_id: str) -> ActiveSandboxResponse:
        return service.activate(sandbox_id)

    @router.get('/target', response_model=SandboxTargetResolution)
    async def resolve_target(
        sandbox_id: str | None = None,
        workspace_id: str | None = None,
    ) -> SandboxTargetResolution:
        return resolver.resolve(sandbox_id=sandbox_id, workspace_id=workspace_id)

    @router.get('/{sandbox_id}', response_model=SandboxMetadata)
    async def get_sandbox(sandbox_id: str) -> SandboxMetadata:
        return service.get(sandbox_id)

    @router.post('/{sandbox_id}/start', response_model=SandboxLifecycleResponse)
    async def start_sandbox(sandbox_id: str) -> SandboxLifecycleResponse:
        return service.start(sandbox_id)

    @router.post('/{sandbox_id}/stop', response_model=SandboxLifecycleResponse)
    async def stop_sandbox(sandbox_id: str) -> SandboxLifecycleResponse:
        return service.stop(sandbox_id)

    return router
