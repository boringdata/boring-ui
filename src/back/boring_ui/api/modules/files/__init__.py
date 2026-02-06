"""Files module for boring-ui API.

Provides file system operations: read, write, rename, delete, search.
"""
from .router import create_file_router
from .schemas import FileContent, RenameRequest, MoveRequest
from .service import FileService

__all__ = [
    'create_file_router',
    'FileContent',
    'RenameRequest', 
    'MoveRequest',
    'FileService',
]
