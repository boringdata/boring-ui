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

        # Get status (porcelain format for stable parsing)
        status = run_git(['status', '--porcelain'])
        files = {}
        for line in status.strip().split('\n'):
            if line:
                # Porcelain format: XY PATH
                # X = index status, Y = working tree status
                status_code = line[:2].strip()
                file_path = line[3:]
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
