"""Repository and provider protocol interfaces for dependency injection.

Bead: bd-1joj.1 (CP0)

These protocols define the contracts that concrete implementations (InMemory
for local dev, Supabase for non-local) must satisfy. The app factory accepts
any implementation that matches these protocols.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkspaceRepository(Protocol):
    """Workspace CRUD operations."""

    async def get(self, workspace_id: str) -> dict[str, Any] | None: ...
    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]: ...
    async def create(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def update(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


@runtime_checkable
class MemberRepository(Protocol):
    """Workspace membership operations."""

    async def list_members(self, workspace_id: str) -> list[dict[str, Any]]: ...
    async def add_member(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]: ...
    async def remove_member(self, workspace_id: str, member_id: str) -> bool: ...
    async def get_membership(self, workspace_id: str, user_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Active workspace session tracking."""

    async def get_active_workspace(self, user_id: str) -> str | None: ...
    async def set_active_workspace(self, user_id: str, workspace_id: str) -> None: ...


@runtime_checkable
class ShareRepository(Protocol):
    """Share link lifecycle."""

    async def create_share(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_share(self, token: str) -> dict[str, Any] | None: ...
    async def delete_share(self, share_id: str) -> bool: ...
    async def list_shares(self, workspace_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class AuditEmitter(Protocol):
    """Audit event emission."""

    async def emit(self, event_type: str, data: dict[str, Any]) -> None: ...


@runtime_checkable
class JobRepository(Protocol):
    """Provisioning job tracking."""

    async def create_job(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    async def update_job(self, job_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def get_active_job(self, workspace_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class RuntimeMetadataStore(Protocol):
    """Workspace runtime metadata (sandbox name, state, release info)."""

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None: ...
    async def upsert_runtime(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class SandboxProvider(Protocol):
    """Sandbox lifecycle operations (Sprite or local)."""

    async def create_sandbox(self, name: str, **kwargs: Any) -> dict[str, Any]: ...
    async def get_sandbox(self, name: str) -> dict[str, Any] | None: ...
    async def health_check(self, name: str) -> bool: ...
