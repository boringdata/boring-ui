#!/usr/bin/env python3
"""Internal sandbox API application (bd-1pwb.4).

Runs as a standalone service on the sandbox/remote machine.
Provides file, git, and exec operations for the control plane.

Usage:
    python3 -m boring_ui.api.internal_app

Environment:
    WORKSPACE_ROOT: Path to workspace (default: current directory)
    INTERNAL_API_PORT: Port to listen on (default: 9000)
    INTERNAL_API_HOST: Host to bind to (default: 0.0.0.0)
    CAPABILITY_PUBLIC_KEY: RSA public key PEM for capability token validation
    SERVICE_KEY_VERSIONS: JSON map of service key version -> PEM public key
    SERVICE_CURRENT_VERSION: Active key version for service validation
"""

import os
import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from boring_ui.api.local_api import create_local_api_router
from boring_ui.api.capability_tokens import CapabilityTokenValidator, JTIReplayStore
from boring_ui.api.sandbox_auth import add_capability_auth_middleware
from boring_ui.api.service_auth import ServiceTokenValidator, add_service_auth_middleware


def create_internal_app():
    """Create FastAPI app for internal sandbox operations (bd-1adh.2.3).

    Uses local_api routers for file, git, and exec operations.
    Runs as standalone service on sandbox/remote machine or in-process in LOCAL mode.

    Returns:
        FastAPI application with local_api routers.
    """
    # Read config from environment
    workspace_root = Path(os.environ.get('WORKSPACE_ROOT', Path.cwd()))
    workspace_root.mkdir(parents=True, exist_ok=True)

    # Create app
    app = FastAPI(
        title='Boring UI Internal Sandbox API',
        description='Private API for sandbox file, git, and exec operations',
        version='1.0.0',
    )

    # CORS - allow control plane to access
    control_plane_origins = os.environ.get(
        'CONTROL_PLANE_ORIGINS',
        'http://localhost:8000,http://127.0.0.1:8000'
    ).split(',')

    app.add_middleware(
        CORSMiddleware,
        allow_origins=control_plane_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # Mount local_api router (file, git, exec operations)
    # Routes available at /internal/v1/files/*, /internal/v1/git/*, /internal/v1/exec/*
    local_api_router = create_local_api_router(workspace_root)
    app.include_router(local_api_router)

    # Capability auth for internal API routes.
    # Expected caller: hosted control API issuing short-lived capability tokens.
    capability_public_key = os.environ.get('CAPABILITY_PUBLIC_KEY', '').strip()
    if capability_public_key:
        validator = CapabilityTokenValidator(
            capability_public_key.replace("\\n", "\n")
        )
        add_capability_auth_middleware(
            app,
            validator=validator,
            replay_store=JTIReplayStore(),
            required_prefix="/internal/v1",
        )

    # Optional service-to-service auth; enabled when key versions are configured.
    service_validator = ServiceTokenValidator.from_env()
    if service_validator:
        add_service_auth_middleware(
            app,
            validator=service_validator,
            required_prefix="/internal/v1",
            accepted_services=["hosted-api"],
        )

    return app


if __name__ == '__main__':
    app = create_internal_app()

    # Get config from environment
    host = os.environ.get('INTERNAL_API_HOST', '0.0.0.0')
    port = int(os.environ.get('INTERNAL_API_PORT', '9000'))

    print(f"Starting Internal Sandbox API on {host}:{port}")
    print(f"Workspace: {os.environ.get('WORKSPACE_ROOT', Path.cwd())}")

    uvicorn.run(app, host=host, port=port)
