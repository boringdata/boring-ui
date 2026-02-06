"""Git operations service for boring-ui API."""
import subprocess
from pathlib import Path
from fastapi import HTTPException

from ...config import APIConfig


class GitService:
    """Service class for git operations.
    
    Handles git command execution and path validation.
    """
    
    def __init__(self, config: APIConfig):
        """Initialize the git service.
        
        Args:
            config: API configuration with workspace_root
        """
        self.config = config
    
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
    
    def run_git(self, args: list[str]) -> str:
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
            cwd=self.config.workspace_root,
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
    
    def is_git_repo(self) -> bool:
        """Check if workspace is a git repository.
        
        Returns:
            True if workspace is a git repo, False otherwise
        """
        try:
            self.run_git(['rev-parse', '--git-dir'])
            return True
        except HTTPException:
            return False
    
    def get_status(self) -> dict:
        """Get git repository status.

        Returns:
            dict with is_repo (bool) and files (dict of path -> normalized status)
        """
        if not self.is_git_repo():
            return {'is_repo': False, 'files': []}

        # Get status (porcelain v1 format for stable parsing)
        status = self.run_git(['status', '--porcelain'])
        files = {}

        # Priority for status codes (higher = more important, don't overwrite)
        status_priority = {'C': 5, 'D': 4, 'A': 3, 'M': 2, 'U': 1}

        def normalize_status(raw: str) -> str:
            """Convert git XY status to single-char frontend status.

            Returns: M (Modified), A (Added), D (Deleted), U (Untracked), C (Conflict)
            """
            raw = raw.strip()
            # Untracked files (standard '??' or condensed '?' format)
            if raw in ('??', '?'):
                return 'U'
            # Merge conflicts (unmerged states)
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
                # Only split for actual rename/copy statuses
                if raw_status.startswith(('R', 'C')) and ' -> ' in file_path:
                    file_path = file_path.split(' -> ')[-1]

                if raw_status and file_path:
                    status_code = normalize_status(raw_status)
                    # Don't overwrite higher-priority status
                    existing = files.get(file_path)
                    if existing is None or status_priority.get(status_code, 0) > status_priority.get(existing, 0):
                        files[file_path] = status_code

        return {
            'is_repo': True,
            'available': True,  # Compatibility with frontend
            'files': files,
        }
    
    def get_diff(self, path: str) -> dict:
        """Get diff for a specific file against HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with diff content and path
        """
        rel_path = self.validate_and_relativize(path)
        
        try:
            diff = self.run_git(['diff', 'HEAD', '--', str(rel_path)])
            return {'diff': diff, 'path': path}
        except HTTPException as e:
            # File might be untracked
            return {'diff': '', 'path': path, 'error': str(e.detail)}
    
    def get_show(self, path: str) -> dict:
        """Get file contents at HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with content at HEAD (or null if not tracked)
        """
        rel_path = self.validate_and_relativize(path)
        
        try:
            content = self.run_git(['show', f'HEAD:{rel_path}'])
            return {'content': content, 'path': path}
        except HTTPException:
            return {'content': None, 'path': path, 'error': 'Not in HEAD'}
