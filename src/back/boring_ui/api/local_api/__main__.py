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
from cryptography.hazmat.primitives import serialization as _ser

from .app import create_local_api_app


def main():
    port = int(os.environ.get("LOCAL_API_PORT", "2469"))
    workspace = Path(os.environ.get("WORKSPACE_ROOT", Path.cwd()))
    workspace.mkdir(parents=True, exist_ok=True)

    # Read capability keys for token validation (optional for parity mode)
    cap_pub_key = os.environ.get("CAPABILITY_PUBLIC_KEY", "")
    if cap_pub_key:
        cap_pub_key = cap_pub_key.replace("\\n", "\n")
    elif os.environ.get("CAPABILITY_PRIVATE_KEY"):
        try:
            priv_pem = os.environ["CAPABILITY_PRIVATE_KEY"].replace("\\n", "\n").encode()
            private_key = _ser.load_pem_private_key(priv_pem, password=None)
            cap_pub_key = private_key.public_key().public_bytes(
                _ser.Encoding.PEM,
                _ser.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
        except Exception as exc:
            print(f"Failed to derive CAPABILITY_PUBLIC_KEY from CAPABILITY_PRIVATE_KEY: {exc}", file=sys.stderr)
            cap_pub_key = ""

    app = create_local_api_app(workspace, capability_public_key_pem=cap_pub_key or None)

    print(f"Local API parity server starting on http://127.0.0.1:{port}")
    print(f"Workspace: {workspace}")
    print(f"Capability auth: {'enabled' if cap_pub_key else 'disabled'}")

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
