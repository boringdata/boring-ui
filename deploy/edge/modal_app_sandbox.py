"""Modal ASGI deployment for boring-sandbox data plane (edge gateway).

Deploy:
    modal deploy deploy/edge/modal_app_sandbox.py

The sandbox gateway proxies /w/* requests to Sprite runtimes.
Auth and control-plane routes are handled by boring-ui (deploy/edge/modal_app.py).

Requires boring-sandbox source: checks vendor/boring-sandbox/ first,
then falls back to cloning from GitHub.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import modal

app = modal.App("boring-sandbox")

# Resolve vendor root — check local checkout, then clone if needed.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_CANDIDATE = _REPO_ROOT / "vendor" / "boring-sandbox"


def _ensure_boring_sandbox() -> Path | None:
    """Ensure boring-sandbox source is available locally."""
    if _CANDIDATE.is_dir() and (_CANDIDATE / "src" / "boring_sandbox").is_dir():
        return _CANDIDATE
    # Clone from GitHub (shallow, no submodules)
    clone_dir = _REPO_ROOT / "vendor" / "boring-sandbox"
    try:
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth=1", "--no-recurse-submodules",
             "https://github.com/boringdata/boring-sandbox.git",
             str(clone_dir)],
            check=True, capture_output=True, text=True,
        )
        return clone_dir
    except Exception:
        return None


VENDOR_ROOT: Path | None = _ensure_boring_sandbox()


def _base_image() -> modal.Image:
    assert VENDOR_ROOT is not None, "vendor/boring-sandbox submodule not found"
    return (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "fastapi>=0.115",
            "httpx>=0.27",
            "asyncpg>=0.30",
            "PyJWT>=2.9",
            "cryptography>=42",
            "websockets>=13",
            "uvicorn>=0.30",
        )
        .apt_install("wget", "unzip", "curl")
        .run_commands(
            "wget -qO /tmp/vault.zip https://releases.hashicorp.com/vault/1.17.5/vault_1.17.5_linux_amd64.zip",
            "unzip -o /tmp/vault.zip -d /usr/local/bin && rm /tmp/vault.zip",
            "curl -fsSL https://sprites.dev/install.sh | sh",
            "ln -sf /root/.local/bin/sprite /usr/local/bin/sprite",
            "sprite --help >/dev/null",
        )
        .add_local_dir(str(VENDOR_ROOT / "apps"), "/root/apps", copy=True)
        .add_local_dir(str(VENDOR_ROOT / "src" / "boring_sandbox"), "/root/src/boring_sandbox", copy=True)
        .add_local_dir(str(VENDOR_ROOT / "deploy"), "/root/deploy", copy=True)
    )


def _with_optional_bundles(img: modal.Image) -> modal.Image:
    if VENDOR_ROOT is None:
        return img
    artifacts = VENDOR_ROOT / "artifacts"
    for name in ("boring-macro-bundle.tar.gz", "boring-ui-bundle.tar.gz"):
        bundle = artifacts / name
        if bundle.exists():
            img = img.add_local_file(
                str(bundle),
                f"/root/artifacts/{name}",
                copy=True,
            )
    return img


# Image building is guarded by VENDOR_ROOT being available (local CLI only).
if VENDOR_ROOT is not None:
    image = _with_optional_bundles(_base_image()).env(
        {
            "PATH": "/root/.local/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": "/root/src",
            "APP_ID_DEFAULT": "boring-macro",
        }
    )
else:
    # Container-side fallback — the image is already built;
    # Modal ignores the Image object at runtime.
    image = modal.Image.debian_slim(python_version="3.12")

# Modal secrets — create via `modal secret create boring-sandbox-secrets ...`
secrets = modal.Secret.from_name("boring-sandbox-secrets")
macro_secrets = modal.Secret.from_name("boring-sandbox-macro-secrets")
sprite_secrets = modal.Secret.from_name("boring-sandbox-sprite-secrets")
mail_secrets = modal.Secret.from_name("boring-sandbox-mail-secrets")
macro_runtime_secrets = modal.Secret.from_name("boring-sandbox-macro-runtime-secrets")


@app.function(
    image=image,
    secrets=[secrets, macro_secrets, sprite_secrets, mail_secrets, macro_runtime_secrets],
    timeout=600,
    min_containers=1,
    memory=512,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def gateway():
    """Create and return the boring-sandbox gateway ASGI application."""
    from boring_sandbox.gateway.app import create_app

    return create_app()
