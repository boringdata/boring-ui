# Deployment Matrix

Document what environment variables and configuration paths are relevant for the supported runtime modes so filesystem selection can be treated as a parameter that only reroutes where the file/git endpoints run.

## Modes

| Mode | Description | Primary API(s) | Filesystem target | Enabled routers |
| --- | --- | --- | --- | --- |
| `local` | Single FastAPI process runs file/git/pty/stream/approval/sandbox directly inside the configured workspace. | `boring-ui API` (`src/back/boring_ui/api/app.py`). | `WORKSPACE_ROOT` – local path. | All routers from `create_app` (files, git, pty, stream, sandbox, companion). |
| `hosted` | Control plane exposed to browsers; serves canonical `/api/v1/*` privileged operations backed by a private sandbox service. | `boring-ui API` (public) + `local_api` data plane (`python -m boring_ui.api.local_api`). | `WORKSPACE_ROOT` for the sandbox internal API (private). Frontend sees `FILESYSTEM_SOURCE` metadata but never directly hits this workspace. | Public routers limited to canonical control-plane surfaces (approval, capabilities, canonical `/api/v1/*`). |
| `sprites` | Hosted mode with `SANDBOX_PROVIDER=sprites`; the sandbox data plane runs inside Sprites.dev, but the control plane still targets the workspace that the sprite exposes. | Same as `hosted`, plus the Sprites provider for sandbox-agent (`src/back/boring_ui/api/modules/sandbox/providers/sprites.py`). | The sprite’s `/home/sprite/workspace` (pointed to by the Sprites sandbox). | Same as hosted plus the sandbox capability published once `SandboxManager` is started. |

## Environment variable matrix (key pieces only)

| Env var | Mode | Required? | Purpose | Notes |
| --- | --- | --- | --- | --- |
| `BORING_UI_RUN_MODE` | local/hosted | **REQUIRED** | Switches app between direct-mode and control-plane proxy logic (`APIConfig.run_mode`). | Local mode mounts `files`/`git` routers directly; hosted mode relies on `local_api` plus `hosted_proxy`. |
| `WORKSPACE_ROOT` | all | **REQUIRED** | Sets the workspace path for whichever API instance is running (local app or internal sandbox). | `create_app` defaults to `Path.cwd()`; `create_local_api_app` uses this to drive file/git/exec endpoints. |
| `FILESYSTEM_SOURCE` | UI | optional | Metadata returned by `/api/capabilities`; frontend displays whether files come from `local`, `sandbox`, or `sprites`. | Defaults to `local`. Doesn't change routing, only informs `FilesystemIndicator` and capability gating. |
| `SANDBOX_PROVIDER` | sandbox-enabled | optional | Chooses `local`, `sprites`, or other sandbox-agent implementations (`create_provider`). | Defaults to `local`. Uses `LocalProvider`; `sprites` uses a SpritesClient with credentials. |
| `SANDBOX_WORKSPACE` | sandbox-enabled | optional | Workspace path for sandbox-agent (local provider). | Defaults to `WORKSPACE_ROOT`. Points the private API to the correct filesystem. |
| `SANDBOX_RUN_MODE` | sandbox-enabled | optional | Passed to sandbox provider so it binds appropriately. | Set automatically by `create_app` based on `BORING_UI_RUN_MODE`. `LocalProvider` treats `hosted` as `0.0.0.0`, otherwise `127.0.0.1`. |
| `CAPABILITY_PRIVATE_KEY` | hosted | **REQUIRED** (hosted only) | Enables the hosted API to issue capability tokens for canonical hosted `/api/v1/*` operations. | Without this, hosted privileged routes are disabled (logged as warning). |
| `SERVICE_PRIVATE_KEY` | hosted | optional | Signs service requests from control plane to sandbox (mutual auth). | Set automatically if not provided. |
| `INTERNAL_SANDBOX_URL` | hosted | optional | How the hosted control plane reaches the private internal API. | Defaults to `http://127.0.0.1:2469`. Change for remote sandbox. |
| `EXTERNAL_HOST` | all | optional | Hostname for service registry URLs so frontends can reach sandbox/companion services. | Defaults to `127.0.0.1`. Set to public hostname for remote deployments. |
| `COMPANION_PORT` | companion-enabled | optional | Port for Companion server. | Defaults to `3456`. |
| `COMPANION_WORKSPACE` | companion-enabled | optional | Workspace path for Companion server. | Defaults to `WORKSPACE_ROOT`. |
| `COMPANION_RUN_MODE` | companion-enabled | optional | Bind mode for Companion server. | Set automatically by `create_app`. |

## Filesystem parameter semantics

- The backend treats `WORKSPACE_ROOT` (and, for sandbox providers, `SANDBOX_WORKSPACE`) as the source of truth for file/git/exec endpoints. Pointing those env vars at different directories (local path vs Sprites workspace) is how the filesystem parameter reroutes the implementation.
- `APIConfig.filesystem_source` simply tags the `/api/capabilities` response so the frontend can display the proper indicator. `FilesystemIndicator` and capability-aware components read this value but do not change API routing logic.
- If you need to switch the entire stack to a different filesystem, you update `WORKSPACE_ROOT`/`SANDBOX_WORKSPACE` (and optionally `FILESYSTEM_SOURCE`) before starting the relevant process.

## Binding logic and host selection

- `CompanionProvider._build_env` and `LocalProvider.create` rely on the `run_mode` config (`COMPANION_RUN_MODE`, `SANDBOX_RUN_MODE`) to decide whether to bind to `127.0.0.1` (local) or `0.0.0.0` (hosted). That central `run_mode` value is the single source of truth for transport bindings, so there’s no need to scatter multiple `*_HOST` env vars. See `src/back/boring_ui/api/modules/companion/provider.py` and `src/back/boring_ui/api/modules/sandbox/providers/local.py` for details.
- `external_host` (set via `EXTERNAL_HOST` or default) is the hostname the frontend writes into service registry entries under `/api/capabilities` so direct-connect consumers (sandbox/companion) know which URL to use. This is distinct from the bind interface but ensures the frontends learn the correct host even if the service binds to `0.0.0.0`.
- Hosted deployments should keep `SANDBOX_RUN_MODE=hosted` and `COMPANION_RUN_MODE=hosted` (set by `create_app` when `run_mode.value == 'hosted'`), so all subprocesses already read the same host policy as the control plane.

## Quick-start: Copy-paste examples

### LOCAL mode (development, all services local)
```bash
# Terminal 1: Backend
export BORING_UI_RUN_MODE=local
export WORKSPACE_ROOT=$(pwd)
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# Terminal 2: Frontend
npx vite --host 0.0.0.0 --port 5173
```

### HOSTED mode (control plane local, sandbox private/remote)
```bash
# Terminal 1: Remote sandbox (internal API only)
export WORKSPACE_ROOT=/remote/workspace
export INTERNAL_API_PORT=2469
python3 -c "
from boring_ui.api.modules.sandbox.internal_api import create_internal_sandbox_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(create_internal_sandbox_router(Path('/remote/workspace')))
uvicorn.run(app, host='0.0.0.0', port=2469)
"

# Terminal 2: Local backend (control plane + proxy)
export BORING_UI_RUN_MODE=hosted
export WORKSPACE_ROOT=$(pwd)
export INTERNAL_SANDBOX_URL=http://REMOTE_IP:2469
export CAPABILITY_PRIVATE_KEY="$(openssl rand -hex 32)"
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app()
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# Terminal 3: Local frontend
npx vite --host 0.0.0.0 --port 5173
```

### SPRITES mode (sandbox-agent on Sprites.dev VM)
```bash
# On Sprites.dev VM: Start sandbox-agent
export WORKSPACE_ROOT=/home/sprite/workspace
export SANDBOX_PROVIDER=local
python3 -m @sandbox-agent/cli --port 2468 --token $(openssl rand -hex 16)

# Local: Backend pointing to Sprites sandbox
export BORING_UI_RUN_MODE=hosted
export WORKSPACE_ROOT=$(pwd)
export SANDBOX_PROVIDER=sprites
export SPRITES_SANDBOX_URL=https://sprites.dev/sandbox
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app()
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# Local: Frontend
npx vite --host 0.0.0.0 --port 5173
```

## Troubleshooting common mistakes

| Symptom | Cause | Fix |
| --- | --- | --- |
| "`hosted mode running without CAPABILITY_PRIVATE_KEY`" warning | `BORING_UI_RUN_MODE=hosted` but no `CAPABILITY_PRIVATE_KEY` set | Generate key: `export CAPABILITY_PRIVATE_KEY="$(openssl rand -hex 32)"` and restart backend. |
| Sandbox proxy routes return 502 Bad Gateway | `INTERNAL_SANDBOX_URL` unreachable or wrong port | Check remote is running on correct port (default 2469) and IP is accessible. Test: `curl http://REMOTE_IP:2469/internal/health` |
| Frontend shows "sandbox unavailable" but backend started OK | `SANDBOX_RUN_MODE=hosted` but services still bind to `127.0.0.1` | Ensure `EXTERNAL_HOST` is set to public hostname. Services will still bind to `0.0.0.0` but advertise correct URL to frontend. |
| File operations work locally but fail in remote sandbox | `WORKSPACE_ROOT` on local backend != `WORKSPACE_ROOT` on remote sandbox | Verify both machines have consistent workspace paths (or intentionally different if using different filesystems). |

## Summary

Treating "filesystem" as a parameter means wiring the workspace env vars (`WORKSPACE_ROOT`, `SANDBOX_WORKSPACE`) to the private file/git endpoints and surfacing the resulting source via `FILESYSTEM_SOURCE`. The matrix above captures how each mode sets those env vars, and the binding logic section explains why existing `*_RUN_MODE` values are the root of truth for binding, making the control-plane bindings predictable without additional host-specific env vars.
