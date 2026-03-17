# Extract GitBackend ABC — Make Git Pluggable

## Problem

Files are pluggable. Git is not.

```python
# Files — injectable, pluggable
create_app(storage=MyStorage())
create_file_router(config, storage)    # Storage ABC
FileService(config, storage)

# Git — hardcoded
create_app(...)                        # no git param
create_git_router(config)              # no backend param
GitService(config)                     # subprocess.run(['git', ...]) directly
```

`GitService` calls `subprocess.run(['git', ...], cwd=config.workspace_root)` with no
abstraction layer. To swap git implementations you'd have to fork the service.

## Goal

Extract a `GitBackend` ABC from `GitService`, mirroring how `Storage` ABC already works
for files. Ship `SubprocessGitBackend` as the only implementation. Zero behavior change.

## Phase 1: GitBackend ABC + error types + domain types

```python
# src/back/boring_ui/api/git_backend.py

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


# ── Domain types ──────────────────────────────────────────────────────

class StatusEntry(TypedDict):
    path: str
    status: str   # M, A, D, U, C


class RemoteInfo(TypedDict):
    remote: str
    url: str


@dataclass(frozen=True)
class GitCredentials:
    """Opaque credential object passed through to backend."""
    username: str
    password: str


# ── Error hierarchy ───────────────────────────────────────────────────

class GitBackendError(Exception):
    """Base error for all git backend failures."""

class GitCommandError(GitBackendError):
    """Git command execution failed."""
    def __init__(self, message: str, stderr: str = '', exit_code: int | None = None):
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code

class GitNotRepoError(GitBackendError):
    """Workspace is not a git repository."""

class GitConflictError(GitBackendError):
    """Merge conflict."""

class GitAuthError(GitBackendError):
    """Authentication/credential failure."""


# ── ABC ───────────────────────────────────────────────────────────────

class GitBackend(ABC):
    """Pluggable git operations backend.

    Returns domain-level values, NOT HTTP-shaped dicts. The GitService
    adapter wraps results into API response dicts and maps errors to
    HTTPException.

    Error contract: backends raise GitBackendError subclasses for all
    failures. GitService catches only GitBackendError, never subprocess
    or other implementation-specific exceptions.

    Path contract: all path arguments are repo-relative strings, already
    validated by GitService. Backends must not re-validate.
    """

    # ── Repo state ──

    @abstractmethod
    def is_repo(self) -> bool: ...

    @abstractmethod
    def status(self) -> list[StatusEntry]: ...

    @abstractmethod
    def diff(self, path: str) -> str: ...

    @abstractmethod
    def show(self, path: str) -> str | None: ...

    # ── Write operations ──

    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def add(self, paths: list[str] | None = None) -> None: ...

    @abstractmethod
    def commit(self, message: str, author_name: str | None = None,
               author_email: str | None = None) -> str: ...
    # Returns commit OID as string

    @abstractmethod
    def push(self, remote: str, branch: str | None = None,
             credentials: GitCredentials | None = None) -> None: ...

    @abstractmethod
    def pull(self, remote: str, branch: str | None = None,
             credentials: GitCredentials | None = None) -> None: ...

    @abstractmethod
    def clone(self, url: str, branch: str | None = None,
              credentials: GitCredentials | None = None) -> None: ...
    # Clones INTO workspace_root. Precondition: workspace_root is empty
    # or does not exist. Backend is responsible for target dir semantics.

    # ── Branches ──

    @abstractmethod
    def branches(self) -> tuple[list[str], str | None]: ...
    # Returns (branch_names, current_branch_or_none)

    @abstractmethod
    def create_branch(self, name: str, checkout: bool = True) -> None: ...

    @abstractmethod
    def checkout(self, name: str) -> None: ...

    @abstractmethod
    def merge(self, source: str, message: str | None = None) -> None: ...
    # Raises GitConflictError on conflict

    # ── Remotes ──

    @abstractmethod
    def add_remote(self, name: str, url: str) -> None: ...

    @abstractmethod
    def remove_remote(self, name: str) -> None: ...

    @abstractmethod
    def list_remotes(self) -> list[RemoteInfo]: ...
```

**Design decisions**:

- **Domain return types, not dicts**. `status()` returns `list[StatusEntry]`, not
  `{is_repo, files}`. `commit()` returns `str` (OID), not `{oid}`. `branches()` returns
  `tuple[list, str|None]`, not `{branches, current}`. GitService shapes these into HTTP
  response dicts.
- **`GitCredentials` dataclass** instead of loose `dict | None`. Type-safe, documented,
  prevents callers from passing arbitrary dicts.
- **`GitCommandError`** carries `stderr` and `exit_code` — needed for error mapping in
  GitService (e.g. "nothing to commit" → 400 vs generic failure → 500).
- **`GitNotRepoError`** separate from generic error — current service maps "not a repo"
  to a specific response, not a 500.
- **`current_branch()` removed** — `branches()` already returns current. One method, one
  source of truth. GitService calls `branches()` and extracts current when needed.
- **`clone()` preconditions documented** — target dir semantics are backend-specific,
  called out in docstring.
- **All methods `@abstractmethod`** — no concrete defaults on the ABC.
- **Ref/URL validation stays in GitService** — backends receive already-validated inputs.
  `_validate_git_ref`, `_validate_git_url` remain in the service layer.

## Phase 2: SubprocessGitBackend (mechanical extraction)

Move current `GitService` logic into `SubprocessGitBackend(GitBackend)`.

```python
# src/back/boring_ui/api/subprocess_git.py

class SubprocessGitBackend(GitBackend):
    """Git operations via subprocess. Current behavior, extracted."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def _run(self, args: list[str], credentials: GitCredentials | None = None,
             timeout: int = 30) -> str:
        # Current run_git() logic moved here byte-for-byte.
        # Wraps subprocess.CalledProcessError → GitCommandError
        # Wraps auth failures → GitAuthError
        # Wraps conflict detection → GitConflictError
        ...

    def status(self) -> list[StatusEntry]:
        if not self.is_repo():
            return []
        output = self._run(['status', '--porcelain'])
        # Current normalize_status logic, returns list[StatusEntry]
        ...

    def commit(self, message, author_name=None, author_email=None) -> str:
        # Current logic, returns OID string (not dict)
        ...
```

Module-level helpers stay in the same file: `_create_askpass_script`,
`_cleanup_askpass`, `_sanitize_git_error`.

Validation helpers move to GitService (or a shared `git_validation.py` module):
`_validate_git_ref`, `_validate_git_url`.

**Verification rules**:
- `SubprocessGitBackend` takes `workspace_root: Path`, NOT `APIConfig`
- `SubprocessGitBackend` never raises `HTTPException` — only `GitBackendError` subclasses
- `SubprocessGitBackend` never calls path validation — assumes inputs are valid
- `GitService` must NOT import `subprocess` after this split
- `_run()` error translation (stderr parsing, auth detection, conflict detection) must be
  byte-for-byte equivalent to current `run_git()`

**GitService becomes a thin adapter**:

```python
class GitService:
    def __init__(self, config: APIConfig, backend: GitBackend | None = None):
        self.config = config
        self.backend = backend or SubprocessGitBackend(config.workspace_root)

    def get_status(self) -> dict:
        try:
            entries = self.backend.status()
            return {
                'is_repo': self.backend.is_repo(),
                'available': True,
                'files': [dict(e) for e in entries],
            }
        except GitNotRepoError:
            return {'is_repo': False, 'available': True, 'files': []}

    def get_diff(self, path: str) -> dict:
        rel_path = self.validate_and_relativize(path)
        try:
            diff = self.backend.diff(str(rel_path))
            return {'diff': diff, 'path': path}
        except GitBackendError as e:
            # Preserve current behavior: untracked files return empty diff
            return {'diff': '', 'path': path, 'error': str(e)}

    def commit(self, message, author_name=None, author_email=None) -> dict:
        try:
            oid = self.backend.commit(message, author_name, author_email)
            return {'oid': oid}
        except GitCommandError as e:
            if 'nothing to commit' in e.stderr.lower():
                raise HTTPException(status_code=400, detail=f'Git error: {e.stderr}')
            raise HTTPException(status_code=500, detail=f'Git error: {e.stderr}')

    def list_branches(self) -> dict:
        branches, current = self.backend.branches()
        return {'branches': branches, 'current': current}
```

GitService retains: path validation, ref/URL validation, HTTP error mapping, response
formatting (wrapping domain values into API dicts).

GitService delegates: all git operations to `self.backend.*`.

## Phase 3: Wire into create_app

```python
# git_backend is keyword-only — won't break positional callers
def create_app(config=None, storage=None, *, git_backend=None, ...):
    # Lazy: only construct backend if git router is enabled
    if 'git' in enabled_routers and git_backend is None:
        git_backend = SubprocessGitBackend(config.workspace_root)
    router_args = {
        'files': (config, storage),
        'git': (config, git_backend),
    }

def create_git_router(config: APIConfig, git_backend: GitBackend | None = None) -> APIRouter:
    service = GitService(config, backend=git_backend)
```

Backward compatible: `git_backend=None` defaults to `SubprocessGitBackend`.
Lazy construction: backend not created if git router is excluded — no git import needed.

## Testing — No Regression Strategy

### Existing test inventory (all must pass unchanged)

| File | What it covers |
|---|---|
| `tests/unit/test_git_routes.py` | status, diff, show via HTTP (AsyncClient + ASGI) |
| `tests/unit/test_git_write_routes.py` | init, add, commit, push, pull, clone, remote via HTTP |
| `tests/unit/test_git_branch_routes.py` | branches, create, checkout, merge via GitService directly |
| `tests/unit/test_git_routes.py::TestAskpassSecurity` | credential escaping, stderr sanitization |
| `tests/unit/test_git_routes.py::TestPathSecurity` | path traversal rejection |

These tests use real `tmp_path` git repos, real `subprocess` git, and hit the router via
`httpx.AsyncClient(ASGITransport)`. They are the regression net.

**Rule**: Run full suite before AND after each phase. Diff API responses — must be
byte-identical.

### How tests adapt per phase

**Phase 1 (ABC + errors)**: No test changes. ABC is just a new file, nothing consumes it yet.

**Phase 2 (extraction)**: Existing tests still work because:
- `create_git_router(config)` → `GitService(config)` → internally creates
  `SubprocessGitBackend(config.workspace_root)`. Same code path, just indirected.
- Tests that import `GitService` directly (e.g. `test_git_branch_routes.py`) still work
  because `GitService.__init__` defaults to `SubprocessGitBackend`.
- Tests that import helpers (e.g. `_create_askpass_script`, `_sanitize_git_error`) will
  need import paths updated if helpers move to `subprocess_git.py`. Update imports, not
  assertions.

**New tests added in Phase 2**:
- `test_subprocess_git_backend.py` — call `SubprocessGitBackend` methods directly against
  a `tmp_path` git repo. Mirror the same assertions from existing route tests, but at the
  backend layer (no HTTP, no GitService).
- `test_git_backend_errors.py` — verify `SubprocessGitBackend` raises `GitCommandError`
  (with stderr + exit_code), `GitConflictError`, `GitNotRepoError` in the right cases.
- `test_git_service_adapter.py` — verify `GitService` maps `GitBackendError` →
  `HTTPException` correctly (conflict → 409, not-repo → 200 with is_repo=false,
  command error → 500, nothing-to-commit → 400).
- `test_init_add_commit_workflow.py` — backend starts with empty dir (no repo), calls
  `init → add → commit`, verifies OID returned. Tests the "not a repo yet" edge case.

**Phase 3 (wiring)**: Existing tests still work because `create_git_router(config)` with
no `git_backend` param defaults to current behavior.

**New test in Phase 3**:
- `test_create_app_git_injection.py` — verify `create_app(git_backend=mock)` passes mock
  through to GitService.
- `test_no_git_import.py` — `create_app(routers=['files'])` must not import
  `subprocess_git` module. Use `sys.modules` check.
- `test_no_subprocess_in_service.py` — static check that `git/service.py` does not contain
  `import subprocess` or `from subprocess`.

### CI gate

Add to CI: `pytest tests/unit/test_git*.py tests/unit/test_subprocess_git*.py
tests/unit/test_git_service_adapter.py -v` must pass with zero failures before merge.

## What does NOT change

Frontend, Storage ABC, LocalStorage, S3Storage, FileService, API contracts, capabilities.

## Success Criteria

- [ ] `GitBackend` ABC with all methods `@abstractmethod`
- [ ] Domain types: `StatusEntry`, `RemoteInfo`, `GitCredentials`
- [ ] Error hierarchy: `GitBackendError` > `GitCommandError` / `GitNotRepoError` / `GitConflictError` / `GitAuthError`
- [ ] `SubprocessGitBackend` passes all existing git tests
- [ ] `GitService` delegates to backend, no `subprocess` import
- [ ] `create_app(*, git_backend=...)` injectable, lazy construction
- [ ] `create_app()` without param = identical to current behavior
- [ ] Zero frontend changes, zero API contract changes
