"""Run local-api as a standalone HTTP server for parity testing (bd-1adh.7.2).

Usage:
    LOCAL_API_PORT=2469 python -m boring_ui.api.local_api

Starts a uvicorn server for the local-api workspace plane. Used with
LOCAL_PARITY_MODE=http on the control plane to exercise the same HTTP
transport path as hosted mode.
"""

import os
import sys
from pathlib import Path

import uvicorn

from .app import create_local_api_app


def main():
    port = int(os.environ.get("LOCAL_API_PORT", "2469"))
    workspace = Path(os.environ.get("WORKSPACE_ROOT", Path.cwd()))
    workspace.mkdir(parents=True, exist_ok=True)

    app = create_local_api_app(workspace)

    print(f"Local API parity server starting on http://127.0.0.1:{port}")
    print(f"Workspace: {workspace}")

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

main()
