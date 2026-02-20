# Workspace Plugin System for boring-ui

## Context

boring-podcast needs a UI panel and API routes for podcast publishing (YouTube upload, RSS feed, transcript generation). Rather than hardcoding podcast-specific code into boring-ui (a general-purpose web IDE), we need a **workspace plugin system** that lets any workspace contribute custom panels and API routes. The user wants true hot-reload: drop a `.py` or `.jsx` file and have it appear immediately, no restarts, no rebuilds.

boring-ui already has the perfect infrastructure:
- **PaneRegistry** (`src/front/registry/panes.js`) - dynamic panel registration with `register()`
- **RouterRegistry** (`src/back/boring_ui/api/capabilities.py`) - modular router composition
- **CapabilityGate** - panels declare requirements, auto-degrade if unavailable
- `/api/capabilities` - runtime feature discovery the frontend already polls

We just need a **discovery layer** that scans the workspace for plugins and wires them in.

## Convention

Workspace plugins live under `kurt/` in the workspace root (pointed to by `BORING_UI_WORKSPACE_ROOT`):

```
<workspace>/
  kurt/
    api/
      podcast.py          # exports `router` (FastAPI APIRouter)
      analytics.py        # another plugin route module
    panels/
      podcast/
        Panel.jsx          # default export: React component
      analytics/
        Panel.jsx
```

**Backend rule**: Each `kurt/api/<name>.py` must export a `router` variable (FastAPI `APIRouter`). Routes are mounted at `/api/x/<name>/`.

**Frontend rule**: Each `kurt/panels/<name>/Panel.jsx` must default-export a React component. The panel ID becomes `ws-<name>` (prefixed to avoid collisions with core panes).

## Changes

### Part 1: Backend - Workspace Plugin Gateway

**New file: `src/back/boring_ui/api/workspace_plugins.py`**

Core class: `WorkspacePluginManager`
- Scans `{workspace_root}/kurt/api/*.py` for route modules
- Uses `importlib.util.spec_from_file_location()` to load each module
- Builds an inner FastAPI sub-app with each module's `router` mounted at `/{module_name}/`
- Wraps in a **SwitchableApp** ASGI wrapper so the inner app can be swapped without restarting
- Starts a background `watchfiles` watcher on `kurt/api/` and `kurt/panels/`
- On file change: reloads affected module, rebuilds inner app, calls `swap()`
- Also scans `kurt/panels/*/Panel.jsx` to report available frontend panels

Key classes:
```python
class SwitchableApp:
    """ASGI app that delegates to a swappable inner app."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
    def swap(self, new_app):
        self.app = new_app

class WorkspacePluginManager:
    def __init__(self, workspace_root: Path):
        self.api_dir = workspace_root / "kurt" / "api"
        self.panels_dir = workspace_root / "kurt" / "panels"
        self._switchable = SwitchableApp(self._build_app())
        self._start_watcher()

    def get_asgi_app(self) -> SwitchableApp:
        """Mount this on the main app at /api/x"""

    def list_workspace_panes(self) -> list[dict]:
        """Scan kurt/panels/*/Panel.jsx, return [{id, path}]"""

    def _build_app(self) -> FastAPI:
        """Import all kurt/api/*.py modules, mount their routers"""

    def _on_change(self, changes):
        """File watcher callback - rebuild and swap"""
```

**Modified file: `src/back/boring_ui/api/app.py`**

In `create_app()`:
1. Create `WorkspacePluginManager(config.workspace_root)`
2. Mount `manager.get_asgi_app()` at `/api/x` via `app.mount("/api/x", ...)`
3. Extend the capabilities endpoint to include `workspace_panes` from the manager
4. Add a WebSocket endpoint `/ws/plugins` that broadcasts `{type: "plugin_changed"}` when file watcher fires

**Modified file: `src/back/boring_ui/api/capabilities.py`**

Extend `create_capabilities_router()` to accept an optional `workspace_panes` list:
```python
capabilities['workspace_panes'] = [
    {'id': 'ws-podcast', 'name': 'podcast', 'path': 'podcast/Panel.jsx'},
]
```

### Part 2: Frontend - Dynamic Panel Loading

**Modified file: `vite.config.ts`**

Add workspace alias and fs.allow:
```ts
const workspaceRoot = env.BORING_UI_WORKSPACE_ROOT || env.WORKSPACE_ROOT || ''

resolve: {
  alias: {
    '@': path.resolve(__dirname, './src/front'),
    // Only add if workspace root is set
    ...(workspaceRoot ? { '@workspace': path.resolve(workspaceRoot, 'kurt/panels') } : {}),
  },
},
server: {
  fs: {
    allow: ['.', ...(workspaceRoot ? [workspaceRoot] : [])],
  },
  // ... existing proxy config
}
```

**New file: `src/front/workspace/loader.js`**

Dynamic workspace panel loader:
```js
export async function loadWorkspacePanes(workspacePanes) {
  // workspacePanes = [{id: 'ws-podcast', name: 'podcast', path: 'podcast/Panel.jsx'}]
  const loaded = {}
  for (const pane of workspacePanes) {
    try {
      const mod = await import(/* @vite-ignore */ `@workspace/${pane.path}`)
      loaded[pane.id] = mod.default
    } catch (err) {
      console.warn(`[Workspace] Failed to load panel ${pane.id}:`, err)
    }
  }
  return loaded
}
```

**Modified file: `src/front/App.jsx`**

1. Move the `components` map from module-level (line 69) into the App component as state
2. After capabilities load, if `capabilities.workspace_panes` exists:
   - Call `loadWorkspacePanes(capabilities.workspace_panes)`
   - Register each in PaneRegistry: `registerPane({id, component, title, ...})`
   - Rebuild the components map
3. Connect to `/ws/plugins` WebSocket
4. On `plugin_changed` message: refetch capabilities, reload workspace panes

Key change in `App()`:
```jsx
const [workspaceComponents, setWorkspaceComponents] = useState({})

useEffect(() => {
  if (capabilities?.workspace_panes?.length > 0) {
    loadWorkspacePanes(capabilities.workspace_panes).then(loaded => {
      // Register each workspace pane
      for (const [id, component] of Object.entries(loaded)) {
        registerPane({ id, component, title: id.replace('ws-', ''), placement: 'center' })
      }
      setWorkspaceComponents(loaded)
    })
  }
}, [capabilities?.workspace_panes])

// Merge core + workspace components
const allComponents = useMemo(() => ({
  ...getGatedComponents(createCapabilityGatedPane),
  ...workspaceComponents,
}), [workspaceComponents])
```

Pass `allComponents` to `<DockviewReact components={allComponents} .../>`.

**New file: `src/front/hooks/useWorkspacePlugins.js`**

WebSocket hook that connects to `/ws/plugins`, listens for `plugin_changed` events, and calls `capabilities.refetch()` to trigger reload.

### Part 3: boring-podcast Workspace Plugin

**New file: `boring-podcast/kurt/api/podcast.py`**

Move the podcast API routes here. Exports `router` (FastAPI APIRouter) with endpoints:
- `GET /status` - pipeline status for an episode
- `POST /publish` - trigger publish pipeline
- `GET /episodes` - list episodes with metadata

**New file: `boring-podcast/kurt/panels/podcast/Panel.jsx`**

Move the podcast panel UI here. A React component that:
- Lists episodes from `GET /api/x/podcast/episodes`
- Shows publish status per-platform
- Has "Publish" button that calls `POST /api/x/podcast/publish`
- Shows progress for each pipeline step

## Files Summary

| File | Action | In Repo |
|------|--------|---------|
| `src/back/boring_ui/api/workspace_plugins.py` | CREATE | boring-ui |
| `src/back/boring_ui/api/app.py` | MODIFY | boring-ui |
| `src/back/boring_ui/api/capabilities.py` | MODIFY | boring-ui |
| `vite.config.ts` | MODIFY | boring-ui |
| `src/front/workspace/loader.js` | CREATE | boring-ui |
| `src/front/hooks/useWorkspacePlugins.js` | CREATE | boring-ui |
| `src/front/App.jsx` | MODIFY | boring-ui |
| `kurt/api/podcast.py` | CREATE | boring-podcast |
| `kurt/panels/podcast/Panel.jsx` | CREATE | boring-podcast |

## Implementation Order

1. **Backend plugin manager** (`workspace_plugins.py`) - core scanning + SwitchableApp + file watcher
2. **Wire into app.py** - mount at `/api/x`, extend capabilities
3. **Vite config** - add `@workspace` alias + `server.fs.allow`
4. **Frontend loader** - `workspace/loader.js` + `useWorkspacePlugins` hook
5. **App.jsx integration** - dynamic component map, WebSocket reconnect
6. **boring-podcast plugins** - `kurt/api/podcast.py` + `kurt/panels/podcast/Panel.jsx`
7. **Test end-to-end** - start boring-ui pointed at boring-podcast workspace, verify panel appears

## Verification

1. Set `BORING_UI_WORKSPACE_ROOT=/home/ubuntu/projects/boring-podcast`
2. Start boring-ui backend: `uvicorn boring_ui.runtime:app --reload`
3. Start boring-ui frontend: `npm run dev` (with BORING_UI_WORKSPACE_ROOT set)
4. Check `/api/capabilities` returns `workspace_panes: [{id: 'ws-podcast', ...}]`
5. Check `/api/x/podcast/episodes` returns episode list
6. Verify podcast panel appears in Dockview panel list
7. Edit `kurt/api/podcast.py` in boring-podcast - verify API updates without restart
8. Edit `kurt/panels/podcast/Panel.jsx` - verify Vite HMR updates the panel
