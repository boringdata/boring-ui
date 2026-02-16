"""Workspace plugin discovery and hot-reload for boring-ui.

Scans ``{workspace_root}/kurt/api/*.py`` for FastAPI router modules and
``kurt/panels/*/Panel.jsx`` for frontend panel components.  Changes are
picked up automatically via ``watchfiles`` so plugins appear without a
restart.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("boring_ui.workspace_plugins")


# ---------------------------------------------------------------------------
# SwitchableApp – ASGI wrapper whose inner app can be swapped atomically
# ---------------------------------------------------------------------------

class SwitchableApp:
    """ASGI app that delegates to an inner app which can be replaced at runtime."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope, receive, send)

    def swap(self, new_app: ASGIApp) -> None:
        self._app = new_app


# ---------------------------------------------------------------------------
# WorkspacePluginManager
# ---------------------------------------------------------------------------

class WorkspacePluginManager:
    """Discover, load and hot-reload workspace plugins.

    Parameters
    ----------
    workspace_root:
        Absolute path to the workspace (``BORING_UI_WORKSPACE_ROOT``).
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.api_dir = workspace_root / "kurt" / "api"
        self.panels_dir = workspace_root / "kurt" / "panels"
        self._ws_clients: set[WebSocket] = set()
        self._watcher_task: asyncio.Task | None = None

        # Build the initial inner app (may be empty if dirs don't exist yet)
        self._switchable = SwitchableApp(self._build_app())

    # -- public API --------------------------------------------------------

    def get_asgi_app(self) -> SwitchableApp:
        """Return the ASGI app to mount on the main FastAPI at ``/api/x``."""
        return self._switchable

    def list_workspace_panes(self) -> list[dict[str, str]]:
        """Return metadata for each discovered ``kurt/panels/*/Panel.jsx``."""
        panes: list[dict[str, str]] = []
        if not self.panels_dir.is_dir():
            return panes
        for panel_dir in sorted(self.panels_dir.iterdir()):
            if not panel_dir.is_dir():
                continue
            panel_jsx = panel_dir / "Panel.jsx"
            if not panel_jsx.exists():
                continue
            name = panel_dir.name
            panes.append(
                {
                    "id": f"ws-{name}",
                    "name": name,
                    "path": f"{name}/Panel.jsx",
                }
            )
        return panes

    def list_workspace_routes(self) -> list[dict[str, str]]:
        """Return metadata for each discovered ``kurt/api/*.py`` module."""
        routes: list[dict[str, str]] = []
        if not self.api_dir.is_dir():
            return routes
        for py_file in sorted(self.api_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            name = py_file.stem
            routes.append({"name": name, "prefix": f"/api/x/{name}"})
        return routes

    # -- WebSocket broadcast ------------------------------------------------

    def create_ws_router(self) -> APIRouter:
        """Return a router with the ``/ws/plugins`` endpoint."""
        router = APIRouter()

        @router.websocket("/ws/plugins")
        async def plugin_ws(ws: WebSocket) -> None:
            await ws.accept()
            self._ws_clients.add(ws)
            try:
                while True:
                    # Keep connection alive; ignore incoming messages
                    await ws.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                self._ws_clients.discard(ws)

        return router

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.discard(ws)

    # -- file watcher -------------------------------------------------------

    def start_watcher(self) -> None:
        """Start the background file-watcher (call once after the event loop is running)."""
        if self._watcher_task is not None:
            return
        self._watcher_task = asyncio.create_task(self._watch_loop())

    async def _watch_loop(self) -> None:
        try:
            from watchfiles import awatch, Change
        except ImportError:
            logger.warning("watchfiles not installed – workspace hot-reload disabled")
            return

        watch_paths: list[Path] = []
        for d in (self.api_dir, self.panels_dir):
            if d.is_dir():
                watch_paths.append(d)
        if not watch_paths:
            # Neither directory exists yet – watch the workspace root instead
            # so we can pick up plugin dirs when they're created.
            watch_root = self.workspace_root / "kurt"
            if not watch_root.is_dir():
                watch_root = self.workspace_root
            watch_paths = [watch_root]

        logger.info("workspace_plugin_watcher_start", extra={"paths": [str(p) for p in watch_paths]})

        try:
            async for changes in awatch(*watch_paths):
                logger.info("workspace_plugin_change", extra={"changes": str(changes)})
                self._switchable.swap(self._build_app())
                await self._broadcast({"type": "plugin_changed"})
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("workspace_plugin_watcher_error")

    # -- inner app construction --------------------------------------------

    def _build_app(self) -> FastAPI:
        """Import all ``kurt/api/*.py`` modules and mount their routers."""
        inner = FastAPI()

        if not self.api_dir.is_dir():
            return inner

        for py_file in sorted(self.api_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            name = py_file.stem
            try:
                mod = self._load_module(name, py_file)
                router: APIRouter | None = getattr(mod, "router", None)
                if router is None:
                    logger.warning("workspace_plugin_no_router", extra={"file": str(py_file)})
                    continue
                inner.include_router(router, prefix=f"/{name}")
                logger.info("workspace_plugin_loaded", extra={"plugin_name": name})
            except Exception:
                logger.exception("workspace_plugin_load_error", extra={"file": str(py_file)})

        return inner

    @staticmethod
    def _load_module(name: str, path: Path) -> types.ModuleType:
        """Load (or reload) a Python module from *path*."""
        module_name = f"workspace_plugin_{name}"

        # Remove from cache so we always get a fresh copy
        sys.modules.pop(module_name, None)

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
