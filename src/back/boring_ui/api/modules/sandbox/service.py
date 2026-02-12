"""Sandbox metadata storage, lifecycle service, and target resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException

from .schemas import (
    ActiveSandboxResponse,
    CreateSandboxRequest,
    SandboxLifecycleResponse,
    SandboxMetadata,
    SandboxStatus,
    SandboxTargetResolution,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SandboxStore(ABC):
    """Persistence contract for sandbox metadata."""

    @abstractmethod
    def list(self) -> list[SandboxMetadata]:
        raise NotImplementedError

    @abstractmethod
    def get(self, sandbox_id: str) -> SandboxMetadata | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, sandbox: SandboxMetadata) -> SandboxMetadata:
        raise NotImplementedError

    @abstractmethod
    def active_id(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def set_active_id(self, sandbox_id: str | None) -> None:
        raise NotImplementedError


class InMemorySandboxStore(SandboxStore):
    """Thread-safe in-memory metadata store for sandbox records."""

    def __init__(self) -> None:
        self._items: dict[str, SandboxMetadata] = {}
        self._active_id: str | None = None
        self._lock = RLock()

    def list(self) -> list[SandboxMetadata]:
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._items.values()),
                key=lambda item: item.created_at,
            )

    def get(self, sandbox_id: str) -> SandboxMetadata | None:
        with self._lock:
            item = self._items.get(sandbox_id)
            return item.model_copy(deep=True) if item else None

    def save(self, sandbox: SandboxMetadata) -> SandboxMetadata:
        with self._lock:
            self._items[sandbox.id] = sandbox.model_copy(deep=True)
            return sandbox.model_copy(deep=True)

    def active_id(self) -> str | None:
        with self._lock:
            return self._active_id

    def set_active_id(self, sandbox_id: str | None) -> None:
        with self._lock:
            self._active_id = sandbox_id


class SandboxService:
    """Lifecycle operations for sandbox metadata records."""

    def __init__(self, store: SandboxStore) -> None:
        self._store = store

    def create(self, request: CreateSandboxRequest) -> SandboxLifecycleResponse:
        sandbox = SandboxMetadata(
            id=str(uuid4()),
            name=request.name,
            workspace_id=request.workspace_id,
            owner=request.owner,
            status=SandboxStatus.pending,
            target_base_url=request.target_base_url,
            labels=dict(request.labels),
            metadata=dict(request.metadata),
        )
        saved = self._store.save(sandbox)

        # First sandbox becomes active by default for deterministic resolution.
        if self._store.active_id() is None:
            self._store.set_active_id(saved.id)

        return SandboxLifecycleResponse(sandbox=saved)

    def list(self) -> list[SandboxMetadata]:
        return self._store.list()

    def get(self, sandbox_id: str) -> SandboxMetadata:
        sandbox = self._store.get(sandbox_id)
        if not sandbox:
            raise HTTPException(status_code=404, detail='sandbox_not_found')
        return sandbox

    def start(self, sandbox_id: str) -> SandboxLifecycleResponse:
        sandbox = self.get(sandbox_id)
        now = _now()
        sandbox.status = SandboxStatus.running
        sandbox.started_at = now
        sandbox.updated_at = now
        saved = self._store.save(sandbox)
        return SandboxLifecycleResponse(sandbox=saved)

    def stop(self, sandbox_id: str) -> SandboxLifecycleResponse:
        sandbox = self.get(sandbox_id)
        now = _now()
        sandbox.status = SandboxStatus.stopped
        sandbox.stopped_at = now
        sandbox.updated_at = now
        saved = self._store.save(sandbox)

        if self._store.active_id() == sandbox_id:
            self._store.set_active_id(None)

        return SandboxLifecycleResponse(sandbox=saved)

    def activate(self, sandbox_id: str) -> ActiveSandboxResponse:
        sandbox = self.get(sandbox_id)
        self._store.set_active_id(sandbox.id)
        return ActiveSandboxResponse(active_sandbox_id=sandbox.id, sandbox=sandbox)

    def get_active(self) -> ActiveSandboxResponse:
        active_id = self._store.active_id()
        if not active_id:
            return ActiveSandboxResponse(active_sandbox_id=None, sandbox=None)
        sandbox = self._store.get(active_id)
        if not sandbox:
            self._store.set_active_id(None)
            return ActiveSandboxResponse(active_sandbox_id=None, sandbox=None)
        return ActiveSandboxResponse(active_sandbox_id=active_id, sandbox=sandbox)


@dataclass
class TargetResolver:
    """Resolve runtime target from managed sandbox metadata."""

    store: SandboxStore

    def resolve(
        self,
        sandbox_id: str | None = None,
        workspace_id: str | None = None,
    ) -> SandboxTargetResolution:
        if sandbox_id:
            sandbox = self.store.get(sandbox_id)
            if not sandbox:
                raise HTTPException(status_code=404, detail='sandbox_not_found')
            return SandboxTargetResolution(
                mode='sandbox',
                sandbox_id=sandbox.id,
                target_base_url=sandbox.target_base_url,
                reason='explicit_sandbox_id',
            )

        active_id = self.store.active_id()
        if active_id:
            sandbox = self.store.get(active_id)
            if sandbox:
                return SandboxTargetResolution(
                    mode='sandbox',
                    sandbox_id=sandbox.id,
                    target_base_url=sandbox.target_base_url,
                    reason='active_sandbox',
                )

        if workspace_id:
            for sandbox in self.store.list():
                if sandbox.workspace_id == workspace_id:
                    return SandboxTargetResolution(
                        mode='sandbox',
                        sandbox_id=sandbox.id,
                        target_base_url=sandbox.target_base_url,
                        reason='workspace_match',
                    )

        return SandboxTargetResolution(
            mode='local',
            sandbox_id=None,
            target_base_url=None,
            reason='no_sandbox_selected',
        )
