"""Fly.io fly-replay routing implementation of WorkspaceRouter."""

from __future__ import annotations

import logging
from typing import Callable, Awaitable

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class FlyReplayRouter:
    """WorkspaceRouter that uses Fly Proxy's fly-replay header.

    When a response includes ``fly-replay: instance=<machine_id>``,
    Fly's edge proxy replays the original request (including body and
    headers) to that specific Machine. Zero bytes proxied by our code.
    Works for HTTP and WebSocket upgrades.
    """

    def __init__(
        self,
        lookup_machine_id: Callable[[str], Awaitable[str | None]],
    ) -> None:
        self._lookup = lookup_machine_id

    async def route(self, workspace_id: str, request: Request) -> Response:
        """Return a fly-replay response that routes to the workspace Machine."""
        machine_id = await self._lookup(workspace_id)
        if not machine_id:
            return Response(status_code=404, content="Workspace not found")
        return Response(
            status_code=200,
            headers={"fly-replay": f"instance={machine_id}"},
        )
