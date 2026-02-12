"""Canonical /api/v1 contract definitions for boring-ui (bd-1pwb.6.1).

Pydantic models define the stable contract for:
- File operations
- Git operations
- Exec operations
- Error responses

These contracts are used for:
- Schema validation at API boundaries
- OpenAPI documentation generation
- Client code generation
- Migration/versioning strategy
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# File Operations (bd-1pwb.6.1)
# ============================================================================

class FileInfo(BaseModel):
    """Metadata about a file or directory."""

    model_config = {"json_schema_extra": {
        "example": {
            "name": "app.py",
            "type": "file",
            "size": 1024,
        }
    }}

    name: str = Field(..., description="File or directory name")
    type: str = Field(..., description="'file' or 'dir'")
    size: Optional[int] = Field(None, description="File size in bytes (null for directories)")


class ListFilesRequest(BaseModel):
    """Request to list files in a directory."""
    path: str = Field(default=".", description="Path relative to workspace")


class ListFilesResponse(BaseModel):
    """Response with list of files."""

    model_config = {"json_schema_extra": {
        "example": {
            "path": ".",
            "files": [
                {"name": "app.py", "type": "file", "size": 1024},
                {"name": "src", "type": "dir", "size": None},
            ],
        }
    }}

    files: List[FileInfo] = Field(..., description="List of files")
    path: str = Field(..., description="Listed directory path")


class ReadFileResponse(BaseModel):
    """Response with file contents."""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="File contents")
    size: int = Field(..., description="File size in bytes")


class WriteFileRequest(BaseModel):
    """Request to write file."""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="File contents to write")


class WriteFileResponse(BaseModel):
    """Response after writing file."""
    path: str = Field(..., description="File path written")
    size: int = Field(..., description="Bytes written")
    written: bool = Field(True, description="Operation success")


# ============================================================================
# Git Operations (bd-1pwb.6.1)
# ============================================================================

class GitStatusResponse(BaseModel):
    """Git repository status."""
    branch: str = Field(..., description="Current branch")
    staged: List[str] = Field(default_factory=list, description="Staged files")
    unstaged: List[str] = Field(default_factory=list, description="Unstaged files")
    untracked: List[str] = Field(default_factory=list, description="Untracked files")
    clean: bool = Field(..., description="True if no changes")


class GitDiffStats(BaseModel):
    """Diff statistics."""
    insertions: int = Field(0, description="Lines added")
    deletions: int = Field(0, description="Lines removed")
    files_changed: int = Field(0, description="Files with changes")


class GitDiffResponse(BaseModel):
    """Git diff output."""
    context: str = Field(..., description="'working', 'staged', or 'head'")
    diff: str = Field(..., description="Unified diff output")
    stats: GitDiffStats = Field(..., description="Diff statistics")


class GitShowResponse(BaseModel):
    """Git show output for a specific file."""
    path: str = Field(..., description="File path")
    content: Optional[str] = Field(None, description="File content at HEAD")
    is_new: bool = Field(False, description="True if file is new (not in HEAD)")


# ============================================================================
# Exec Operations (bd-1pwb.6.1)
# ============================================================================

class ExecRunRequest(BaseModel):
    """Request to execute command."""
    command: str = Field(..., description="Command to execute (no shell expansion)")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Timeout in seconds (1-300)")


class ExecRunResponse(BaseModel):
    """Response from command execution."""
    command: str = Field(..., description="Command executed")
    exit_code: int = Field(..., description="Process exit code")
    timeout_seconds: int = Field(..., description="Timeout used")
    status: str = Field(..., description="'completed' or 'timeout'")
    stdout: Optional[str] = Field(None, description="Standard output (optional)")
    stderr: Optional[str] = Field(None, description="Standard error (optional)")


# ============================================================================
# Error Response (bd-1pwb.6.1)
# ============================================================================

class ErrorCode(str, Enum):
    """Canonical error codes."""
    
    # Authentication (401)
    AUTH_MISSING = "AUTH_MISSING"
    AUTH_INVALID = "AUTH_INVALID"
    
    # Authorization (403)
    AUTHZ_INSUFFICIENT = "AUTHZ_INSUFFICIENT"
    
    # Validation (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    
    # Not Found (404)
    NOT_FOUND = "NOT_FOUND"
    
    # Server (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # Gateway (502)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorResponse(BaseModel):
    """Canonical error response structure."""
    
    code: ErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    request_id: Optional[str] = Field(None, description="Request correlation ID")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    model_config = {"json_schema_extra": {
        "example": {
            "code": "AUTH_MISSING",
            "message": "Missing or invalid authorization header",
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "details": None,
        }
    }}
