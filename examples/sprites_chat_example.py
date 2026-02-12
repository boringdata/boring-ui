#!/usr/bin/env python3
"""
Example: Running boring-ui with Sprites provider + regular chat.

This script demonstrates:
1. Starting the backend with Sprites sandbox provider
2. Enabling both Companion chat and Sprites sandbox
3. Running the frontend
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Get Sprites credentials from environment
SPRITES_TOKEN = os.getenv("SPRITES_TOKEN")
SPRITES_ORG = os.getenv("SPRITES_ORG")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def check_requirements():
    """Check if required tools are available."""
    print("Checking requirements...")

    required = {
        "python3": "Python",
        "npm": "Node.js",
        "pip3": "pip",
    }

    for cmd, name in required.items():
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"❌ {name} not found. Install it to continue.")
            return False

    if not SPRITES_TOKEN or not SPRITES_ORG:
        print("❌ Missing Sprites credentials:")
        print("   export SPRITES_TOKEN=your-token")
        print("   export SPRITES_ORG=your-org")
        return False

    if not ANTHROPIC_API_KEY:
        print("⚠️  ANTHROPIC_API_KEY not set (optional for Claude chat)")

    print("✓ All requirements met")
    return True


def install_dependencies():
    """Install backend and frontend dependencies."""
    print("\nInstalling dependencies...")

    # Backend
    print("  Installing backend...")
    result = subprocess.run(
        ["pip3", "install", "-e", ".", "--break-system-packages"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"❌ Backend install failed: {result.stderr.decode()}")
        return False

    # Frontend
    print("  Installing frontend...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"❌ Frontend install failed: {result.stderr.decode()}")
        return False

    print("✓ Dependencies installed")
    return True


def start_backend():
    """Start the FastAPI backend with Sprites provider."""
    print("\nStarting backend (port 8000)...")

    env = os.environ.copy()
    env.update({
        "SANDBOX_PROVIDER": "sprites",
        "SPRITES_TOKEN": SPRITES_TOKEN,
        "SPRITES_ORG": SPRITES_ORG,
        "SANDBOX_PORT": "2468",
    })

    script = """
from boring_ui.api.app import create_app
import uvicorn

app = create_app(
    include_sandbox=True,      # Enable Sprites sandbox
    include_companion=True,    # Enable Companion chat
)

uvicorn.run(
    app,
    host='0.0.0.0',
    port=8000,
    log_level='info',
)
"""

    proc = subprocess.Popen(
        ["python3", "-c", script],
        cwd=Path(__file__).parent.parent,
        env=env,
    )
    return proc


def start_frontend():
    """Start the Vite frontend dev server."""
    print("Starting frontend (port 5173)...")

    proc = subprocess.Popen(
        ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"],
        cwd=Path(__file__).parent.parent,
    )
    return proc


def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 60)
    print("🚀 boring-ui with Sprites Provider + Chat")
    print("=" * 60)
    print(f"\n📊 Configuration:")
    print(f"  • Provider:  Sprites.dev ({SPRITES_ORG})")
    print(f"  • Backend:   http://localhost:8000")
    print(f"  • Frontend:  http://localhost:5173")
    print(f"  • Chat:      Companion + Sandbox")
    print(f"\n🔗 Quick Links:")
    print(f"  • UI:         http://localhost:5173")
    print(f"  • Sandbox:    http://localhost:5173?chat=sandbox")
    print(f"  • Companion:  http://localhost:5173?chat=companion")
    print(f"\n📝 API Endpoints:")
    print(f"  • Status:     curl http://localhost:8000/api/sandbox/status")
    print(f"  • Start:      curl -X POST http://localhost:8000/api/sandbox/start")
    print(f"  • Logs:       curl http://localhost:8000/api/sandbox/logs")
    print(f"  • Health:     curl http://localhost:8000/api/sandbox/health")
    print("\n" + "=" * 60)
    print("Press Ctrl+C to stop\n")


def main():
    """Main entry point."""
    if not check_requirements():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    print_banner()

    try:
        backend_proc = start_backend()
        time.sleep(3)  # Wait for backend to start

        frontend_proc = start_frontend()
        time.sleep(2)  # Wait for frontend to start

        # Wait for processes
        backend_proc.wait()
        frontend_proc.wait()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait(timeout=5)
        frontend_proc.wait(timeout=5)
        print("✓ Stopped")


if __name__ == "__main__":
    main()
