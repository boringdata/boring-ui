# boring-ui

A configurable, reusable UI framework for data applications. boring-ui provides production-ready components, flexible layout management, and a comprehensive design token system.

**Key Features:**
- **FileTree** - Configurable file browser with git status integration
- **Editor** - Rich markdown editor with diff support (TipTap-based)
- **Terminal** - Full shell terminal with session management (xterm.js)
- **Chat** - Claude Code-style chat interface
- **Theme System** - Light/dark mode with customizable design tokens
- **Layout Management** - Flexible dock-style panel arrangement
- **Config-Driven** - Fully customizable via `app.config.js`

## Quick Start

### Installation

Copy the boring-ui folder into your project and install dependencies:

```bash
npm install
```

### Basic Setup

Create an `app.config.js` file in your project root:

```javascript
// app.config.js
export default {
  branding: {
    name: 'My Data App',
    logo: 'M',
    titleFormat: (ctx) => ctx.workspace ? `${ctx.workspace} - My App` : 'My App',
  },

  fileTree: {
    sections: [
      { key: 'documents', label: 'Documents', icon: 'FileText' },
      { key: 'queries', label: 'Queries', icon: 'Search' },
    ],
    configFiles: ['*.config.yaml', 'app.toml'],
  },

  storage: {
    prefix: 'myapp',
  },

  styles: {
    light: { accent: '#3b82f6' },
    dark: { accent: '#60a5fa' },
  },
}
```

### Running the App

```bash
npm run dev
```

The app will start at `http://localhost:5173` with your configuration.

## Configuration API

All aspects of boring-ui are configurable through `app.config.js`. The configuration object supports the following sections:

### Branding

Customize app appearance and branding:

```javascript
branding: {
  // App name shown in header
  name: 'My App',

  // Logo: string character, React component, or element
  logo: 'M',                    // Character
  // logo: <MyLogo />,          // Component
  // logo: () => <MyLogo />,    // Function component

  // Function to format document title
  titleFormat: (context) => {
    // context: { folder?: string, workspace?: string }
    return context.workspace ? `${context.workspace} - My App` : 'My App'
  },
}
```

### FileTree

Configure the file browser panel:

```javascript
fileTree: {
  // Sections to display (each maps to an API endpoint path)
  sections: [
    {
      key: 'documents',
      label: 'Documents',
      icon: 'FileText',  // Lucide icon name
    },
    {
      key: 'queries',
      label: 'Queries',
      icon: 'Search',
    },
  ],

  // Files to show at top with special icon
  // Supports exact matches and glob patterns
  configFiles: ['*.config', 'app.toml', 'README.md'],

  // Git status polling interval (ms)
  gitPollInterval: 5000,

  // File tree refresh polling interval (ms)
  treePollInterval: 3000,
}
```

### Storage

Configure localStorage behavior:

```javascript
storage: {
  // Prefix for all storage keys (recommended: app acronym)
  prefix: 'myapp',

  // Storage layout version for cache busting
  layoutVersion: 1,

  // Legacy key migration map (for app updates)
  migrateLegacyKeys: {
    'old-layout-key': 'layout',
    'old-theme-key': 'theme',
  },
}
```

### Panels

Configure panel layout defaults:

```javascript
panels: {
  // Which panels to always show
  essential: ['filetree', 'terminal'],

  // Default sizes when visible
  defaults: {
    filetree: 280,   // pixels
    terminal: 400,
  },

  // Minimum sizes when dragging
  min: {
    filetree: 180,
    terminal: 250,
  },

  // Size when collapsed
  collapsed: {
    filetree: 48,
    terminal: 48,
  },
}
```

### API

Configure backend API:

```javascript
api: {
  // Base URL for API requests
  baseURL: process.env.VITE_API_URL || '',
}
```

### Features

Enable/disable features:

```javascript
features: {
  // Git status integration in file tree
  gitStatus: true,

  // File search functionality
  search: true,

  // Cloud/workspace mode
  cloudMode: true,

  // Workflow management features
  workflows: false,
}
```

### Styles

Customize design tokens at runtime:

```javascript
styles: {
  // Light mode token overrides
  light: {
    accent: '#8b5cf6',
    accentHover: '#7c3aed',
    accentLight: '#f3e8ff',
    bgPrimary: '#ffffff',
    textPrimary: '#111827',
    // ... other color tokens
  },

  // Dark mode token overrides
  dark: {
    accent: '#a78bfa',
    accentHover: '#c4b5fd',
    accentLight: '#6d28d9',
    bgPrimary: '#0f0f0f',
    textPrimary: '#fafafa',
    // ... other color tokens
  },
}
```

## Component Guide

### Core Components

#### Header

Application header with branding and controls.

```jsx
import Header from './components/Header'

<Header
  userContext={{
    is_cloud_mode: true,
    user: { email: 'user@example.com' },
    workspace: { name: 'My Workspace' },
  }}
  projectRoot="/path/to/project"
/>
```

**Features:**
- Configurable logo (string, component, or element)
- Dynamic title formatting via config
- Theme toggle button
- User menu (when in cloud mode)

#### FileTree

Configurable file browser with git integration.

```jsx
import FileTree from './components/FileTree'

<FileTree
  onOpen={(path) => console.log('Open:', path)}
  onOpenToSide={(path) => console.log('Open to side:', path)}
  onFileDeleted={(path) => console.log('Deleted:', path)}
  onFileRenamed={(oldPath, newPath) => console.log('Renamed:', oldPath, newPath)}
  onFileMoved={(oldPath, newPath) => console.log('Moved:', oldPath, newPath)}
  projectRoot="/home/user/my-project"
  activeFile="src/App.jsx"
/>
```

**Features:**
- Organized file sections based on config
- Git status badges for modified/added/deleted files
- Drag-and-drop file moving
- Context menu (rename, delete, copy path)
- File search
- Create new files

#### Editor

Rich markdown editor with diff support.

```jsx
import Editor from './components/Editor'

<Editor
  content={fileContent}
  contentVersion={version}
  isDirty={hasUnsavedChanges}
  isSaving={isSavingToServer}
  onChange={(newContent) => handleChange(newContent)}
  onAutoSave={(content) => handleAutoSave(content)}
  showDiffToggle={true}
  editorMode="rendered"  // 'rendered' | 'diff' | 'git-diff'
  originalContent={gitHeadContent}
/>
```

**Modes:**
- `rendered` - Normal editing
- `diff` - Inline diff highlighting
- `git-diff` - Read-only diff view

**Features:**
- TipTap-based rich text editing
- Markdown support with syntax highlighting
- Frontmatter editor
- Inline git diff visualization
- Word-level diff highlighting
- Auto-save with configurable delay

#### Terminal

Shell terminal with session management.

```jsx
import { Terminal } from './components/Terminal'

<Terminal
  sessionId="session-123"
  onSessionChange={(newId) => setSessionId(newId)}
/>
```

**Features:**
- xterm.js-based terminal emulation
- Session persistence
- Copy/paste support
- Resizable interface

#### ThemeToggle

Light/dark theme switcher button.

```jsx
import ThemeToggle from './components/ThemeToggle'

// Standalone mode (manages own state)
<ThemeToggle />

// Controlled mode
<ThemeToggle
  theme={currentTheme}
  onToggle={() => toggleTheme()}
  onChange={(newTheme) => setTheme(newTheme)}
  customIcons={{
    light: <Sun size={16} />,
    dark: <Moon size={16} />,
  }}
/>
```

#### UserMenu

User avatar with dropdown menu.

```jsx
import UserMenu from './components/UserMenu'

<UserMenu
  email="user@example.com"
  workspaceName="My Workspace"
  workspaceId="workspace-123"
  onLogout={() => handleLogout()}
/>
```

## Customization

### Custom Accent Colors

Change the primary accent color without modifying CSS:

```javascript
// app.config.js
export default {
  styles: {
    light: {
      accent: '#8b5cf6',        // Purple
      accentHover: '#7c3aed',
      accentLight: '#f3e8ff',
    },
    dark: {
      accent: '#a78bfa',
      accentHover: '#c4b5fd',
    },
  },
}
```

### Custom File Sections

Organize files into custom sections:

```javascript
// app.config.js
fileTree: {
  sections: [
    { key: 'dashboards', label: 'Dashboards', icon: 'LayoutDashboard' },
    { key: 'models', label: 'Models', icon: 'Database' },
    { key: 'profiles', label: 'Profiles', icon: 'Users' },
  ],
}
```

The `key` should match a path returned by your API's `/api/config` endpoint.

### Custom Storage Prefix

Each app instance uses a unique storage prefix to avoid conflicts:

```javascript
// app.config.js
storage: {
  prefix: 'myapp',  // Keys like: myapp-layout, myapp-theme, etc.
}
```

### Custom CSS

Override any design token by adding CSS:

```css
:root {
  --color-accent: #your-color;
  --font-sans: 'Your Font', sans-serif;
}
```

All components use CSS custom properties, so changes propagate everywhere.

## Advanced Configuration

### Title Formatting

The `titleFormat` function receives context about the current workspace/folder:

```javascript
titleFormat: (ctx) => {
  const parts = []
  if (ctx.folder) parts.push(ctx.folder)
  if (ctx.workspace) parts.push(ctx.workspace)
  parts.push('My App')
  return parts.join(' - ')
}
```

### Legacy Key Migration

If you rename storage keys, automatically migrate old data:

```javascript
storage: {
  prefix: 'myapp-v2',
  migrateLegacyKeys: {
    'old-layout-key': 'layout',
    'old-sidebar-state': 'sidebar-collapsed',
  },
}
```

This will automatically move data from `myapp-v1-old-layout-key` to `myapp-v2-layout` on first load.

### Dynamic Configuration

Load configuration from environment or API:

```javascript
// main.jsx
import config from './app.config.js'

// Override from environment
const finalConfig = {
  ...config,
  branding: {
    ...config.branding,
    name: process.env.VITE_APP_NAME,
  },
  storage: {
    ...config.storage,
    prefix: process.env.VITE_STORAGE_PREFIX,
  },
}

// Pass to ConfigProvider
```

## API Integration

boring-ui expects a backend API with these endpoints:

### GET /api/config

Returns project configuration with section paths:

```json
{
  "paths": {
    "documents": "documents",
    "queries": "queries"
  }
}
```

### GET /api/tree?path={dir}

Returns directory contents:

```json
{
  "entries": [
    {
      "path": "src/App.jsx",
      "name": "App.jsx",
      "is_dir": false
    }
  ]
}
```

### GET /api/git/status

Returns git file status:

```json
{
  "available": true,
  "files": {
    "src/App.jsx": "M",
    "src/utils/api.js": "A"
  }
}
```

### GET /api/file?path={file}

Get file contents (handled by parent app).

### PUT /api/file?path={file}

Save file contents.

### POST /api/file/rename

Rename a file:

```json
{
  "old_path": "old.txt",
  "new_path": "new.txt"
}
```

### POST /api/file/move

Move a file:

```json
{
  "src_path": "file.txt",
  "dest_dir": "target/"
}
```

### DELETE /api/file?path={file}

Delete a file.

## Testing

### Unit Tests

Run unit tests with Vitest:

```bash
npm test                  # Watch mode
npm run test:run         # Single run
npm run test:coverage    # With coverage
npm run test:ui          # UI mode
```

Tests are located in `src/front/__tests__/`:
- `components/` - Component unit tests
- `utils/` - Utility function tests
- `integration/` - Integration tests

### E2E Tests

Run end-to-end tests with Playwright (requires installation):

```bash
npm install -D @playwright/test
npm run test:e2e          # Run tests
npm run test:e2e:ui       # UI mode
npm run test:e2e:debug    # Debug mode
```

E2E tests are in `src/front/__tests__/e2e/` and cover:
- Theme persistence
- Storage integration
- User interactions
- Accessibility

## Development

### Project Structure

```
boring-ui/
├── src/
│   ├── front/           # Frontend React app
│   │   ├── components/  # React components
│   │   ├── panels/      # Dockview panel components
│   │   ├── hooks/       # Custom hooks
│   │   ├── config/      # Configuration system
│   │   ├── registry/    # Pane registry
│   │   ├── layout/      # Layout persistence
│   │   ├── utils/       # Utility functions
│   │   ├── __tests__/   # Unit and E2E tests
│   │   ├── main.jsx     # App entry point
│   │   ├── App.jsx      # Root component
│   │   └── index.js     # Public API exports
│   └── back/            # Backend Python API
│       └── boring_ui/   # Python package
│           └── api/     # FastAPI routers and modules
├── examples/            # Example app configurations
├── docs/                # Documentation
├── app.config.js        # Your app configuration
├── package.json
└── vite.config.ts       # Vite configuration
```

### Building

Create an optimized production build:

```bash
npm run build
npm run preview  # Test production build locally
```

### Code Quality

Check code style:

```bash
npm run lint
```

## Troubleshooting

### Components Not Rendering

**Problem:** FileTree or Editor shows blank

**Solution:**
1. Check that your API endpoints are working (`/api/tree`, `/api/config`)
2. Verify `VITE_API_URL` environment variable is set correctly
3. Check browser console for errors

### Theme Not Persisting

**Problem:** Theme resets on page reload

**Solution:**
1. Verify storage prefix is configured: `storage: { prefix: 'myapp' }`
2. Check localStorage is enabled in browser
3. Verify theme toggle has `storage` utility integrated

### File Tree Shows No Sections

**Problem:** File sections not appearing

**Solution:**
1. Verify your `/api/config` endpoint returns the correct paths
2. Ensure `fileTree.sections` keys match the API response keys
3. Check that section folders exist in your project

### Custom Styles Not Applied

**Problem:** Custom accent colors not working

**Solution:**
1. Verify `styles` config is at root level of `app.config.js`
2. Check that StyleProvider is wrapping your app in `main.jsx`
3. Try a dark color like `#8b5cf6` to ensure it's visible
4. Inspect `--color-accent` CSS variable in DevTools

### Tests Failing

**Problem:** Unit tests not passing

**Solution:**
1. Clear node_modules: `rm -rf node_modules && npm install`
2. Run single test file: `npm test storage.test.ts`
3. Check mock setup in `src/front/__tests__/setup.ts`

## Examples

The `examples/` directory contains two complete app configurations:

- **boring-bi** - Business intelligence dashboard with purple accent
- **kurt-core** - Workflow management app with blue accent

Use these as templates for your own apps.

## Extensibility

boring-ui is designed for extensibility. See the [Extension Guide](docs/EXTENSION_GUIDE.md) for:

- **Pane Registry** - Register custom panel components
- **Layout Manager** - Customize layout persistence
- **App Config** - Configure branding and features
- **Capabilities API** - Discover available features

## License

MIT

## Contributing

Contributions welcome! Please:
1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Create a pull request

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review example configurations
3. Open an issue on GitHub
4. Check API integration requirements

---

**boring-ui** - Simple, configurable, production-ready UI framework for data applications.
