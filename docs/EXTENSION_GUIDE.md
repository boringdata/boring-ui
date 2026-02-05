# Extension Guide

This guide covers boring-ui's extension points for adding custom panels, routers, and configurations.

## Overview

boring-ui provides four main extension points:

1. **Pane Registry** - Register custom panel components for the UI
2. **Layout Manager** - Customize layout persistence and restoration
3. **App Config** - Configure branding, storage, and features
4. **Capabilities API** - Discover available features at runtime

## Pane Registry

The pane registry (`src/front/registry/panes.js`) manages panel components for the Dockview layout.

### Using the Registry

```javascript
import {
  registerPane,
  getPane,
  listPaneIds,
  essentialPanes,
  getComponents,
} from './registry/panes'

// Get all registered pane IDs
const paneIds = listPaneIds()
// => ['filetree', 'editor', 'terminal', 'shell', 'empty', 'review']

// Get essential panes (must exist in layout)
const essentials = essentialPanes()
// => ['filetree', 'terminal', 'shell']

// Get components map for Dockview
const components = getComponents()
// => { filetree: FileTreePanel, editor: EditorPanel, ... }
```

### Registering a Custom Pane

```javascript
import { registerPane } from './registry/panes'
import MyCustomPanel from './panels/MyCustomPanel'

registerPane({
  id: 'my-custom',
  component: MyCustomPanel,
  title: 'My Panel',
  placement: 'center',  // 'left' | 'center' | 'right' | 'bottom'
  essential: false,     // If true, must exist in layout
  locked: false,        // If true, group is locked (no close button)
  hideHeader: false,    // If true, group header is hidden
  constraints: {
    minWidth: 200,      // Minimum width in pixels
    minHeight: 150,     // Minimum height in pixels
  },
})
```

### Pane Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `id` | string | Unique identifier (required) |
| `component` | React.Component | Panel component (required) |
| `title` | string | Default panel title |
| `placement` | string | Default position: 'left', 'center', 'right', 'bottom' |
| `essential` | boolean | If true, pane must exist in layout |
| `locked` | boolean | If true, prevents closing tabs in group |
| `hideHeader` | boolean | If true, hides the group header |
| `constraints` | object | Size constraints: `minWidth`, `minHeight`, etc. |

## Layout Manager

The layout manager (`src/front/layout/LayoutManager.js`) handles layout persistence.

### Storage Functions

```javascript
import {
  loadLayout,
  saveLayout,
  loadCollapsedState,
  saveCollapsedState,
  loadPanelSizes,
  savePanelSizes,
  getStorageKey,
} from './layout/LayoutManager'

// Load saved layout
const storagePrefix = 'my-app'
const projectRoot = '/path/to/project'
const layout = loadLayout(storagePrefix, projectRoot)

// Save layout
saveLayout(storagePrefix, projectRoot, dockApi.toJSON())

// Load/save collapsed state
const collapsed = loadCollapsedState(storagePrefix)
saveCollapsedState({ filetree: true, terminal: false }, storagePrefix)

// Load/save panel sizes
const sizes = loadPanelSizes(storagePrefix)
savePanelSizes({ filetree: 300, terminal: 400 }, storagePrefix)
```

### Layout Validation

```javascript
import { validateLayoutStructure, checkForSavedLayout } from './layout/LayoutManager'

// Check if a saved layout exists
const { hasSaved, invalidFound } = checkForSavedLayout('my-app')

// Validate layout structure
const isValid = validateLayoutStructure(layout)
```

## App Config

Configure boring-ui via `app.config.js` in your project root.

### Configuration Options

```javascript
// app.config.js
export default {
  // App branding
  branding: {
    name: 'My App',
    logo: 'M',  // String, React component, or element
    titleFormat: (ctx) => `${ctx.folder} - My App`,
  },

  // LocalStorage configuration
  storage: {
    prefix: 'my-app',      // Storage key prefix
    layoutVersion: 1,      // Increment to force layout reset
  },

  // Panel configuration
  panels: {
    essential: ['filetree', 'terminal', 'shell'],
    defaults: { filetree: 280, terminal: 400, shell: 250 },
    min: { filetree: 180, terminal: 250, shell: 100 },
    collapsed: { filetree: 48, terminal: 48, shell: 36 },
  },

  // Feature flags
  features: {
    gitStatus: true,
    search: true,
    cloudMode: false,
  },

  // Design tokens (CSS variables)
  styles: {
    light: { accent: '#3b82f6', accentHover: '#2563eb' },
    dark: { accent: '#60a5fa', accentHover: '#93c5fd' },
  },
}
```

### Using Config in Components

```javascript
import { useConfig } from './config'

function MyComponent() {
  const config = useConfig()

  return (
    <div>
      <h1>{config.branding.name}</h1>
      <span>{config.storage.prefix}</span>
    </div>
  )
}
```

## Backend Router Registry

Add custom routers to the backend API.

### Adding a Router

```python
from boring_ui.api import create_app, RouterRegistry, create_default_registry

# Create custom registry
registry = create_default_registry()

# Register a custom router
registry.register(
    name='my-feature',
    prefix='/api/my-feature',
    factory=create_my_feature_router,
    description='My custom feature endpoints',
    tags=['custom'],
)

# Create app with custom registry
app = create_app(registry=registry)
```

### Router Factory Pattern

```python
from fastapi import APIRouter

def create_my_feature_router(config):
    """Create router for my feature."""
    router = APIRouter(tags=['my-feature'])

    @router.get('/items')
    async def list_items():
        return {'items': []}

    @router.post('/items')
    async def create_item(data: dict):
        return {'id': '123', **data}

    return router
```

### Selective Router Inclusion

```python
# Include only specific routers
app = create_app(routers=['files', 'git', 'my-feature'])

# Or exclude optional routers
app = create_app(include_pty=False, include_stream=False)
```

## Capabilities API

The `/api/capabilities` endpoint reports available features.

### Response Format

```json
{
  "version": "0.1.0",
  "features": {
    "files": true,
    "git": true,
    "pty": true,
    "stream": true,
    "approval": true
  },
  "routers": [
    {
      "name": "files",
      "prefix": "/api",
      "description": "File system operations",
      "tags": ["files"],
      "enabled": true
    }
  ]
}
```

### Using Capabilities in Frontend

```javascript
async function checkCapabilities() {
  const response = await fetch('/api/capabilities')
  const { features, routers } = await response.json()

  if (features.pty) {
    // Enable terminal features
  }

  if (features.approval) {
    // Enable approval workflow
  }
}
```

## Best Practices

1. **Pane IDs**: Use lowercase, hyphenated IDs (e.g., `my-custom-panel`)
2. **Storage Prefix**: Use a unique prefix to avoid conflicts with other apps
3. **Essential Panes**: Only mark panes as essential if they're truly required
4. **Router Tags**: Use consistent tags for OpenAPI documentation
5. **Feature Flags**: Check capabilities before using optional features
6. **Layout Version**: Increment when making breaking layout changes

## See Also

- [README.md](../README.md) - Quick start guide
- [tests/unit/test_capabilities.py](../tests/unit/test_capabilities.py) - API test examples
