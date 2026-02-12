# Boring UI Testing Framework and Patterns

## Frontend Testing

### Test Framework Setup

**Test Runner**: Vitest 1.3.1
**Configuration** (`vitest.config.ts`):
- Environment: jsdom (simulates browser DOM)
- Globals enabled (describe, it, expect available without imports)
- Setup file: `./src/front/__tests__/setup.ts`
- Test pattern: `src/front/**/*.{test,spec}.{js,jsx,ts,tsx}`
- Excluded: `src/front/__tests__/e2e/**`
- CSS support enabled

**Coverage Configuration**:
- Provider: v8 (native V8 coverage)
- Reporters: text, json, html
- Include: `src/front/components/**`, `src/front/panels/**`
- Exclude: `src/front/__tests__/**`, `src/front/**/*.d.ts`

### Testing Libraries

**Core Dependencies**:
- @testing-library/react 14.2.1 - Component rendering and interaction
- @testing-library/jest-dom 6.4.2 - DOM assertions
- @testing-library/user-event 14.5.2 - User interaction simulation
- @vitest/ui 1.3.1 - Visual test UI
- @vitest/coverage-v8 1.3.1 - Coverage reporting

### Setup and Global Mocks

**Setup File** (`src/front/__tests__/setup.ts`):

**DOM Cleanup**:
```javascript
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
})
```

**Mocked Browser APIs**:
1. **IntersectionObserver** - Used by virtual scrolling libraries
   - Methods: observe, unobserve, disconnect (all vi.fn())

2. **ResizeObserver** - Used by resize-detecting components
   - Methods: observe, unobserve, disconnect (all vi.fn())

3. **window.matchMedia** - Media queries
   - Returns mock with matches, media, listeners properties
   - Full event handling API mocked

4. **navigator.clipboard** - Clipboard operations
   - writeText: resolves with undefined
   - readText: resolves with empty string

5. **EventSource** - Server-sent events
   - States: CONNECTING (0), OPEN (1), CLOSED (2)
   - Properties: readyState, onopen, onmessage, onerror
   - Methods: close, addEventListener, removeEventListener
   - Helpers: simulateMessage(), simulateError() for tests

6. **fetch** - HTTP requests (globally mocked)
   - Tests override with specific mock implementations
   - Synchronous stubs via vi.fn()

**Environment**:
```javascript
vi.stubEnv('VITE_API_URL', '')
```

### Test Structure and Patterns

**Test File Location**:
```
src/front/
├── components/
│   ├── FileTree.jsx
│   ├── UserMenu.jsx
│   └── ...
└── __tests__/
    ├── components/
    │   ├── FileTree.test.tsx
    │   ├── UserMenu.test.tsx
    │   └── ...
    ├── integration/
    │   └── layout-persistence.test.tsx
    ├── fixtures/
    ├── utils/
    └── setup.ts
```

**Default Test Structure** (from FileTree.test.tsx):

```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Component from '../../components/Component'

describe('Component', () => {
  const defaultProps = {
    prop1: value1,
    prop2: vi.fn(),
  }

  beforeEach(() => {
    setupApiMocks({
      '/api/endpoint': { data: 'value' },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Feature Group', () => {
    it('describes specific behavior', () => {
      render(<Component {...defaultProps} />)
      // Test assertions
    })
  })
})
```

### Testing Utilities and Helpers

**API Mocking Helper** (`setupApiMocks`):
```javascript
setupApiMocks({
  '/api/tree': { entries: [] },
  '/api/git/status': { available: true, files: {} },
  '/api/search': (url) => { /* Dynamic response */ }
})
```
- Supports static objects and functions for dynamic responses
- Functions receive URL and return mock response
- Global fetch is stubbed with this implementation

**Common Test Utilities**:
- `flushPromises()` - Wait for pending promises
- `simulateContextMenu(element, coords)` - Trigger context menu
- `simulateDragDrop(source, target)` - Simulate drag operations
- `waitFor(() => expect(...), { timeout: 5000 })` - Poll with timeout

**Fixture Data**:
```javascript
import { fileTree, gitStatus, searchResults } from '../fixtures'
```
- fileTree.root - Root directory entries
- fileTree.srcDir - src directory contents
- gitStatus.clean - No changed files
- searchResults.basic - Sample search results

### Common Testing Patterns

**Async Component Testing**:
```javascript
it('waits for async data load', async () => {
  render(<Component />)

  // Wait for loading to complete
  await waitFor(() => {
    expect(screen.getByText('Content')).toBeInTheDocument()
  })
})
```

**Polling and Intervals**:
```javascript
it('sets up polling interval', async () => {
  const setIntervalSpy = vi.spyOn(global, 'setInterval')
  render(<Component />)

  await waitFor(() => {
    expect(setIntervalSpy).toHaveBeenCalled()
  })

  setIntervalSpy.mockRestore()
})
```

**Cleanup and Unmount**:
```javascript
it('cleans up polling on unmount', async () => {
  const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
  const { unmount } = render(<Component />)

  unmount()

  expect(clearIntervalSpy).toHaveBeenCalled()
  clearIntervalSpy.mockRestore()
})
```

**User Interactions**:
```javascript
it('handles click events', async () => {
  const onClickMock = vi.fn()
  render(<Component onClick={onClickMock} />)

  fireEvent.click(screen.getByRole('button'))

  expect(onClickMock).toHaveBeenCalled()
})
```

**Search and Selection**:
```javascript
// By text
const element = screen.getByText('Label')

// By role
const button = screen.getByRole('button', { name: 'Submit' })

// By placeholder
const input = screen.getByPlaceholderText('Search...')

// By test ID
const container = screen.getByTestId('file-item')

// Query variants
screen.queryByText('Text') // Returns null if not found
screen.getAllByText('Text') // Returns array
```

### Component Test Examples

**FileTree Component Tests**:
- Rendering: Initial load, retry on empty, project title
- Directory operations: Expand, collapse, nested navigation
- File selection: Click handling, active state highlighting
- Search: Input handling, result display, text highlighting, result selection
- Git Status: Modified badges, new file indicators, directory change detection
- Context Menu: Right-click display, option visibility, menu closure
- File Operations: Rename, delete (with confirmation), create
- Drag & Drop: Draggable attributes, visual feedback, drop zones
- Polling: Interval setup, refresh on expand, cleanup on unmount
- State Reflection: File moves, directory updates after polling

**UserMenu Component Tests**:
- Avatar rendering with email initials
- Dropdown open/close behavior
- Click outside to close
- Empty/undefined email handling
- Accessibility attributes

### Running Tests

**Available Scripts** (from package.json):
```bash
npm run test              # Watch mode (Vitest)
npm run test:run         # Single run
npm run test:coverage    # Coverage report
npm run test:ui          # Visual UI
```

**Test Output**:
- Console output in watch mode
- Coverage HTML report in `coverage/` directory
- Vitest UI available at http://localhost:51204/__vitest__/ (when running with --ui)

## Backend Testing

### Test Framework Setup

**Test Runner**: pytest 7.0+
**Async Support**: pytest-asyncio 0.21+
**HTTP Client**: httpx >= 0.24 with AsyncClient

**Configuration** (`tests/conftest.py`):
```python
# Path setup for src-layout imports
_PROJECT_ROOT = Path(__file__).parent.parent
_SRC_BACK = _PROJECT_ROOT / 'src' / 'back'
sys.path.insert(0, str(_SRC_BACK))

@pytest.fixture
def workspace_root(tmp_path):
    """Create a temporary workspace root for testing."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace
```

### Test Structure

**Test Organization**:
```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_file_routes.py  # File operations
│   ├── test_git_routes.py   # Git integration
│   ├── test_capabilities.py # API capabilities
│   ├── test_config.py       # Configuration
│   ├── test_approval.py     # Approval workflows
│   ├── test_pty_module.py   # PTY handling
│   └── test_storage.py      # Storage backends
└── integration/
    └── test_create_app.py   # App factory and routing
```

### Fixtures and Setup

**Workspace Fixture**:
```python
@pytest.fixture
def workspace_root(tmp_path):
    """Create a temporary workspace root for testing."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace
```

**App Factory Fixture**:
```python
@pytest.fixture
def app(tmp_path):
    """Create test FastAPI app with routers."""
    config = APIConfig(workspace_root=tmp_path)
    storage = LocalStorage(tmp_path)

    # Create test files
    (tmp_path / 'test.txt').write_text('content')
    (tmp_path / 'subdir').mkdir()

    app = FastAPI()
    app.include_router(create_file_router(config, storage), prefix='/api')
    return app
```

**Minimal vs Full Apps**:
```python
@pytest.fixture
def app(workspace):
    """Full application with all routers."""
    config = APIConfig(workspace_root=workspace)
    return create_app(config)

@pytest.fixture
def minimal_app(workspace):
    """Core routers only."""
    config = APIConfig(workspace_root=workspace)
    return create_app(config, include_pty=False, include_stream=False)
```

### Testing Patterns

**Async HTTP Testing**:
```python
@pytest.mark.asyncio
async def test_get_tree_root(self, app):
    """Test listing root directory."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        r = await client.get('/api/tree?path=.')
        assert r.status_code == 200
        data = r.json()
        assert 'entries' in data
```

**Class-Based Test Organization**:
```python
class TestTreeEndpoint:
    """Tests for GET /tree endpoint."""

    @pytest.mark.asyncio
    async def test_get_tree_root(self, app):
        ...

    @pytest.mark.asyncio
    async def test_get_tree_subdir(self, app):
        ...

    @pytest.mark.asyncio
    async def test_get_tree_nonexistent(self, app):
        ...
```

**File System Testing**:
```python
def test_file_creation():
    # Create test files in tmp_path fixture
    (tmp_path / 'test.txt').write_text('test content')
    (tmp_path / 'subdir').mkdir()
    (tmp_path / 'subdir' / 'nested.txt').write_text('content')

    # Tests interact with real filesystem
    # Cleanup handled automatically by pytest
```

**Configuration Testing**:
```python
def test_path_validation():
    config = APIConfig(workspace_root=tmp_path)

    # Valid paths
    result = config.validate_path('subdir/file.txt')
    assert result.is_relative_to(config.workspace_root)

    # Invalid (traversal) paths
    with pytest.raises(ValueError):
        config.validate_path('../outside/file.txt')
```

### Running Tests

**Test Commands**:
```bash
# Run all tests
pytest

# Run with markers
pytest -m asyncio

# Run specific test file
pytest tests/unit/test_file_routes.py

# Run specific test class/method
pytest tests/unit/test_file_routes.py::TestTreeEndpoint::test_get_tree_root

# Verbose output
pytest -v

# Show print statements
pytest -s

# Coverage
pytest --cov=src/back/boring_ui --cov-report=html
```

### Test Coverage Expectations

**Frontend**:
- Component tests: FileTree, UserMenu, Editor, FrontmatterEditor, GitDiff
- Integration tests: Layout persistence, app initialization
- Coverage targets: Components and panels directories
- Excluded: Test utilities, type definitions

**Backend**:
- Unit tests: File routes, Git routes, Storage, Config, Capabilities, Approval, PTY
- Integration tests: App factory, router composition, health checks
- Coverage targets: api/, modules/, core functionality
- Expected: >80% coverage on critical paths

## E2E Testing

### Test Framework

**Framework**: Playwright 1.58.1
**Configuration** (`playwright.config.js`):
- Browser types: chromium (default), firefox, webkit (optional)
- Base URL: http://localhost:5173
- Timeout: 30 seconds per test
- Screenshot on failure: captured
- Trace collection: on first retry

**Test Pattern**:
```
src/front/__tests__/e2e/**/*.spec.ts
```

### Running E2E Tests

```bash
npm run test:e2e           # Full run with all configured browsers
npm run test:e2e:ui        # Interactive UI mode
npm run test:e2e:debug     # Debug mode with Inspector
```

## Mocking Strategies

### Frontend Mocking

**Global Mocks** (in setup.ts):
- Browser APIs: IntersectionObserver, ResizeObserver, matchMedia
- Clipboard API: writeText, readText
- EventSource: SSE handling
- fetch: Global stub (tests provide specific implementations)

**Component-Level Mocks**:
```javascript
const defaultProps = {
  onOpen: vi.fn(),
  onFileDeleted: vi.fn(),
  onFileRenamed: vi.fn(),
}
```

**API Response Mocking**:
```javascript
setupApiMocks({
  '/api/tree': { entries: fileTree.root },
  '/api/git/status': { available: true, files: {} },
  '/api/search': (url) => {
    const params = new URL(url, 'http://localhost').searchParams
    const query = params.get('q')
    // Dynamic response based on query
  }
})
```

### Backend Mocking

**Temporary File Systems**:
```python
@pytest.fixture
def tmp_path():  # Built-in pytest fixture
    """Provides isolated temporary directory"""
    # Each test gets fresh tmp_path
```

**Storage Backends**:
```python
storage = LocalStorage(tmp_path)  # File-based storage for testing
# Can be swapped with InMemoryStorage or other implementations
```

## Best Practices

### Frontend Testing

1. **Use semantic queries** - Prefer `getByRole` > `getByLabelText` > `getByPlaceholderText` > `getByTestId`
2. **Test behavior, not implementation** - Test what users see/do, not internal state
3. **Async operations** - Always use `waitFor` for state updates, API calls, polling
4. **Mock network calls** - API mocks should be realistic (errors, delays)
5. **Clean up** - Intervals cleared, event listeners removed, global state reset
6. **Test one thing** - Each test focuses on single behavior
7. **Realistic data** - Use fixtures that represent real-world usage

### Backend Testing

1. **Use AsyncClient with ASGITransport** - Tests real app routing
2. **Create realistic test data** - Sample files and directories
3. **Test error cases** - Invalid paths, missing resources, conflicts
4. **Isolation** - Each test gets fresh tmp_path and fixtures
5. **Async markers** - Mark async tests with `@pytest.mark.asyncio`
6. **Fixtures for setup** - Database state, file structures, mocks
7. **Assertion messages** - Clear failure messages help debugging

## Test Coverage Goals

**Targets**:
- Frontend: 70%+ on components/panels (exclude utilities)
- Backend: 80%+ on core routes and business logic
- Critical paths: 95%+ (file ops, git, auth, PTY)
- Untested acceptable: Type definitions, display-only components

**Running Coverage**:
```bash
# Frontend
npm run test:coverage

# Backend
pytest --cov=src/back/boring_ui --cov-report=html tests/
```
