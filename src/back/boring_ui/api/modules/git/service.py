"""Git operations service for boring-ui API.

Thin adapter: validates inputs, delegates to GitBackend, shapes results
into HTTP response dicts, maps selected GitBackendError subclasses to
HTTPException (GitCommandError, GitConflictError, GitAuthError).
"""
import re
from pathlib import Path
from urllib.parse import urlparse
from fastapi import HTTPException

from ...config import APIConfig
from ...git_backend import (
    GitBackend,
    GitAuthError,
    GitCommandError,
    GitConflictError,
    GitCredentials,
)
from ...subprocess_git import SubprocessGitBackend

# Re-export helpers that moved to subprocess_git — tests import from here.
# TODO: migrate tests to import from subprocess_git directly, then remove.
from ...subprocess_git import (  # noqa: F401
    _create_askpass_script,
    _cleanup_askpass,
    _sanitize_git_error,
)

_ALLOWED_CLONE_SCHEMES = {'http', 'https', 'git', 'ssh'}
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9._\-/]*$')
# scp-style: user@host:path (no scheme, colon without //)
_SCP_STYLE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._\-]*@[A-Za-z0-9][A-Za-z0-9._\-]*:.+$')


def _validate_git_ref(value: str, label: str = 'value') -> None:
    """Reject values that could be interpreted as git flags."""
    if not value or not _SAFE_NAME_RE.match(value):
        raise HTTPException(status_code=400, detail=f'Invalid {label}: {value!r}')


def _validate_git_url(url: str) -> None:
    """Validate a git remote URL (scheme-based or scp-style)."""
    if _SCP_STYLE_RE.match(url):
        return  # git@github.com:user/repo.git
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_CLONE_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid git URL scheme: {parsed.scheme!r}. '
                   f'Allowed: {", ".join(sorted(_ALLOWED_CLONE_SCHEMES))} or scp-style',
        )


def _creds_from_dict(credentials: dict | None) -> GitCredentials | None:
    """Convert a credentials dict to GitCredentials, or None.

    Returns None if credentials are missing or incomplete to avoid
    activating askpass with blank values.
    """
    if not credentials:
        return None
    username = credentials.get('username')
    password = credentials.get('password')
    if not username or not password:
        return None
    return GitCredentials(username=username, password=password)


def _map_backend_error(e: GitCommandError) -> HTTPException:
    """Map a GitCommandError to an HTTPException."""
    return HTTPException(status_code=500, detail=f'Git error: {e.stderr}')


class GitService:
    """Service class for git operations.

    Validates inputs, delegates to GitBackend, shapes domain results into
    HTTP response dicts, and maps GitBackendError → HTTPException.
    """

    def __init__(self, config: APIConfig, backend: GitBackend | None = None):
        """Initialize the git service.

        Args:
            config: API configuration with workspace_root
            backend: Git backend. Defaults to SubprocessGitBackend.
        """
        self.config = config
        self.backend = backend or SubprocessGitBackend(config.workspace_root)

    def validate_and_relativize(self, path_str: str) -> Path:
        """Validate path and return relative path.

        Args:
            path_str: Path to validate

        Returns:
            Path relative to workspace root

        Raises:
            HTTPException: If path is invalid or outside workspace
        """
        try:
            validated = self.config.validate_path(Path(path_str))
            return validated.relative_to(self.config.workspace_root)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ── Repo state ──

    def is_git_repo(self) -> bool:
        """Check if workspace is a git repository."""
        return self.backend.is_repo()

    def get_status(self) -> dict:
        """Get git repository status.

        Returns:
            dict with is_repo (bool) and files (list of {path, status} dicts)
        """
        is_repo = self.backend.is_repo()
        if not is_repo:
            return {'is_repo': False, 'available': True, 'files': []}
        entries = self.backend.status()
        return {
            'is_repo': True,
            'available': True,
            'files': [dict(e) for e in entries],
        }

    def get_diff(self, path: str) -> dict:
        """Get diff for a specific file against HEAD.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with diff content and path
        """
        rel_path = self.validate_and_relativize(path)
        diff = self.backend.diff(str(rel_path))
        if diff:
            return {'diff': diff, 'path': path}
        return {'diff': '', 'path': path}

    def get_show(self, path: str) -> dict:
        """Get file contents at HEAD.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with content at HEAD (or null if not tracked)
        """
        rel_path = self.validate_and_relativize(path)
        content = self.backend.show(str(rel_path))
        if content is not None:
            return {'content': content, 'path': path}
        return {'content': None, 'path': path, 'error': 'Not in HEAD'}

    # ── Write operations ──

    def init_repo(self) -> dict:
        """Initialize a git repository in the workspace."""
        try:
            self.backend.init()
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'initialized': True}

    def add_files(self, paths: list[str] | None = None) -> dict:
        """Stage files for commit.

        Args:
            paths: Specific file paths to stage. If None, stages all.
                   If empty list, returns without staging.
        """
        if paths is not None and len(paths) == 0:
            return {'staged': False}
        if paths is not None:
            validated = [str(self.validate_and_relativize(p)) for p in paths]
        else:
            validated = None
        self.backend.add(validated)
        return {'staged': True}

    def commit(self, message: str, author_name: str | None = None,
               author_email: str | None = None) -> dict:
        """Create a commit with staged changes."""
        try:
            oid = self.backend.commit(message, author_name, author_email)
            return {'oid': oid}
        except GitCommandError as e:
            if 'nothing to commit' in e.stderr.lower():
                raise HTTPException(status_code=400, detail=f'Git error: {e.stderr}')
            raise _map_backend_error(e)

    def push(self, remote: str = 'origin', branch: str | None = None,
             credentials: dict | None = None) -> dict:
        """Push to a remote."""
        _validate_git_ref(remote, 'remote')
        if branch:
            _validate_git_ref(branch, 'branch')
        creds = _creds_from_dict(credentials)
        try:
            self.backend.push(remote, branch, creds)
        except GitAuthError as e:
            raise HTTPException(status_code=401, detail=f'Authentication failed: {e}')
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'pushed': True}

    def pull(self, remote: str = 'origin', branch: str | None = None,
             credentials: dict | None = None) -> dict:
        """Pull from a remote."""
        _validate_git_ref(remote, 'remote')
        if branch:
            _validate_git_ref(branch, 'branch')
        creds = _creds_from_dict(credentials)
        try:
            self.backend.pull(remote, branch, creds)
        except GitAuthError as e:
            raise HTTPException(status_code=401, detail=f'Authentication failed: {e}')
        except GitConflictError as e:
            raise HTTPException(status_code=409, detail=f'Pull conflict: {e}')
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'pulled': True}

    def clone_repo(self, url: str, branch: str | None = None,
                   credentials: dict | None = None) -> dict:
        """Clone a repository into workspace."""
        _validate_git_url(url)
        if branch:
            _validate_git_ref(branch, 'branch')
        creds = _creds_from_dict(credentials)
        try:
            self.backend.clone(url, branch, creds)
        except GitAuthError as e:
            raise HTTPException(status_code=401, detail=f'Authentication failed: {e}')
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'cloned': True}

    # ── Branch operations ──

    def current_branch(self) -> dict:
        """Get the current branch name."""
        name = self.backend.current_branch_name()
        return {'branch': name}

    def list_branches(self) -> dict:
        """List all local branches."""
        if not self.backend.is_repo():
            return {'branches': [], 'current': None}
        branches, current = self.backend.branches()
        return {'branches': branches, 'current': current}

    def create_branch(self, name: str, checkout: bool = True) -> dict:
        """Create a new branch."""
        _validate_git_ref(name, 'branch name')
        try:
            self.backend.create_branch(name, checkout)
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'created': True, 'branch': name, 'checked_out': checkout}

    def checkout_branch(self, name: str) -> dict:
        """Checkout an existing branch."""
        _validate_git_ref(name, 'branch name')
        try:
            self.backend.checkout(name)
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'checked_out': True, 'branch': name}

    def merge_branch(self, source: str, message: str | None = None) -> dict:
        """Merge a branch into the current branch."""
        _validate_git_ref(source, 'branch name')
        try:
            self.backend.merge(source, message)
        except GitConflictError as e:
            raise HTTPException(
                status_code=409,
                detail=f'Merge conflict: {e}',
            )
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'merged': True, 'source': source}

    def add_remote(self, name: str, url: str) -> dict:
        """Add or update a remote."""
        _validate_git_ref(name, 'remote name')
        _validate_git_url(url)
        try:
            self.backend.add_remote(name, url)
        except GitCommandError as e:
            raise _map_backend_error(e)
        return {'added': True}

    def list_remotes(self) -> dict:
        """List configured remotes."""
        remotes = self.backend.list_remotes()
        return {'remotes': [dict(r) for r in remotes]}
