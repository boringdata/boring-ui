# Technical Debt, Concerns, and Issues

## Summary

This document catalogs known technical debt, potential bugs, security concerns, performance issues, and fragile areas in the boring-ui codebase. It serves as a living reference for prioritizing refactoring and hardening efforts.

---

## Critical Issues

### 1. Path Traversal Validation Inconsistency

**Location**: `src/back/boring_ui/api/storage.py` (lines 67-78) vs `src/back/boring_ui/api/config.py` (lines 42-67)

**Concern**: Two separate path validation implementations with slightly different logic:
- `LocalStorage._abs()` checks: `if self.root not in resolved.parents and resolved != self.root`
- `APIConfig.validate_path()` checks: `if not resolved.is_relative_to(self.config.workspace_root.resolve())`

**Risk**: If one implementation has a bug, the other might not catch all path traversal attempts. The condition in `LocalStorage._abs()` (line 76) could theoretically fail for symlinked paths or edge cases.

**Impact**: HIGH - Security vulnerability could allow file access outside workspace

**Recommendation**: Consolidate validation logic into a single, well-tested utility function. Use the more robust `is_relative_to()` method from both locations.

---

### 2. Blind Exception Handling in PTY Service

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (lines 85-86, 94-95)

```python
except Exception:
    break
except Exception:
    pass
```

**Concern**: These catch-all exception handlers silently swallow errors without logging. This makes debugging extremely difficult and could hide important issues:
- Line 85-86: Exception in read loop silently terminates
- Line 94-95: Exception during kill silently ignored

**Risk**: MEDIUM - Silent failures in PTY management could lead to:
- Sessions that appear alive but aren't
- Zombie processes not cleaned up
- Clients receiving no error feedback

**Recommendation**: Replace with specific exception handling and logging:
```python
except asyncio.CancelledError:
    break
except Exception as e:
    print(f"[PTY] Read loop error: {e}")
    break
```

---

### 3. Unsafe Subprocess Command Execution

**Location**: `src/back/boring_ui/api/modules/git/service.py` (lines 41-65)

```python
result = subprocess.run(
    ['git'] + args,  # args come from user input
    cwd=self.config.workspace_root,
    capture_output=True,
    text=True,
    timeout=30,
)
```

**Concern**: Git command arguments are directly passed from user input without validation. While subprocess.run() with list arguments is safer than shell=True, the code doesn't validate against dangerous git options.

**Risk**: MEDIUM - Possible information disclosure via git config:
- User could request `git config --get-all user.token`
- User could access environment variables via `git -c core.pager='env'`

**Recommendation**: Whitelist allowed git subcommands and validate arguments. Only allow specific operations (status, diff, show).

---

## High-Priority Issues

### 4. Weak CORS Configuration in Development

**Location**: `src/back/boring_ui/api/config.py` (lines 13-22)

```python
return [
    'http://localhost:5173',
    # ... other localhost origins ...
    '*',  # Allow all origins in dev - restrict in production
]
```

**Concern**: The wildcard `'*'` CORS origin is included in default development configuration. If this config is ever used in production, it creates a CSRF vulnerability.

**Risk**: MEDIUM - While documented as dev-only, accidental production deployment would be severe

**Recommendation**:
- Remove wildcard from defaults
- Make CORS origins environment-variable driven
- Add validation to prevent `'*'` in production

---

### 5. Unhandled PTY Session Registry Memory Leaks

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (lines 237-269)

**Concern**: The PTY session cleanup task has potential edge cases:
- Cleanup only removes idle sessions without clients (line 260)
- If a client connects and disconnects rapidly, timing windows exist where sessions aren't cleaned
- No maximum session count enforcement during normal operation (only checked in get_or_create)

**Risk**: MEDIUM - Over time, memory could accumulate from zombie sessions

**Recommendation**:
- Add metric tracking for session count
- Implement more aggressive TTL (not just idle timeout)
- Add a hard session limit with LRU eviction

---

### 6. Missing Error Handling in File Operations

**Location**: `src/back/boring_ui/api/file_routes.py` (lines 185-210)

```python
def search_recursive(dir_path: Path, depth: int = 0):
    if depth > 10:  # Prevent infinite recursion
        return

    try:
        entries = storage.list_dir(dir_path)
        # ...
    except (FileNotFoundError, PermissionError):
        pass  # Silently ignore
```

**Concern**: `PermissionError` during search is silently ignored. Unexpected exceptions (disk full, etc.) are also not caught.

**Risk**: LOW-MEDIUM - Search results incomplete without user feedback

**Recommendation**: Log permission errors and return partial results with a warning flag.

---

### 7. Global Mutable State in Stream Service

**Location**: `src/back/boring_ui/api/modules/stream/service.py` (lines 38-40)

```python
_SESSION_REGISTRY: dict[str, "StreamSession"] = {}
_SESSION_REGISTRY_LOCK = asyncio.Lock()
```

**Concern**: Global mutable dictionary accessed across async tasks. While a lock is used, there are potential issues:
- Lock not held during iteration in some cleanup paths
- Session objects themselves contain mutable state (clients set, history deque)
- No version tracking or generation IDs for concurrent access detection

**Risk**: MEDIUM - Race conditions possible in:
- Session cleanup during active broadcast
- Concurrent client additions/removals
- History buffer modifications

**Recommendation**: Wrap all registry operations in lock context managers. Consider using immutable data structures for sessions or generation IDs.

---

### 8. Unvalidated WebSocket Message Handling

**Location**: `src/back/boring_ui/api/modules/stream/router.py` (lines 26-220)

**Concern**: WebSocket message handling doesn't validate message structure:
```python
# No validation that message has required fields
for line in websocket_lines:
    await session.write_message(line)
```

**Risk**: MEDIUM - Malformed messages could cause crashes or unexpected behavior

**Recommendation**: Validate incoming JSON messages against a Pydantic model before processing.

---

## Medium-Priority Issues

### 9. Incomplete Git Status Parsing

**Location**: `src/back/boring_ui/api/modules/git/service.py` (lines 79-158)

**Concern**: Git status parsing assumes specific format and handles edge cases inconsistently:
- Lines 102-103: Handles `??` and `?` formats, but git can output other single-char variants
- Lines 133-140: Complex logic to determine if line[2] is space or not - fragile parsing
- No handling for submodule status (`S` in git porcelain)
- Doesn't handle merge conflict proper (`both added`, `both deleted`)

**Risk**: MEDIUM - Certain file states might be incorrectly reported to frontend

**Recommendation**: Use git's machine-readable `--porcelain=v2` format instead of v1.

---

### 10. Synchronous File I/O in Async Context

**Location**: `src/back/boring_ui/api/storage.py` (lines 101-110)

```python
def read_file(self, path: Path) -> str:
    p = self._abs(path)
    with open(p, 'r', encoding='utf-8') as f:  # Blocking I/O
        return f.read()
```

**Concern**: Synchronous file operations in async functions can block the event loop. For large files, this could cause noticeable latency.

**Risk**: LOW-MEDIUM - Performance degradation under load with large files

**Recommendation**: Use `aiofiles` or `loop.run_in_executor()` for large file operations.

---

### 11. Missing Session Lifecycle Validation

**Location**: `src/back/boring_ui/api/modules/stream/router.py` (lines 138-180)

**Concern**: Complex session creation logic with multiple states:
- `resume`, `force_new`, and implicit new session creation
- No atomic guarantee that session won't be created twice
- No validation that requested session still exists after lock release

**Risk**: MEDIUM - Race condition where two clients could create same session ID

**Recommendation**: Add generation ID or version number to sessions. Validate session state before operations.

---

### 12. No Request Size Limits

**Location**: `src/back/boring_ui/api/file_routes.py` (lines 91-107), `src/back/boring_ui/api/app.py`

**Concern**: No `max_request_size` configured in FastAPI app. Users could upload massive files:
```python
@router.put('/file')
async def put_file(path: str, body: FileContent):  # FileContent.content unbounded
    storage.write_file(rel_path, body.content)
```

**Risk**: MEDIUM - Denial of service via large file uploads

**Recommendation**: Set `max_request_size` in FastAPI config and validate file size in routes.

---

### 13. Unhandled Encoding Errors in Terminal Output

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (line 149)

```python
encoded = data.encode('utf-8', errors='replace')
```

**Concern**: While `errors='replace'` prevents crashes, it silently corrupts binary output. For non-UTF-8 terminal sessions, output quality degrades.

**Risk**: LOW - Terminal output displays garbled characters instead of proper text

**Recommendation**: Use `errors='surrogateescape'` for better fidelity and add encoding detection.

---

### 14. Incomplete Frontend TODO

**Location**: `src/front/components/UserMenu.jsx` (lines 38-41)

```javascript
// TODO: implement workspace management navigation
const handleManageWorkspace = () => {
    console.log('Manage workspace clicked', workspaceId)
    setIsOpen(false)
}
```

**Concern**: Unimplemented feature with silent failure (only logs to console).

**Risk**: LOW - Feature doesn't work, but gracefully degrades

**Recommendation**: Either implement or remove the UI element.

---

### 15. Blind localStorage Error Handling

**Location**: `src/front/components/chat/ClaudeStreamChat.jsx` (lines 114-126)

```javascript
try {
    const raw = localStorage.getItem(key)
    // ...
    return parsed
} catch {
    return []  // Silently return empty on any error
}
```

**Concern**: Catches all exceptions including JSON parse errors, data corruption, quota exceeded. User doesn't know why history is lost.

**Risk**: LOW-MEDIUM - User loses chat history silently without warning

**Recommendation**: Log errors and show toast notification when history recovery fails.

---

## Low-Priority Issues

### 16. Hardcoded Terminal Dimensions

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (line 53)

```python
dimensions=(24, 80)
```

**Concern**: Fixed terminal size doesn't match typical modern terminals (usually 24x120+). Resize message should be sent on connection.

**Risk**: LOW - Terminal displays may have odd wrapping

**Recommendation**: Use larger defaults or receive dimensions from client query params.

---

### 17. No Connection Timeout for WebSocket

**Location**: `src/back/boring_ui/api/modules/stream/router.py`, `src/back/boring_ui/api/modules/pty/router.py`

**Concern**: WebSocket connections can hang indefinitely if client disconnects ungracefully.

**Risk**: LOW - Accumulates hanging connections over time

**Recommendation**: Add idle timeout detection and graceful disconnect.

---

### 18. Loose Type Hints in Python Code

**Location**: `src/back/boring_ui/api/stream_bridge.py` (lines 44, 156, etc.)

```python
def __init__(self, config, pty_config=None, logger=None):  # No type hints
    self.config = config
```

**Concern**: Missing or `Any` type hints make refactoring dangerous and IDE support limited.

**Risk**: LOW - Harder to catch bugs during development

**Recommendation**: Add comprehensive type hints and use `mypy --strict`.

---

### 19. Missing Docstrings in Key Functions

**Location**: `src/back/boring_ui/api/modules/stream/service.py` (lines 68-98)

Several internal functions like `_normalize_rule()` lack docstrings explaining parameters and return types.

**Risk**: LOW - Harder to maintain

**Recommendation**: Add docstrings to all public and important internal functions.

---

### 20. Hardcoded Configuration Values

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (lines 14-16), `src/back/boring_ui/api/modules/stream/service.py` (lines 26-28)

```python
PTY_HISTORY_BYTES = int(os.environ.get('PTY_HISTORY_BYTES', 200000))
PTY_IDLE_TTL = int(os.environ.get('PTY_IDLE_TTL', 30))
PTY_MAX_SESSIONS = int(os.environ.get('PTY_MAX_SESSIONS', 20))
```

**Concern**: Configuration loaded at import time, not easily testable or changeable at runtime.

**Risk**: LOW - Difficult to configure for different deployment scenarios

**Recommendation**: Move configuration to APIConfig dataclass.

---

## Design Concerns

### 21. Blurred Responsibility in Stream Service

**Location**: `src/back/boring_ui/api/modules/stream/service.py` (lines 43-160)

The StreamSession class handles:
- Process management (spawning, termination)
- JSON parsing and protocol handling
- Permission suggestion persistence
- Environment variable management

**Concern**: Too many responsibilities make testing and debugging difficult. Session management is tangled with protocol handling.

**Recommendation**: Separate into:
1. `StreamProcess` - process lifecycle
2. `StreamProtocol` - JSON handling
3. `PermissionManager` - persistence logic

---

### 22. Tight Coupling Between Frontend and Backend Versions

**Location**: `src/front/components/chat/ClaudeStreamChat.jsx` (line 97), `src/back/boring_ui/api/modules/stream/service.py` (line 26)

Frontend and backend both define slash commands:
```javascript
// Frontend
const DEFAULT_SLASH_COMMANDS = [...]

# Backend
DEFAULT_SLASH_COMMANDS = [...]
```

**Concern**: Changes to commands must be synchronized in both places. If out of sync, UI shows commands that backend doesn't handle.

**Recommendation**: Backend should provide command list via `/api/capabilities` or new endpoint.

---

### 23. Incomplete Error Recovery in Chat

**Location**: `src/front/components/chat/ClaudeStreamChat.jsx` (missing error boundary)

**Concern**: No error boundary around ClaudeStreamChat component. A crash in chat would unmount entire pane.

**Risk**: MEDIUM - Bad stream message could crash the entire chat UI

**Recommendation**: Add React error boundary and display error state.

---

## Performance Concerns

### 24. Memory Inefficient History Storage

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (line 115), (lines 148-151)

```python
history: deque = field(default_factory=lambda: deque(maxlen=PTY_HISTORY_BYTES))

# Later: storing individual bytes
for byte in encoded:
    self.history.append(byte)
```

**Concern**: Storing history as individual bytes is extremely memory-inefficient. A 200KB deque with millions of appends causes:
- High memory fragmentation
- Slow garbage collection
- Inefficient serialization

**Risk**: MEDIUM - Memory usage grows quickly with active terminals

**Recommendation**: Store history as chunks (e.g., 64KB strings) instead of individual bytes.

---

### 25. No Pagination in File Search

**Location**: `src/back/boring_ui/api/file_routes.py` (lines 166-213)

```python
@router.get('/search')
async def search_files(q: str, path: str):
    # Returns ALL matches up to depth 10
    search_recursive(rel_path)
    return {'results': matches}
```

**Concern**: Large codebases could return thousands of results, consuming memory and network bandwidth.

**Risk**: MEDIUM - Performance degradation on large projects

**Recommendation**: Add `limit` and `offset` parameters for pagination.

---

### 26. No Caching for Expensive Operations

**Location**: `src/back/boring_ui/api/modules/git/service.py` (line 79-158)

Git status is recomputed on every request without caching. For large repos, `git status` can be slow.

**Risk**: LOW-MEDIUM - Slow git status on large repositories

**Recommendation**: Cache status for 5-10 seconds per path.

---

## Documentation Concerns

### 27. PLAN.md is Partially Implemented

**Location**: `/docs/PLAN.md`

Plan describes desired structure but implementation is incomplete:
- Some module naming doesn't match (chat_claude_code vs stream)
- Layout manager persistence not fully validated
- Recovery mechanisms not fully tested

**Risk**: LOW - Confusion about what's actually implemented

**Recommendation**: Update PLAN.md to reflect actual implementation or complete remaining work.

---

### 28. Minimal API Documentation

**Location**: Code lacks inline API documentation for WebSocket protocol

**Concern**: Protocol for PTY and stream WebSocket messages is not well documented in code.

**Risk**: LOW - Third-party integrations will guess at protocol

**Recommendation**: Add clear documentation and perhaps OpenAPI schema for WebSocket.

---

## Testing Gaps

### 29. Limited Test Coverage for Error Cases

**Location**: Test files in `/tests/` and `src/front/**/*.test.js`

**Concern**: Most tests cover happy paths. Edge cases and error conditions are rarely tested:
- Path traversal attempts not tested
- Malformed WebSocket messages not tested
- Session cleanup race conditions not tested

**Risk**: MEDIUM - Bugs in error handling discovered in production

**Recommendation**: Add test suite focused on error cases, security scenarios, and concurrency issues.

---

### 30. No Integration Tests

**Location**: Missing end-to-end tests

**Concern**: No tests that exercise full client-server interaction:
- Chat message flow through WebSocket
- File editing and git operations together
- Session cleanup under load

**Risk**: MEDIUM - Integration issues discovered after deployment

**Recommendation**: Add Playwright integration tests covering full workflows.

---

## Security Concerns

### 31. Subprocess Shell Injection Risk in PTY

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (line 49)

```python
self.process = ptyprocess.PtyProcessUnicode.spawn(
    command,  # Can be user-provided
    cwd=str(cwd),
    env=process_env,
    dimensions=(24, 80),
)
```

**Concern**: If `command` parameter comes from user input, shell metacharacters could be exploited.

**Risk**: HIGH - Remote code execution if command is user-controllable

**Recommendation**: Only allow whitelisted commands or require explicit shell escaping.

---

### 32. Insufficient Input Validation

**Location**: Multiple routes lack input validation for path parameters

**Concern**: While path traversal validation exists, other inputs are loosely validated:
- Glob patterns in search could be exploited
- Git diff/show paths validated, but branch names are not

**Risk**: MEDIUM - Potential for various injection attacks

**Recommendation**: Add Pydantic validation models for all inputs.

---

### 33. No Rate Limiting

**Location**: `src/back/boring_ui/api/app.py`

**Concern**: No rate limiting on any endpoints. Users could:
- Spam file operations
- Exhaust git process limits
- Flood WebSocket connections

**Risk**: MEDIUM - Denial of service

**Recommendation**: Add slowdown middleware with configurable rate limits.

---

## Dependency Concerns

### 34. Large Dependency on External Claude CLI

**Location**: `src/back/boring_ui/api/modules/stream/`, `src/back/boring_ui/api/config.py` (line 39)

```python
'claude': ['claude', '--dangerously-skip-permissions'],
```

**Concern**: Stream functionality completely depends on external `claude` binary. No version pinning or compatibility checking.

**Risk**: MEDIUM - Breaking changes in claude CLI could break stream feature

**Recommendation**:
- Version pin the claude CLI
- Detect version at startup and validate compatibility
- Provide clear error messages if CLI is missing or incompatible

---

### 35. Ptyprocess Library Not Pinned

**Location**: `src/back/boring_ui/api/modules/pty/service.py` (line 36)

```python
import ptyprocess
```

**Concern**: Optional dependency not specified in requirements with version pin.

**Risk**: LOW - Compatibility issues when dependency updates

**Recommendation**: Pin ptyprocess version in requirements.

---

## Known Workarounds and Quirks

### 36. Alias Support for Stream Router

**Location**: `src/back/boring_ui/api/app.py` (lines 85-92, 127-128)

```python
# Use new canonical name, but 'stream' also works via registry alias
enabled_routers.add('chat_claude_code')

# Support 'stream' alias -> 'chat_claude_code' for backward compatibility
if 'stream' in enabled_routers:
    enabled_routers.add('chat_claude_code')
```

**Concern**: Two names for same router causes complexity. Router arguments dict (lines 123-130) has duplicate entries.

**Risk**: LOW - Confusing to maintain, but works

**Recommendation**: Complete migration to `chat_claude_code` and remove `stream` alias.

---

### 37. Frontend History Storage Format

**Location**: `src/front/components/chat/ClaudeStreamChat.jsx` (lines 97-127)

**Concern**: Chat history stored in localStorage with custom format. No migration strategy if format changes.

**Risk**: LOW - Users lose chat history when format changes

**Recommendation**: Add version field to history format and migration functions.

---

## Configuration and Environment

### 38. No Environment Variable Validation

**Location**: `src/back/boring_ui/api/config.py` (lines 7-22)

Environment variables are read but not validated:
```python
PTY_HISTORY_BYTES = int(os.environ.get('PTY_HISTORY_BYTES', 200000))
# What if environment has invalid value?
```

**Risk**: LOW - Invalid config silently accepted or raises cryptic error

**Recommendation**: Add configuration validation at startup with clear error messages.

---

## Future Recommendations Summary

**Critical (Fix Immediately)**:
1. Consolidate path validation logic
2. Add logging to exception handlers
3. Validate git command arguments

**High Priority (Next Sprint)**:
4. Review CORS configuration for production safety
5. Improve PTY session cleanup and memory management
6. Add input validation for WebSocket messages
7. Fix git status parsing

**Medium Priority (Backlog)**:
8. Refactor stream service responsibilities
9. Move command definitions to backend
10. Add comprehensive error handling tests
11. Implement rate limiting
12. Add performance optimizations (caching, pagination)

**Low Priority (Nice to Have)**:
13. Add mypy strict type checking
14. Complete documentation
15. Improve logging across codebase
16. Add performance monitoring

---

**Document Version**: 1.0
**Last Updated**: 2026-02-09
**Status**: Initial comprehensive analysis complete
