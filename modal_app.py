"""
Modal Deployment Configuration for Boring UI.

This module configures the Modal deployment with:
- FastAPI backend (boring-ui API)
- Static frontend files (Vite build)
- Secrets for external services
- Resource limits and scaling

Deploy with: modal deploy modal_app.py
Run locally: modal serve modal_app.py
"""

import modal

# --- Modal App Configuration ---

app = modal.App(
    name="boring-ui",
    secrets=[
        modal.Secret.from_name("anthropic-key", required_keys=["ANTHROPIC_API_KEY"]),
        modal.Secret.from_name("sprite-bearer", required_keys=["SPRITE_BEARER_TOKEN"]),
        modal.Secret.from_name("supabase-creds", required_keys=[
            "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        ]),
        modal.Secret.from_name("jwt-secret", required_keys=["SUPABASE_JWT_SECRET"]),
        modal.Secret.from_name("session-config", required_keys=["SESSION_SECRET"]),
    ],
)

# --- Container Image ---

# Build frontend assets during image build
image = (
    modal.Image.debian_slim(python_version="3.11")
    # Install Node.js for frontend build
    .apt_install("curl")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
    )
    # Copy frontend source and build
    .copy_local_dir("src/front", "/app/src/front")
    .copy_local_file("package.json", "/app/package.json")
    .copy_local_file("package-lock.json", "/app/package-lock.json", dest="/app/package-lock.json")
    .copy_local_file("vite.config.ts", "/app/vite.config.ts")
    .copy_local_file("index.html", "/app/index.html")
    .copy_local_file("tailwind.config.js", "/app/tailwind.config.js")
    .run_commands(
        "cd /app && npm ci",
        "cd /app && npm run build",
    )
    # Install Python dependencies
    .pip_install(
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.23.0",
        "ptyprocess>=0.7.0",
        "websockets>=11.0",
        "aiofiles>=23.0.0",
    )
    # Copy Python backend
    .copy_local_dir("src/back", "/app/src/back")
)

# --- Volume for Workspace Data ---

workspace_volume = modal.Volume.from_name("boring-ui-workspace", create_if_missing=True)

# --- FastAPI ASGI App ---


@app.function(
    image=image,
    volumes={"/workspace": workspace_volume},
    cpu=2.0,
    memory=1024,
    timeout=600,
    min_containers=0,  # Scale to zero when idle
    max_containers=10,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web_app():
    """
    Modal ASGI entry point for the Boring UI application.

    Serves both the FastAPI backend and static frontend files.
    """
    from fastapi.staticfiles import StaticFiles
    from boring_ui.api.app import create_app
    from boring_ui.api.config import APIConfig

    # Create backend API with workspace volume
    config = APIConfig(workspace_path="/workspace")
    backend = create_app(config=config)

    # Mount static frontend files
    backend.mount("/assets", StaticFiles(directory="/app/dist/assets"), name="assets")

    # Serve index.html for all non-API routes (SPA routing)
    @backend.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        from fastapi.responses import FileResponse
        # API routes are already handled by FastAPI routers
        if full_path.startswith("api/"):
            return {"error": "Not found"}, 404
        return FileResponse("/app/dist/index.html")

    return backend


# --- CLI Commands ---

@app.local_entrypoint()
def main():
    """Local entrypoint for testing and development."""
    print("Boring UI - Modal Deployment")
    print("=" * 50)
    print()
    print("Commands:")
    print("  modal deploy modal_app.py    - Deploy to Modal")
    print("  modal serve modal_app.py     - Run locally with hot reload")
    print()
    print("Features:")
    print("  - FastAPI backend with file/git/pty/stream APIs")
    print("  - React frontend (Vite build)")
    print("  - WebSocket support for terminals and streaming")
    print("  - Persistent workspace storage")
    print()
    print("Environment:")
    print("  - Workspace: /workspace (persistent volume)")
    print("  - Frontend: /app/dist (static build)")
    print("  - Backend: /app/src/back")
    print()
