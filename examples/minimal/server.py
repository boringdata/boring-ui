#!/usr/bin/env python3
"""Minimal example server using boring-ui backend.

This demonstrates how to use boring-ui's create_app() factory
to quickly spin up a web IDE backend.

Usage:
    python server.py
    # or: uvicorn server:app --reload

The server will:
- Serve file operations for the current directory
- Provide git status/diff endpoints
- Enable PTY terminal WebSocket connections
- Enable Claude chat WebSocket connections
"""
import os
from pathlib import Path

from boring_ui.api import create_app, APIConfig


# Configure the API
# Change workspace_root to your project directory
config = APIConfig(
    workspace_root=Path.cwd(),
    cors_origins=[
        'http://localhost:5173',  # Vite dev server
        'http://localhost:3000',  # Alternative dev server
    ],
)

# Create the FastAPI app
# Claude stream routes are opt-in to keep the minimal server lightweight.
enable_claude_stream = os.getenv('BORING_UI_ENABLE_CLAUDE_STREAM', '').lower() in ('1', 'true', 'yes')
app = create_app(config, include_stream=enable_claude_stream)


if __name__ == '__main__':
    import uvicorn

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    boring-ui API Server                       ║
╠══════════════════════════════════════════════════════════════╣
║  Workspace: {str(config.workspace_root):<48} ║
║  API Docs:  http://localhost:8000/docs                       ║
║  Health:    http://localhost:8000/health                     ║
╚══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        reload=False,  # Set to True for development
    )
