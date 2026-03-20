"""Pydantic schemas for command execution."""
from pydantic import BaseModel


class ExecRequest(BaseModel):
    """Request body for command execution."""
    command: str
    cwd: str | None = None


class ExecResponse(BaseModel):
    """Response body for command execution."""
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
