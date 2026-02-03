"""FastAPI routers and utilities for boring-ui backend.

This module provides composable FastAPI routers for building web IDE backends.

Example:
    # Simple usage with create_app()
    from boring_ui.api import create_app
    app = create_app()

    # Custom configuration
    from boring_ui.api import create_app, APIConfig
    from pathlib import Path
    config = APIConfig(workspace_root=Path('/my/project'))
    app = create_app(config)

    # Compose routers manually
    from fastapi import FastAPI
    from boring_ui.api import (
        APIConfig, LocalStorage,
        create_file_router, create_git_router
    )
    config = APIConfig(workspace_root=Path.cwd())
    storage = LocalStorage(config.workspace_root)
    app = FastAPI()
    app.include_router(create_file_router(config, storage), prefix='/api')
    app.include_router(create_git_router(config), prefix='/api/git')
"""

# Configuration
from .config import APIConfig

# Storage
from .storage import Storage, LocalStorage, S3Storage

# Router factories
from .file_routes import create_file_router
from .git_routes import create_git_router
from .pty_bridge import create_pty_router
from .stream_bridge import create_stream_router
from .approval import (
    ApprovalStore,
    InMemoryApprovalStore,
    create_approval_router,
)

# App factory
from .app import create_app

__all__ = [
    # Configuration
    'APIConfig',
    # Storage
    'Storage',
    'LocalStorage',
    'S3Storage',
    # Router factories
    'create_file_router',
    'create_git_router',
    'create_pty_router',
    'create_stream_router',
    'create_approval_router',
    # Approval
    'ApprovalStore',
    'InMemoryApprovalStore',
    # App factory
    'create_app',
]
