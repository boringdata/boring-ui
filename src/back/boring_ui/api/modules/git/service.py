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
            dict with is_repo (bool) and files (dict of path -> status)
        """
        if not self.is_git_repo():
            return {'is_repo': False, 'files': []}
        
        # Get status (porcelain v1 format for stable parsing)
        status = self.run_git(['status', '--porcelain'])
        files = {}
        for line in status.strip().split('\n'):
            if len(line) >= 3:
                # Check if position 2 is a space (standard XY format)
                # or position 1 is a space (condensed X format)
                if len(line) > 3 and line[2] == ' ':
                    # Standard: XY PATH - path starts at position 3
                    status_code = line[:2].strip()
                    file_path = line[3:]
                else:
                    # Condensed: X PATH - path starts at position 2
                    status_code = line[0]
                    file_path = line[2:] if line[1] == ' ' else line[3:]
                if status_code and file_path:
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
