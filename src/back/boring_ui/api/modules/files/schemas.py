"""Pydantic schemas for file operations."""
from pydantic import BaseModel


class FileContent(BaseModel):
    """Request body for file content."""
    content: str


class RenameRequest(BaseModel):
    """Request body for file rename."""
    old_path: str
    new_path: str


class MoveRequest(BaseModel):
    """Request body for file move."""
    src_path: str
    dest_dir: str
