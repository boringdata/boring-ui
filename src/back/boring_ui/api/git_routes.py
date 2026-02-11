"""Git operation routes for boring-ui API."""
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException
from .config import APIConfig


def create_git_router(config: APIConfig) -> APIRouter:
    """Create git operations router.

    Args:
        config: API configuration with workspace_root

    Returns:
        FastAPI router with git endpoints
    """
    router = APIRouter(tags=['git'])

    def validate_and_relativize(path_str: str) -> Path:
        """Validate path and return relative path.

        Args:
            path_str: Path to validate

        Returns:
            Path relative to workspace root

        Raises:
            HTTPException: If path is invalid or outside workspace
        """
        try:
            validated = config.validate_path(Path(path_str))
            return validated.relative_to(config.workspace_root)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def run_git(args: list[str]) -> str:
        """Run git command in workspace.

        Args:
            args: Git command arguments (without 'git' prefix)

        Returns:
            stdout from git command

        Raises:
            HTTPException: If git command fails
        """
        result = subprocess.run(
            ['git'] + args,
            cwd=config.workspace_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f'Git error: {result.stderr.strip()}'
            )
        return result.stdout

    @router.get('/status')
    async def get_status():
        """Get git repository status.

        Returns:
            dict with is_repo (bool) and files (list of status entries)
        """
        # Check if it's a git repo
        try:
            run_git(['rev-parse', '--git-dir'])
        except HTTPException:
            return {'is_repo': False, 'files': []}

        # Get status (porcelain v1 format for stable parsing)
        # Standard format: XY PATH (XY = 2-char status, space, path)
        # X = index status, Y = worktree status
        status = run_git(['status', '--porcelain'])
        files = {}

        # Priority for status codes (higher = more important, don't overwrite)
        # Staged statuses (D, A, M in index) take precedence over untracked
        status_priority = {'C': 5, 'D': 4, 'A': 3, 'M': 2, 'U': 1}

        def normalize_status(raw: str) -> str:
            """Convert git XY status to single-char frontend status.

            Returns: M (Modified), A (Added), D (Deleted), ?? (Untracked), C (Conflict)
            """
            raw = raw.strip()
            # Untracked files (standard '??' or condensed '?' format)
            if raw in ('??', '?'):
                return '??'
            # Merge conflicts (unmerged states)
            # UU=both modified, AA=both added, DD=both deleted
            # DU/UD/AU/UA = various conflict combinations
            if raw in ('UU', 'AA', 'DD', 'DU', 'UD', 'AU', 'UA'):
                return 'C'
            # Deleted
            if raw in ('D', 'D ', ' D'):
                return 'D'
            # Added
            if raw in ('A', 'A ', ' A'):
                return 'A'
            # Modified (including MM - modified in both index and worktree)
            if raw in ('M', 'M ', ' M', 'MM'):
                return 'M'
            # Renamed (show as modified for simplicity)
            if raw.startswith('R'):
                return 'M'
            # Copied (show as added since it's a new file)
            if raw.startswith('C'):
                return 'A'
            # Default: use first non-space character if recognized
            # Note: Don't match 'C' here as it's git's copy status, not conflict
            for c in raw:
                if c in 'MADU':
                    return c
                if c != ' ':
                    break
            return 'M'  # Fallback to modified for unknown

        for line in status.strip().split('\n'):
            if len(line) >= 3:
                # Check if position 2 is a space (standard XY format)
                if len(line) > 3 and line[2] == ' ':
                    # Standard: XY PATH - path starts at position 3
                    raw_status = line[:2]
                    file_path = line[3:]
                else:
                    # Condensed: X PATH - path starts at position 2
                    raw_status = line[0]
                    file_path = line[2:] if line[1] == ' ' else line[3:]

                # Handle rename/copy paths: "old -> new" format
                # Git porcelain shows these as "R  old -> new" or "C  old -> new"
                # We want the new (destination) path for display
                # Only split for actual rename/copy statuses to avoid breaking
                # filenames that legitimately contain " -> "
                if raw_status.startswith(('R', 'C')) and ' -> ' in file_path:
                    file_path = file_path.split(' -> ')[-1]

                if raw_status and file_path:
                    status_code = normalize_status(raw_status)
                    # Don't overwrite higher-priority status
                    # (e.g., D should not be overwritten by U from ?? line)
                    existing = files.get(file_path)
                    if existing is None or status_priority.get(status_code, 0) > status_priority.get(existing, 0):
                        files[file_path] = status_code

        return {
            'is_repo': True,
            'available': True,  # Compatibility with frontend
            'files': files,
        }

    @router.get('/diff')
    async def get_diff(path: str):
        """Get diff for a specific file against HEAD.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with diff content and path
        """
        rel_path = validate_and_relativize(path)

        try:
            diff = run_git(['diff', 'HEAD', '--', str(rel_path)])
            return {'diff': diff, 'path': path}
        except HTTPException as e:
            # File might be untracked
            return {'diff': '', 'path': path, 'error': str(e.detail)}

    @router.get('/show')
    async def get_show(path: str):
        """Get file contents at HEAD.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with content at HEAD (or null if not tracked)
        """
        rel_path = validate_and_relativize(path)

        try:
            content = run_git(['show', f'HEAD:{rel_path}'])
            return {'content': content, 'path': path}
        except HTTPException:
            return {'content': None, 'path': path, 'error': 'Not in HEAD'}

    return router
