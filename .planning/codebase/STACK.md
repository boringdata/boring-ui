# Technology Stack

## Frontend

### Runtime & Build
- **Node.js** - JavaScript runtime (v18+ required by package.json)
- **Vite 5.0** - Fast build tool and dev server
  - TypeScript support via @vitejs/plugin-react
  - Environment variable loading (VITE_API_URL)
  - Library build mode (npm run build:lib)
  - Proxy configuration for /api and /ws endpoints
  - Port: 5173 (configurable)

### Core Framework
- **React 18.2.0** - UI library
  - Peer dependency with react-dom 18.2.0
  - JSX support via @vitejs/plugin-react

### State Management & Architecture
- **Zustand 5.0** - Lightweight state management
- **Dockview React 4.13.1** - Panel/layout management system
  - Custom tabbing (hideClose for shell tabs)
  - Layout persistence support

### Styling & UI Components
- **Tailwind CSS 4.1.18** - Utility-first CSS framework
  - @tailwindcss/vite integration
  - Design tokens: colors, spacing, border-radius, shadows, transitions
  - Dark mode support (selector mode)
  - Custom CSS variables for theming
- **Radix UI Components**
  - @radix-ui/react-avatar 1.1.11
  - @radix-ui/react-dialog 1.1.15
  - @radix-ui/react-slot 1.2.4
  - @radix-ui/react-tooltip 1.2.8
- **lucide-react 0.562.0** - Icon library
- **class-variance-authority 0.7.1** - Component variant management

### Rich Text Editing
- **Tiptap 3.15.2** - Headless rich text editor
  - Core, extensions, React integration (@tiptap/react)
  - Code blocks with syntax highlighting (lowlight)
  - Extensions: tables, lists, links, images, placeholders, text-align, underline, task lists
  - Markdown support (@tiptap/markdown)
  - Image resize extension (tiptap-extension-resize-image)
- **Markdown-it 14.0.0** - Markdown parser
- **Remark GFM 4.0.1** - GitHub Flavored Markdown support

### Terminal & Shell
- **Xterm.js 5.3.0** - Terminal emulator
  - @xterm/addon-fit 0.8.0 - Auto-fit to container
- **React Simple Code Editor 0.14.1** - Code editor component

### Diff & Version Control Visualization
- **react-diff-view 3.2.0** - Diff visualization component
- **unidiff 1.0.4** - Diff parsing
- **diff 8.0.2** - Diff generation
- **prism-react-renderer 2.4.1** - Syntax highlighting for diffs

### Markdown & Content
- **Turndown 7.1.2** - HTML to Markdown converter
- **turndown-plugin-gfm 1.0.2** - GitHub Flavored Markdown plugin
- **@assistant-ui/react 0.11.53** - AI assistant UI components
- **@assistant-ui/react-markdown 0.11.9** - Markdown rendering for AI content
- **lowlight 3.3.0** - Syntax highlighting (used with Tiptap)

### Agent Framework
- **@sandbox-agent/cli 0.1.7** - Sandbox agent CLI integration

### Validation & Types
- **Zod 4.3.6** - Runtime type validation
- **TypeScript 5.3.3** - Static type checking

### Utilities
- **clsx 2.1.1** - CSS class string builder
- **tailwind-merge 3.4.0** - Merge Tailwind class utilities

### Development Tools
- **ESLint 9.39.2** - Linting
  - @eslint/js 9.39.2
  - eslint-plugin-react 7.37.5
  - eslint-plugin-react-hooks 7.0.1
  - globals 17.0.0
- **Vitest 1.3.1** - Unit testing (Vite-native)
  - @vitest/ui 1.3.1 - Test UI
  - @vitest/coverage-v8 1.3.1 - Code coverage
  - jsdom 24.0.0 - DOM emulation
- **Testing Library 14.2.1** - Testing utilities
  - @testing-library/react 14.2.1
  - @testing-library/jest-dom 6.4.2
  - @testing-library/user-event 14.5.2
- **Playwright 1.58.1** - E2E testing
  - Tests run on Chromium, Firefox, WebKit, and mobile browsers
  - Screenshots/traces on failure

---

## Backend

### Runtime & Framework
- **Python 3.10+** - Programming language
- **FastAPI 0.100.0+** - Modern, fast async web framework
  - CORS middleware configuration
  - OpenAPI/Swagger documentation
  - Async/await native
- **Uvicorn 0.23.0+** - ASGI server (with standard extras)
  - Can run as: `uvicorn app:app --reload`

### WebSocket & Terminal
- **Websockets 11.0+** - WebSocket protocol support
- **ptyprocess 0.7.0+** - Pseudo-terminal spawning
  - Used for shell terminal sessions (PTY router)
  - Supports xterm-256color TERM environment

### Async & Concurrency
- **Asyncio** - Python's built-in async framework (via FastAPI)
- **aiofiles 23.0.0+** - Async file I/O

### Cloud Storage (Optional)
- **boto3 1.28.0+** - AWS SDK (optional dependency, s3 extra)
  - S3Storage implementation available via pip install boring-ui[s3]
- **s3fs** - S3 filesystem (indirect dependency via boto3)

### Build & Packaging
- **Hatchling** - Modern Python package builder
  - Package structure: src/back/boring_ui

### Development & Testing
- **pytest 7.0+** - Testing framework
- **pytest-asyncio 0.21+** - Async test support
- **httpx 0.24+** - Async HTTP client for testing

### Core Modules
- **pathlib.Path** - Modern path handling
- **subprocess** - Git command execution
- **json** - JSON serialization (for stream protocol)
- **collections.deque** - Message history buffers
- **dataclasses** - Session/session data structures

---

## Storage Backends

### LocalStorage (Default)
- File-based storage at workspace root
- Security: Path validation to prevent directory traversal

### S3Storage (Optional)
- AWS S3 object storage
- Configured with bucket name and optional prefix
- Available via `pip install boring-ui[s3]`

---

## API Routers (Modular)

### File Router (`/api`)
- File system operations: read, write, delete, rename, move, list
- Storage-agnostic (supports LocalStorage, S3Storage, custom implementations)

### Git Router (`/api/git`)
- Git command execution: status, diff, show
- Runs in workspace directory with subprocess

### PTY Router (`/ws`)
- WebSocket endpoint for pseudo-terminal sessions
- Spawns shell processes with ptyprocess
- History buffer: 200KB default (PTY_HISTORY_BYTES env var)
- Session management with idle TTL (PTY_IDLE_TTL, default 30s)
- Max concurrent sessions: 20 (PTY_MAX_SESSIONS env var)

### Stream Router (`/ws` - alias: chat_claude_code)
- WebSocket endpoint for Claude AI streaming
- Uses Claude CLI subprocess with stream-json format
- Handles permission suggestions/settings persistence
- History buffer: 1000 lines default (KURT_STREAM_HISTORY_LINES env var)
- Idle TTL: 60s default (KURT_STREAM_IDLE_TTL env var)
- Max concurrent sessions: 20 (KURT_STREAM_MAX_SESSIONS env var)
- Default slash commands: clear, model, thinking, memory, permissions, mcp, hooks, agents, help, compact, cost, init, terminal, restart

### Approval Router (`/api`)
- Workflow approval endpoints
- In-memory store by default (InMemoryApprovalStore)
- Supports custom approval store implementations

### Capabilities Router (`/api`)
- /api/capabilities - Feature discovery endpoint
- Advertises enabled routers and features to frontend
- Health check: /health
- Config endpoint: /api/config
- Session endpoints: /api/sessions, /api/sessions (POST)

---

## Configuration

### Frontend Configuration (appConfig.js)
- **Branding**: app name, logo, title format
- **FileTree**: sections, config files, polling intervals
- **Storage**: localStorage prefix, layout version
- **Panels**: essential panels, sizes, collapsed states
- **API**: baseUrl (auto-detected or VITE_API_URL)
- **Features**: git status, search, cloud mode, workflows flags
- **Styles**: light/dark theme customization (CSS variables)

### Environment Variables
**Frontend:**
- `VITE_API_URL` - Backend API base URL (defaults to http://localhost:8000)

**Backend:**
- `PTY_HISTORY_BYTES` - Terminal history buffer size (default: 200000)
- `PTY_IDLE_TTL` - PTY session idle timeout in seconds (default: 30)
- `PTY_MAX_SESSIONS` - Max concurrent PTY sessions (default: 20)
- `KURT_STREAM_HISTORY_LINES` - Stream history line count (default: 1000)
- `KURT_STREAM_IDLE_TTL` - Stream session idle timeout (default: 60)
- `KURT_STREAM_MAX_SESSIONS` - Max concurrent stream sessions (default: 20)

---

## Build & Deploy Configuration

### Frontend Build
- **Library Mode** (`npm run build:lib`): Exports as CommonJS and ESM
  - Entry: src/front/index.js
  - Output: dist/boring-ui.cjs, dist/boring-ui.js
  - Single stylesheet: dist/style.css
  - External dependencies: react, react-dom, react/jsx-runtime (peer)
  - Sourcemap enabled

### Backend Build
- **Wheel Package**: Uses Hatchling
  - Package path: src/back/boring_ui
  - Optional extras: [s3] for S3 storage support

### Development Servers
- **Frontend**: `npm run dev` - Vite dev server on port 5173
- **Backend**: `uvicorn src.back.boring_ui.api.app:app --reload` - FastAPI on port 8000
- **Proxies**: Frontend proxies /api and /ws to backend for development

### Testing
- **Unit Tests**: `npm test` or `npm run test:run`
- **E2E Tests**: `npm run test:e2e` - Playwright
- **Coverage**: `npm run test:coverage`

---

## Code Quality

### Linting
- ESLint with React and React Hooks plugins
- Configuration: eslint.config.js

### Type Checking
- TypeScript 5.3.3 with strict mode enabled
- Path aliases: @/* → src/front/*
- Target: ES2020

### CSS & Styling
- Tailwind CSS 4.1.18 with v4 plugin integration
- Dark mode: selector-based
- Custom design token system via CSS variables

---

## Library Exports

When built as library (`npm run build:lib`), boring-ui exports:
- **Default export**: Main React component (BoringUI)
- **Named exports**: Individual components and hooks
- **Stylesheet**: dist/style.css (must be imported by consumer)
- **Formats**: Both ESM and CommonJS for maximum compatibility
