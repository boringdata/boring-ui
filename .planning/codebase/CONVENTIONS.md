# Boring UI Codebase Conventions

## JavaScript/TypeScript Conventions

### Code Style and Formatting

**ECMAScript Version**: ES2020 (target) with full module support
- Strict TypeScript mode enabled across codebase
- Module resolution: ESNext with bundler configuration
- JSX Pragma: react-jsx (automatic runtime)

**ESLint Configuration** (`eslint.config.js`):
- Base: `@eslint/js` recommended rules
- Parser: ES2022 with JSX support enabled
- React plugins enabled: `react` and `react-hooks`

### Naming Conventions

**Variables and Functions**:
- camelCase for variables and function names
- Unused parameters prefixed with `_` are ignored (rule: `'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }]`)
- Functions not defined before use in classes/variables (rule allows function hoisting)

**React Components**:
- PascalCase for component names (e.g., `FileTree`, `UserMenu`, `Editor`)
- Functional components with hooks as primary pattern
- Props destructured in function parameters

**File Organization**:
- Components in `/src/front/components/` directory
- JSX files use `.jsx` extension (can be `.tsx` for TypeScript)
- Test files colocated with component folder structure in `__tests__/`
- Utilities in `/src/front/utils/` (e.g., `apiBase.js`, `fileIcons.js`)
- Custom hooks in `/src/front/hooks/` directory
- Layout managers and configuration in `/src/front/layout/` and `/src/front/config/`

### React Patterns and Hook Usage

**Rules**:
- `react-hooks/recommended` rules enforced
- Hook dependency arrays must be complete
- Hooks can be conditionally called with `react-hooks/set-state-in-effect` disabled as needed
- React imports must be declared even with automatic JSX pragma (legacy pattern in codebase)

**Common Patterns Observed**:
- `useState` for local component state
- `useRef` for direct DOM access and closure-safe tracking (see FileTree polling pattern)
- `useEffect` for side effects and lifecycle management
- `useCallback` for memoizing callback functions passed to children
- `useMemo` for expensive computations
- Custom hooks in `src/front/hooks/` for reusable logic

**Example Pattern - Closure-safe State Tracking**:
```javascript
const expandedDirsRef = useRef(expandedDirs)
useEffect(() => {
  expandedDirsRef.current = expandedDirs
}, [expandedDirs])
```
Used when setInterval or async operations need current state without stale closures.

### Import Organization

**Order**:
1. React and core dependencies
2. Third-party libraries (lucide-react, @tiptap, etc.)
3. Local utilities and utilities
4. Components and other local imports

**Example**:
```javascript
import React, { useEffect, useState, useRef, useCallback } from 'react'
import { Search, X, Folder } from 'lucide-react'
import { buildApiUrl } from '../utils/apiBase'
import FileTree from './FileTree'
```

### Error Handling

**Frontend**:
- Promise chains use `.catch(() => {})` for silent failures on non-critical operations
- Network errors not explicitly handled at component level (rely on fallback rendering)
- Form validation done inline during submission
- API failures degrade gracefully (e.g., git status unavailable shows tree without badges)

**Server Communication**:
- All API calls go through `buildApiUrl()` helper
- Configuration path supported via `VITE_CONFIG_PATH` environment variable
- Fallback defaults provided for missing configurations

### CSS and Styling

**Approach**: Tailwind CSS with class variance authority
- PostCSS configured via `tailwind.config.js`
- Responsive design using Tailwind breakpoints
- Custom animations in `tw-animate-css` package
- CSS modules not used; utility-first approach preferred

### Dependencies and Imports

**Key Dependencies**:
- React 18.2.0 (peer dependency)
- Lucide React for icons
- Tiptap for rich text editing
- React Diff View for git diffs
- @radix-ui for primitives (Avatar, Dialog, Tooltip, Slot)
- Zustand for state management
- Zod for schema validation
- XTerm for terminal emulation

## Python Conventions

### Code Style

**Version**: Python 3.10+
**Build System**: Hatchling with pyproject.toml (PEP 517)
**Project Root Layout**: `src/back/boring_ui/api/` for application code

### Naming Conventions

**Modules and Functions**:
- snake_case for module names and functions
- Module organization: `modules/` subdirectory for feature routers
  - `modules/files/` - file operations
  - `modules/git/` - git integration
  - `modules/pty/` - pseudo-terminal handling
  - `modules/stream/` - streaming responses

**Classes**:
- PascalCase for class names
- Config classes use `@dataclass` decorator
- Example: `APIConfig`, `LocalStorage`, `InMemoryApprovalStore`

**Constants**:
- UPPER_SNAKE_CASE for module-level constants
- Lowercase for local scope constants

### Code Organization

**Application Factory Pattern**:
- Central entry point: `create_app()` in `app.py`
- All routers created via factory functions: `create_*_router(config, ...)`
- Dependencies injected via function arguments (no globals)
- CORS middleware configured via `APIConfig`

**Router Structure**:
```python
def create_file_router(config: APIConfig, storage: Storage) -> APIRouter:
    router = APIRouter(prefix='/api/files', tags=['files'])

    @router.get('/tree')
    async def get_tree(path: str = '.'):
        # Implementation

    return router
```

**Configuration**:
- Centralized in `APIConfig` dataclass
- Environment variables used for overrides (e.g., `CORS_ORIGINS`)
- Default values computed in factory functions
- Path validation with `validate_path()` to prevent traversal attacks

### Security Patterns

**Path Validation**:
- All file paths validated with `APIConfig.validate_path()`
- Prevents directory traversal attacks
- Resolves symlinks and normalizes paths
- Must be called before any filesystem access

**CORS Configuration**:
- Configurable via `APIConfig.cors_origins`
- Environment variable override: `CORS_ORIGINS` (comma-separated)
- Development defaults include localhost:5173-5175 and localhost:3000
- Production should restrict to specific origins

### Error Handling

**Patterns Observed**:
- Exceptions raised for validation failures
- HTTP status codes used appropriately (200, 400, 404, etc.)
- Error messages sent as JSON responses
- AsyncIO used for async operations (not blocking I/O)

**Example**:
```python
def validate_path(self, path: Path | str) -> Path:
    """Validate that a path is within workspace_root."""
    if isinstance(path, str):
        path = Path(path)
    resolved = (self.workspace_root / path).resolve()
    if not resolved.is_relative_to(self.workspace_root.resolve()):
        raise ValueError(f'Path traversal detected: {path}')
    return resolved
```

### Type Hints

**Full Type Coverage**:
- Function parameters and return types annotated
- Union types using `|` syntax (Python 3.10+)
- Optional parameters use `| None`
- Example: `routers: list[str] | None = None`

### Dependencies

**Production**:
- FastAPI >= 0.100.0 (web framework)
- Uvicorn >= 0.23.0 (ASGI server)
- ptyprocess >= 0.7.0 (PTY handling)
- websockets >= 11.0 (WebSocket support)
- aiofiles >= 23.0.0 (async file operations)
- boto3 >= 1.28.0 (S3, optional)

**Development**:
- pytest >= 7.0
- pytest-asyncio >= 0.21
- httpx >= 0.24

### Module Dependencies Pattern

**Dependency Injection**:
- All routers receive `config` and `storage` as arguments
- No global state
- Approval store injected separately
- Router registry for optional feature loading

**Example**:
```python
def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
) -> FastAPI:
    # Defaults injected here
    if config is None:
        config = APIConfig(workspace_root=Path.cwd())
```

## Cross-Platform Patterns

### API Communication

**Frontend to Backend**:
- REST API at base URL from `VITE_API_URL` or `http://localhost:8000`
- Endpoints use `/api/` prefix
- Path encoding: `encodeURIComponent()` for safety
- Query parameters for options

**WebSocket Communication**:
- PTY bridge for interactive terminal
- Stream bridge for Claude streaming responses
- Event-based message handling

### Configuration Files

**Frontend** (`app.config.test.js`):
- Branding configuration (name, logo, title format)
- FileTree settings (sections, polling intervals, git integration)
- Panel dimensions (default, minimum, collapsed sizes)
- Feature flags (gitStatus, search, cloudMode, workflows)
- API base URL configuration
- Theme color schemes

**Environment Variables**:
- `VITE_API_URL`: Backend API base URL
- `VITE_CONFIG_PATH`: Path to load config from
- `CORS_ORIGINS`: Comma-separated list of allowed origins (Python)

## Code Quality

### Linting

**ESLint** (JavaScript/TypeScript):
```bash
npm run lint  # Lints src/front/
```

**Rules**:
- No use of variables before definition (except functions)
- All variables must be used (unused parameters starting with `_` ignored)
- React JSX syntax required
- React Hooks recommendations enforced

### Testing

**JavaScript**:
- Test runner: Vitest with jsdom environment
- Testing library: @testing-library/react with jest-dom assertions
- Test glob pattern: `src/front/**/*.{test,spec}.{js,jsx,ts,tsx}`
- Coverage tool: v8 provider
- Setup file: `src/front/__tests__/setup.ts`

**Python**:
- Test runner: pytest
- Async test support: pytest-asyncio
- HTTP client for testing: httpx.AsyncClient with ASGITransport
- Test directories: `tests/unit/` and `tests/integration/`
- Fixtures for temporary workspaces and app creation

## Documentation Standards

**JSDoc Style** (TypeScript/JavaScript):
- Function and component purpose documented
- Parameter descriptions with types
- Return type descriptions
- Example usage in complex components

**Python Docstrings**:
- Google-style docstrings for public APIs
- Module-level docstrings describing purpose
- Args, Returns, Raises sections for functions

## Formatting and Consistency

**Code Formatting**:
- No explicit prettier configuration (relies on ESLint)
- Line length not enforced by linter
- Indentation: Consistent tab/space usage per file

**Imports**:
- Sorted in groups (core, third-party, local)
- No star imports in main code
- Absolute imports preferred over relative (where possible)
