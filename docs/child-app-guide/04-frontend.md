# 4. Frontend Integration

[< Back to Index](README.md) | [Prev: Backend](03-backend.md) | [Next: Configuration >](05-configuration.md)

---

## 4.1 Main Entry (`frontend/main.jsx`)

```jsx
// ── Polyfills (must be first) ────────────────────────────────────────────────
// Required for isomorphic-git and other Node-expecting libraries in browser
import { Buffer } from 'buffer'
if (!globalThis.Buffer) globalThis.Buffer = Buffer

if (typeof globalThis.process === 'undefined' || globalThis.process === null) {
  globalThis.process = { env: {} }
} else if (typeof globalThis.process.env === 'undefined') {
  globalThis.process.env = {}
}

// Polyfill crypto.randomUUID for non-secure contexts (HTTP localhost)
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
  crypto.randomUUID = () => {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const h = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
  }
}

// ── Imports ──────────────────────────────────────────────────────────────────
import React from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from '@boring-ui'
import appConfig from './app.config.js'

// Register custom panes (side-effect import)
import './registry.js'

// Import boring-ui styles
import '@boring-ui/styles.css'

// ── Mount ────────────────────────────────────────────────────────────────────
async function bootstrap() {
  const { default: App } = await import('@boring-ui/App')

  function Root() {
    return (
      <ConfigProvider config={appConfig}>
        <App />
      </ConfigProvider>
    )
  }

  createRoot(document.getElementById('root')).render(<Root />)
}

bootstrap()
```

**Why polyfills?** boring-ui uses `isomorphic-git` and `lightning-fs` which expect Node.js globals (`Buffer`, `process`). Without these polyfills, the app crashes in the browser. The `crypto.randomUUID` polyfill is needed when running over HTTP (non-secure context) during local dev.

If your app uses `buffer` or `isomorphic-git`, add them to `package.json` dependencies:
```json
"buffer": "^6.0.3",
"isomorphic-git": "^1.37.2",
"@isomorphic-git/lightning-fs": "^4.6.2"
```

## 4.2 App Config (`frontend/app.config.js`)

Override boring-ui defaults for your app's branding, panels, and features.

```javascript
export default {
  branding: {
    name: 'my-app',
    logo: 'A',   // Single character, React component, or element
    titleFormat: (ctx) =>
      ctx.folder ? `${ctx.folder} — my-app` : 'my-app',
    emptyPanelTitle: 'Welcome',
    emptyPanelMessage: 'Get started by opening a file or using the sidebar',
    emptyPanelHint: 'Cmd+P to search files',
  },

  panels: {
    essential: ['filetree'],
    leftSidebarPanels: ['filetree'],
    defaults: { filetree: 280 },
    min: { filetree: 180, center: 400 },
    collapsed: { filetree: 48 },
  },

  features: {
    gitStatus: true,
    search: true,
    cloudMode: false,
    workflows: false,
    codeSessions: false,
    showHeader: false,
    agentRailMode: 'companion',  // 'companion' | 'pi' | 'all' | 'native'
  },

  // Data backend: 'http' (server filesystem), 'lightningfs' (browser-local),
  // or 'cheerpx' (browser VM). Determines how files are read/written.
  data: {
    backend: 'http',  // Use 'lightningfs' for browser-only mode (no server)
  },

  storage: {
    prefix: 'my-app',
    layoutVersion: 1,  // Increment to force layout reset
  },
}
```

## 4.3 Pane Registry (`frontend/registry.js`)

Register your custom panels and override boring-ui defaults.

```javascript
import { registerPane } from '@boring-ui'
import MyDomainPanel from './panels/MyDomainPanel.jsx'
import MyEmptyPanel from './panels/MyEmptyPanel.jsx'

// Register a domain-specific panel
registerPane({
  id: 'my-domain',
  component: MyDomainPanel,
  title: 'My Domain',
  placement: 'left',        // 'left' | 'center' | 'right' | 'bottom'
  essential: true,           // Must exist in layout
  locked: true,              // Can't close
  hideHeader: true,          // Hide the group header
  constraints: {
    minWidth: 220,
    collapsedWidth: 48,
  },
})

// Override boring-ui's empty panel
registerPane({
  id: 'empty',
  component: MyEmptyPanel,
  title: '',
  placement: 'center',
  essential: false,
  locked: false,
  hideHeader: true,
})

// Override shell pane (make it non-essential for your app)
import ShellTerminalPanel from '@boring-ui/panels/ShellTerminalPanel'
registerPane({
  id: 'shell',
  component: ShellTerminalPanel,
  placement: 'bottom',
  essential: false,
  locked: true,
  constraints: { minHeight: 100, collapsedHeight: 36 },
  requiresRouters: ['pty'],
})
```

## 4.4 Custom Panel Component

```jsx
import { useState, useEffect } from 'react'
import './MyDomainPanel.css'

export default function MyDomainPanel() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/v1/my-domain/items')
      .then(r => r.json())
      .then(data => {
        setItems(data.results || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="my-domain-loading">Loading...</div>

  return (
    <div className="my-domain-panel">
      <h2>My Domain</h2>
      <ul>
        {items.map(item => (
          <li key={item.id}>{item.name}</li>
        ))}
      </ul>
    </div>
  )
}
```

## 4.5 Vite Config (`src/web/vite.config.js`)

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const boringUiRoot = path.resolve(__dirname, '../../interface/boring-ui')
const apiProxyTarget = process.env.BM_WEB_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  // base: './' is required because workspace pages are served behind a
  // path prefix (/w/{id}/...) and root-absolute asset URLs would break.
  base: './',
  plugins: [react()],
  resolve: {
    alias: [
      { find: '@boring-ui', replacement: path.resolve(boringUiRoot, 'src/front') },
    ],
    // Dedupe prevents React version conflicts between your app and boring-ui.
    // Add any shared heavy deps here to avoid duplicate bundles.
    dedupe: [
      'react',
      'react-dom',
      '@tanstack/react-query',
      'buffer',
    ],
  },
  server: {
    proxy: {
      '/api': { target: apiProxyTarget, changeOrigin: false },
      '/auth': { target: apiProxyTarget, changeOrigin: false },
      '/ws': { target: apiProxyTarget, changeOrigin: true, ws: true },
      // Workspace-prefixed paths: /w/{id}/api/* → /api/*
      '^/w/[^/]+/api': {
        target: apiProxyTarget,
        changeOrigin: false,
        rewrite: (p) => p.replace(/^\/w\/[^/]+/, ''),
      },
      '^/w/[^/]+/auth': {
        target: apiProxyTarget,
        changeOrigin: false,
        rewrite: (p) => p.replace(/^\/w\/[^/]+/, ''),
      },
    },
  },
})
```

## 4.6 Available boring-ui Imports

```javascript
// Core framework
import { ConfigProvider, useConfig } from '@boring-ui'
import { registerPane, getPane, listPaneIds } from '@boring-ui'

// App shell
import App from '@boring-ui/App'

// Styles
import '@boring-ui/styles.css'

// Built-in panels (to override or reuse)
import ShellTerminalPanel from '@boring-ui/panels/ShellTerminalPanel'
import FileTreePanel from '@boring-ui/panels/FileTreePanel'
import EditorPanel from '@boring-ui/panels/EditorPanel'

// Data providers (for browser-only mode)
import {
  registerDataProviderFactory,
  createLightningFsProvider,
  createIsomorphicGitProvider,
} from '@boring-ui/providers/data'

// PI Agent config (for in-browser AI)
import { setPiAgentConfig, addPiAgentTools } from '@boring-ui/providers/pi/agentConfig'

// Hooks
import { useCapabilities } from '@boring-ui/hooks/useCapabilities'
import { useTheme } from '@boring-ui/hooks/useTheme'
```

## Pane Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `id` | string | Unique identifier (required) |
| `component` | React.Component | Panel component (required) |
| `title` | string | Default panel title |
| `placement` | string | Default position: `'left'`, `'center'`, `'right'`, `'bottom'` |
| `essential` | boolean | If true, pane must exist in layout |
| `locked` | boolean | If true, prevents closing tabs in group |
| `hideHeader` | boolean | If true, hides the group header |
| `constraints` | object | Size constraints: `minWidth`, `minHeight`, `collapsedWidth`, `collapsedHeight` |
| `requiresFeatures` | string[] | Backend features this pane requires (e.g., `['files']`) |
| `requiresRouters` | string[] | Backend routers this pane requires (e.g., `['pty']`) |
| `requiresAnyFeatures` | string[] | At least one of these features must be enabled |
