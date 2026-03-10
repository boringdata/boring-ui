# 6. Deployment

[< Back to Index](README.md) | [Prev: Configuration](05-configuration.md) | [Next: Infrastructure >](07-infrastructure.md)

---

## 6.1 Core Mode (Direct ASGI)

Simplest deploy: your FastAPI app serves API + static frontend directly on Modal.

### `deploy/core/deploy.env`

```bash
MODAL_DEPLOY_NAME=my-app
MODAL_ENV=
AUTO_BUILD=1
```

### `deploy/core/deploy.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_DEPLOY_TAG="core"
source "${ROOT_DIR}/deploy/shared/_deploy_common.sh"

CONFIG_PATH="${1:-${ROOT_DIR}/deploy/core/deploy.env}"
load_deploy_config "${CONFIG_PATH}" MODAL_DEPLOY_NAME MODAL_ENV AUTO_BUILD

MODAL_DEPLOY_NAME="${MODAL_DEPLOY_NAME:-my-app}"
AUTO_BUILD="${AUTO_BUILD:-1}"

need_cmd modal

if [[ "${AUTO_BUILD}" == "1" ]]; then
  echo "[$_DEPLOY_TAG] Building frontend bundle"
  ( cd "${ROOT_DIR}/src/web" && npm run build -- --outDir dist-front )
elif [[ ! -f "${ROOT_DIR}/src/web/dist-front/index.html" ]]; then
  die "Missing src/web/dist-front/index.html and AUTO_BUILD=0"
fi

run_modal_deploy "${MODAL_DEPLOY_NAME}" "deploy/core/modal_app.py" "${ROOT_DIR}"

echo "[$_DEPLOY_TAG] Complete"
```

### `deploy/core/modal_app.py`

```python
"""Modal ASGI deployment for my-app (core mode)."""
from __future__ import annotations
from pathlib import Path
import modal

app = modal.App("my-app")

def _base_image() -> modal.Image:
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "fastapi>=0.115",
            "httpx>=0.27",
            "websockets>=13",
            "python-dotenv>=1.0",
            "asyncpg>=0.30",
            "PyJWT[crypto]>=2.9",
            "ptyprocess>=0.7",
            "uvicorn>=0.30",
            "wsproto",
            # Add your domain-specific deps here
        )
        .apt_install("git")
        .add_local_dir("src/web/backend", "/root/src/web/backend", copy=True)
        .add_local_dir(
            "interface/boring-ui/src/back/boring_ui",
            "/root/interface/boring-ui/src/back/boring_ui",
            copy=True,
        )
    )
    if Path("src/web/dist-front").is_dir():
        image = image.add_local_dir(
            "src/web/dist-front", "/root/src/web/dist-front", copy=True
        )
    return image

image = _base_image().env({
    "PYTHONPATH": "/root/src/web:/root/interface/boring-ui/src/back",
    "CONTROL_PLANE_ENABLED": "true",
    "CONTROL_PLANE_PROVIDER": "neon",  # or "supabase" for legacy
    "CONTROL_PLANE_APP_ID": "my-app",
    "MY_APP_WORKSPACE_ROOT": "/tmp/my-app-workspace",
    "MY_APP_STATIC_DIR": "/root/src/web/dist-front",
    "AUTH_APP_NAME": "My App",
    "AUTH_APP_DESCRIPTION": "Your AI-powered tool",
})

secrets = modal.Secret.from_name("my-app-secrets")

@app.function(
    image=image,
    secrets=[secrets],
    timeout=600,
    min_containers=1,
    memory=1024,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def frontend():
    from backend.config import normalize_deploy_env
    normalize_deploy_env()
    from backend.runtime import app
    return app
```

**Critical:** `normalize_deploy_env()` MUST run before `from backend.runtime import app` because `runtime.py` calls `create_app()` at import time.

---

## 6.2 Edge Mode (Sandbox Gateway)

For isolated workspaces with full sandbox (file system, PTY, git per user). Routes through boring-sandbox.

### `deploy/edge/my-app.app.toml`

```toml
[app]
id = "my-app"
display_name = "My App"

[supabase]
project_url = "secret/agent/my-app-supabase-project-url#url"
publishable_key = "secret/agent/my-app-supabase-publishable-key#key"
service_role_key = "secret/agent/my-app-supabase-service-role-key#key"
db_url = "secret/agent/my-app-supabase-db-url#url"

[release]
bootstrap_cmd = "bash /home/sprite/app/bootstrap.sh"
internal_port = 8080
health_path = "/health"

[email]
provider = "resend"
resend_api_key = "secret/agent/services/resend#api_key"
resend_from_email = "auth@mail.example.com"
resend_from_name = "My App"

[modal]
volume_name = "my-app-artifacts"
```

### `deploy/edge/deploy.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_DEPLOY_TAG="edge"
source "${ROOT_DIR}/deploy/shared/_deploy_common.sh"

CONFIG_PATH="${1:-${ROOT_DIR}/deploy/edge/deploy.env}"
load_deploy_config "${CONFIG_PATH}" \
  APP_ID MODAL_DEPLOY_NAME MODAL_ENV BUNDLE_OUTPUT BM_WHEEL_PATH

BORING_UI_DIR="${ROOT_DIR}/interface/boring-ui"
[[ -d "${BORING_UI_DIR}" ]] || die "Missing boring-ui submodule"

VENDOR_SANDBOX="${BORING_UI_DIR}/vendor/boring-sandbox"
[[ -d "${VENDOR_SANDBOX}/src/boring_sandbox" ]] || {
  echo "[$_DEPLOY_TAG] Initializing boring-sandbox submodule..."
  git -C "${BORING_UI_DIR}" submodule update --init vendor/boring-sandbox
}

APP_ID="${APP_ID:-my-app}"
MODAL_DEPLOY_NAME="${MODAL_DEPLOY_NAME:-my-app}"

need_cmd modal

# Sync app.toml
APP_TOML_SOURCE="${ROOT_DIR}/deploy/edge/${APP_ID}.app.toml"
APP_TOML_TARGET="${VENDOR_SANDBOX}/apps/${APP_ID}/app.toml"
mkdir -p "$(dirname "${APP_TOML_TARGET}")"
cp "${APP_TOML_SOURCE}" "${APP_TOML_TARGET}"

# Build bundle from wheel
BM_WHEEL_PATH="${BM_WHEEL_PATH:-$(ls -1t "${ROOT_DIR}"/dist/*.whl 2>/dev/null | head -1 || true)}"
[[ -n "${BM_WHEEL_PATH}" && -f "${BM_WHEEL_PATH}" ]] || \
  die "Missing wheel. Build with ./scripts/build_web_wheel.sh"

BUNDLE_OUTPUT="${BUNDLE_OUTPUT:-${VENDOR_SANDBOX}/artifacts/${APP_ID}-bundle.tar.gz}"
mkdir -p "$(dirname "${BUNDLE_OUTPUT}")"
BM_WHEEL_PATH="${BM_WHEEL_PATH}" BUNDLE_OUTPUT="${BUNDLE_OUTPUT}" \
  bash "${BORING_UI_DIR}/deploy/edge/scripts/build_macro_bundle.sh" "${ROOT_DIR}"

run_modal_deploy "${MODAL_DEPLOY_NAME}" "deploy/edge/modal_app_sandbox.py" "${BORING_UI_DIR}"

echo "[$_DEPLOY_TAG] Complete"
```

---

## 6.3 Shared Deploy Helpers (`deploy/shared/_deploy_common.sh`)

```bash
#!/usr/bin/env bash
# Source this file; do not execute directly.

die() { echo "[$_DEPLOY_TAG] $*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

load_deploy_config() {
  local config_path="$1"; shift
  local -A saved_env
  for var in "$@"; do saved_env[$var]="${!var-}"; done
  if [[ -f "${config_path}" ]]; then source "${config_path}"; fi
  for var in "$@"; do
    if [[ -n "${saved_env[$var]}" ]]; then eval "${var}=\"${saved_env[$var]}\""; fi
  done
}

run_modal_deploy() {
  local name="$1" entrypoint="$2" workdir="${3:-.}"
  local -a cmd=(modal deploy --name "${name}" "${entrypoint}")
  if [[ -n "${MODAL_ENV:-}" ]]; then cmd+=(--env "${MODAL_ENV}"); fi
  echo "[$_DEPLOY_TAG] Deploying Modal app name=${name}"
  ( cd "${workdir}" && "${cmd[@]}" )
}
```

## 6.4 When to Use Which Mode

| Criteria | Core | Edge |
|----------|------|------|
| Simplicity | Simple — one service | Complex — gateway + sandbox |
| User isolation | Shared workspace | Per-user sandbox |
| File system | Shared `/tmp` | Isolated per workspace |
| Terminal/PTY | Shared process | Isolated container |
| Build artifact | Frontend bundle only | Wheel + bundle tarball |
| Auth | Neon or Supabase (optional) | Neon or Supabase (required) |
| Use when | Internal tool, MVP, single-user | Multi-user SaaS product |
