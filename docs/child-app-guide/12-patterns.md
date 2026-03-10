# 12. Common Patterns

[< Back to Index](README.md) | [Prev: Checklist](11-checklist.md)

---

## 12.1 Patching `/api/capabilities`

Use middleware to inject domain-specific flags that the frontend reads:

```python
@app.middleware("http")
async def patch_capabilities(request, call_next):
    response = await call_next(request)
    if request.url.path == "/api/capabilities" and response.status_code == 200:
        import json
        body = b""
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else chunk.encode()
        data = json.loads(body)
        data.setdefault("features", {})["my_domain"] = True
        # Optionally inline data for instant UI rendering:
        # data["my_domain_seed"] = {"items": cached_items}
        from fastapi.responses import JSONResponse
        return JSONResponse(content=data)
    return response
```

boring-macro also patches `/api/config` to add file tree section routing. You can patch any boring-ui response this way.

## 12.2 Multi-Mode Frontend (Browser vs Sandbox)

If your app supports both browser-only (PI agent, LightningFS) and sandbox (companion, server files) modes:

```javascript
// mode.js
export const macroMode = (import.meta.env.VITE_MACRO_MODE || 'frontend').toLowerCase()
export const isFrontendMode = macroMode === 'frontend'
export const isSandboxMode = macroMode === 'sandbox'
```

```javascript
// app.config.js
import { isFrontendMode } from './mode.js'

const base = {
  branding: { name: 'my-app', logo: 'A' },
  // ... shared config
}

export const frontendConfig = {
  ...base,
  features: { ...base.features, agentRailMode: 'pi' },
  data: { backend: 'lightningfs' },
  storage: { prefix: 'my-app-frontend', layoutVersion: 1 },
}

export const sandboxConfig = {
  ...base,
  features: { ...base.features, agentRailMode: 'companion' },
  storage: { prefix: 'my-app-sandbox', layoutVersion: 1 },
}

export default isFrontendMode ? frontendConfig : sandboxConfig
```

Build modes:
```json
{
  "scripts": {
    "dev": "VITE_MACRO_MODE=frontend vite --host 0.0.0.0",
    "dev:sandbox": "VITE_MACRO_MODE=sandbox vite --host 0.0.0.0",
    "build": "VITE_MACRO_MODE=frontend vite build",
    "build:sandbox": "VITE_MACRO_MODE=sandbox vite build"
  }
}
```

## 12.3 Auth Redirect on Root

Force unauthenticated users to the login page:

```python
# In config
auth_redirect_on_root = env_bool(os.environ.get("MY_APP_AUTH_REDIRECT_ON_ROOT"), False)

# In app.py (register BEFORE dev-session middleware)
if cfg.auth_redirect_on_root:
    @app.middleware("http")
    async def redirect_unauthed_root(request, call_next):
        if request.method == "GET" and request.url.path == "/":
            token = request.cookies.get("boring_session", "")
            if not _has_valid_session(token):
                return RedirectResponse(url="/auth/login?redirect_uri=%2F")
        return await call_next(request)
```

Note: Starlette runs the **last-registered** middleware first. Register redirect (inner) first, then dev-session (outer) so dev-session injection happens before the redirect check.

## 12.4 Dev Auto-Session

Auto-create a dev session cookie so you don't need to log in during local dev:

```python
# Set env vars:
# BM_DEV_AUTO_SESSION=true
# BM_DEV_SESSION_USER_ID=local-dev
# BM_DEV_SESSION_EMAIL=dev@example.com
```

This is implemented in boring-macro's `app.py` — you can copy the `_bootstrap_local_control_plane_session` middleware. It:
1. Checks if the current request has a valid session cookie
2. If not, creates one using boring-ui's `create_session_cookie()`
3. Injects it into both the request scope and the response

## 12.5 WebSocket Bridges

If your domain needs real-time updates, add a WebSocket endpoint:

```python
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

@app.websocket("/ws/my-domain/updates")
async def domain_updates(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            # Process and respond
            await ws.send_text('{"type": "ack"}')
    except WebSocketDisconnect:
        pass
```

For PubSub patterns, see boring-macro's `modules/data/ws.py` which implements a `TabBus` for broadcasting tab state changes.

## 12.6 Ownership Rules for Vertical Apps

Keep workspace APIs in boring-ui core:
- `/auth/*` — authentication
- `/api/v1/me*` — user profile
- `/api/v1/workspaces*` — workspace CRUD
- `/api/v1/files/*` — file operations
- `/api/v1/git/*` — git operations

Add your domain routes under a namespace:
- `/api/v1/my-domain/*` — your domain endpoints

Never shadow boring-ui routes. Never modify boring-ui's source — always extend via middleware or post-hoc router mounting.

## 12.7 Inlining Seed Data in Capabilities

For instant UI rendering, inline cached data in the `/api/capabilities` response:

```python
# In your capabilities patch middleware
if has_domain_data:
    try:
        data["my_domain_catalog"] = domain_service.get_catalog_cached()
    except Exception:
        data["my_domain_catalog"] = {"results": [], "total": 0}
```

The frontend reads this from the capabilities response and renders immediately, without a second API call:

```javascript
const { capabilities } = useCapabilities()
const seedData = capabilities?.my_domain_catalog
```

## 12.8 Mode-Dependent Panel Components

Register different components for the same panel ID based on runtime mode:

```javascript
import { isFrontendMode } from './mode.js'

registerPane({
  id: 'companion',
  component: isFrontendMode ? PiAgentPanel : CompanionAuthPanel,
  title: isFrontendMode ? 'PI Agent' : 'Agent',
  placement: 'right',
  requiresAnyFeatures: ['companion', 'pi'],
})
```
