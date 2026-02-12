"""Production runtime app for boring-ui.

Serves API + built frontend from one FastAPI service when BORING_UI_STATIC_DIR is set.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .api import APIConfig, create_app


workspace_root = Path(os.environ.get("BORING_UI_WORKSPACE_ROOT", "/home/sprite"))
app = create_app(APIConfig(workspace_root=workspace_root))

static_dir = os.environ.get("BORING_UI_STATIC_DIR", "")
if static_dir:
    static_path = Path(static_dir)
    if static_path.exists() and static_path.is_dir():
        assets_path = static_path / "assets"
        if assets_path.exists() and assets_path.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            requested = static_path / full_path
            if full_path and requested.exists() and requested.is_file():
                return FileResponse(requested)
            return FileResponse(static_path / "index.html")
