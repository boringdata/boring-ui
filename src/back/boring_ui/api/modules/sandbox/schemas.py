"""Schemas for sandbox lifecycle management."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class SandboxStatus(str, Enum):
    """Lifecycle state for a managed sandbox."""

    pending = 'pending'
    running = 'running'
    stopped = 'stopped'
    failed = 'failed'


class SandboxMetadata(BaseModel):
    """Stored metadata for a managed sandbox target."""

    id: str
    name: str
    workspace_id: str | None = None
    owner: str | None = None
    status: SandboxStatus = SandboxStatus.pending
    target_base_url: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSandboxRequest(BaseModel):
    """Request payload for creating a sandbox target."""

    name: str = Field(min_length=1)
    workspace_id: str | None = None
    owner: str | None = None
    target_base_url: str = Field(min_length=1)
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SandboxLifecycleResponse(BaseModel):
    """Response for lifecycle actions."""

    sandbox: SandboxMetadata


class ActiveSandboxResponse(BaseModel):
    """Response for current active sandbox."""

    active_sandbox_id: str | None = None
    sandbox: SandboxMetadata | None = None


class SandboxTargetResolution(BaseModel):
    """Resolved runtime target for dispatch decisions."""

    mode: str
    sandbox_id: str | None = None
    target_base_url: str | None = None
    reason: str
