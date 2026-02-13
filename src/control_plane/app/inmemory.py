"""In-memory repository implementations for local development.

Bead: bd-1joj.1 (CP0)

These are used when ENVIRONMENT=local. They satisfy the protocol interfaces
but store everything in dicts (no persistence across restarts).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[str, dict[str, Any]] = {}

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        return self._workspaces.get(workspace_id)

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [
            ws for ws in self._workspaces.values()
            if ws.get("owner_id") == user_id
        ]

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        ws_id = data.get("id") or f"ws_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        workspace = {"id": ws_id, "created_at": now, "updated_at": now, **data}
        self._workspaces[ws_id] = workspace
        return workspace

    async def update(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if workspace_id not in self._workspaces:
            return None
        now = datetime.now(timezone.utc).isoformat()
        self._workspaces[workspace_id].update({**data, "updated_at": now})
        return self._workspaces[workspace_id]


class InMemoryMemberRepository:
    def __init__(self) -> None:
        self._members: dict[str, list[dict[str, Any]]] = {}

    async def list_members(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._members.get(workspace_id, [])

    async def add_member(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
        member_id = data.get("id") or f"mem_{uuid.uuid4().hex[:8]}"
        member = {"id": member_id, "workspace_id": workspace_id, **data}
        self._members.setdefault(workspace_id, []).append(member)
        return member

    async def remove_member(self, workspace_id: str, member_id: str) -> bool:
        members = self._members.get(workspace_id, [])
        for i, m in enumerate(members):
            if m["id"] == member_id:
                members.pop(i)
                return True
        return False

    async def get_membership(self, workspace_id: str, user_id: str) -> dict[str, Any] | None:
        for m in self._members.get(workspace_id, []):
            if m.get("user_id") == user_id:
                return m
        return None


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._active: dict[str, str] = {}

    async def get_active_workspace(self, user_id: str) -> str | None:
        return self._active.get(user_id)

    async def set_active_workspace(self, user_id: str, workspace_id: str) -> None:
        self._active[user_id] = workspace_id


class InMemoryShareRepository:
    def __init__(self) -> None:
        self._shares: dict[str, dict[str, Any]] = {}
        self._by_token: dict[str, str] = {}

    async def create_share(self, data: dict[str, Any]) -> dict[str, Any]:
        share_id = data.get("id") or f"shr_{uuid.uuid4().hex[:8]}"
        token = data.get("token") or uuid.uuid4().hex
        share = {"id": share_id, "token": token, **data}
        self._shares[share_id] = share
        self._by_token[token] = share_id
        return share

    async def get_share(self, token: str) -> dict[str, Any] | None:
        share_id = self._by_token.get(token)
        if share_id:
            return self._shares.get(share_id)
        return None

    async def delete_share(self, share_id: str) -> bool:
        share = self._shares.pop(share_id, None)
        if share:
            self._by_token.pop(share.get("token", ""), None)
            return True
        return False

    async def list_shares(self, workspace_id: str) -> list[dict[str, Any]]:
        return [
            s for s in self._shares.values()
            if s.get("workspace_id") == workspace_id
        ]


class InMemoryAuditEmitter:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append({"type": event_type, **data})


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    async def create_job(self, data: dict[str, Any]) -> dict[str, Any]:
        job_id = data.get("id") or f"job_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        job = {"id": job_id, "created_at": now, "updated_at": now, **data}
        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._jobs.get(job_id)

    async def update_job(self, job_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if job_id not in self._jobs:
            return None
        now = datetime.now(timezone.utc).isoformat()
        self._jobs[job_id].update({**data, "updated_at": now})
        return self._jobs[job_id]

    async def get_active_job(self, workspace_id: str) -> dict[str, Any] | None:
        for job in self._jobs.values():
            if job.get("workspace_id") == workspace_id and job.get("state") not in ("ready", "error"):
                return job
        return None


class InMemoryRuntimeMetadataStore:
    def __init__(self) -> None:
        self._runtimes: dict[str, dict[str, Any]] = {}

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None:
        return self._runtimes.get(workspace_id)

    async def upsert_runtime(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        existing = self._runtimes.get(workspace_id, {"workspace_id": workspace_id})
        existing.update({**data, "updated_at": now})
        self._runtimes[workspace_id] = existing
        return existing


class InMemorySandboxProvider:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, Any]] = {}

    async def create_sandbox(self, name: str, **kwargs: Any) -> dict[str, Any]:
        sandbox = {"name": name, "state": "running", **kwargs}
        self._sandboxes[name] = sandbox
        return sandbox

    async def get_sandbox(self, name: str) -> dict[str, Any] | None:
        return self._sandboxes.get(name)

    async def health_check(self, name: str) -> bool:
        return name in self._sandboxes
