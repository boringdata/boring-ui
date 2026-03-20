"""Command execution route for boring-ui API."""
from dataclasses import replace

from fastapi import APIRouter, Depends, Request

from ...config import APIConfig
from ...policy import enforce_delegated_policy_or_none
from ...storage import Storage
from ...workspace import WorkspaceContext, resolve_workspace_context
from .schemas import ExecRequest
from .service import execute_command


def create_exec_router(config: APIConfig, storage: Storage) -> APIRouter:
    """Create command execution router.

    Args:
        config: API configuration (for workspace root)
        storage: Storage backend (for workspace context resolution)

    Returns:
        Configured APIRouter with exec endpoint
    """
    router = APIRouter(tags=['exec'])

    async def _workspace_context(request: Request) -> WorkspaceContext:
        return await resolve_workspace_context(request, config=config, storage=storage)

    @router.post('/exec')
    async def exec_command(
        request: Request,
        body: ExecRequest,
        ctx: WorkspaceContext = Depends(_workspace_context),
    ):
        """Execute a shell command in the workspace."""
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.exec"},
            operation="workspace-core.exec.run",
        )
        if deny is not None:
            return deny
        request_config = replace(config, workspace_root=ctx.root_path)
        return await execute_command(
            body.command,
            body.cwd,
            request_config.workspace_root,
        )

    return router
