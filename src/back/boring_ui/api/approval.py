"""Approval workflow for boring-ui API."""
import uuid
from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    """Request body for creating an approval request."""
    tool_name: str
    description: str
    command: str | None = None
    metadata: dict[str, Any] | None = None


class DecisionRequest(BaseModel):
    """Request body for submitting a decision."""
    request_id: str
    decision: str  # 'approve' or 'deny'
    reason: str | None = None


class ApprovalStore(ABC):
    """Abstract approval storage interface.

    Implementations can use memory, Redis, SQLite, etc.
    The default InMemoryApprovalStore works for single-process deployments.

    Note: In-memory store doesn't persist across restarts or work with
    multiple workers. Document this limitation clearly.
    """

    @abstractmethod
    async def create(self, request_id: str, data: dict[str, Any]) -> None:
        """Create a pending approval request."""
        ...

    @abstractmethod
    async def get(self, request_id: str) -> dict[str, Any] | None:
        """Get approval request by ID."""
        ...

    @abstractmethod
    async def update(self, request_id: str, decision: str, reason: str | None = None) -> None:
        """Update approval with decision (approve/deny)."""
        ...

    @abstractmethod
    async def list_pending(self) -> list[dict[str, Any]]:
        """List all pending approval requests."""
        ...

    @abstractmethod
    async def delete(self, request_id: str) -> bool:
        """Delete an approval request. Returns True if deleted."""
        ...


class InMemoryApprovalStore(ApprovalStore):
    """In-memory approval store.

    WARNING: Does not persist across restarts or work with multiple workers.
    Use only for development or single-process deployments.
    """

    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    async def create(self, request_id: str, data: dict[str, Any]) -> None:
        self._store[request_id] = {
            **data,
            'id': request_id,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat(),
        }

    async def get(self, request_id: str) -> dict[str, Any] | None:
        return self._store.get(request_id)

    async def update(self, request_id: str, decision: str, reason: str | None = None) -> None:
        if request_id in self._store:
            self._store[request_id]['status'] = decision
            self._store[request_id]['reason'] = reason
            self._store[request_id]['decided_at'] = datetime.now(timezone.utc).isoformat()

    async def list_pending(self) -> list[dict[str, Any]]:
        return [v for v in self._store.values() if v['status'] == 'pending']

    async def delete(self, request_id: str) -> bool:
        if request_id in self._store:
            del self._store[request_id]
            return True
        return False


def create_approval_router(store: ApprovalStore) -> APIRouter:
    """Create approval workflow router.

    Args:
        store: ApprovalStore implementation for persistence

    Returns:
        FastAPI router with approval endpoints
    """
    router = APIRouter(tags=['approval'])

    @router.post('/approval/request')
    async def create_request(body: ApprovalRequest):
        """Create a new approval request.

        Args:
            body: Approval request details

        Returns:
            dict with request_id
        """
        request_id = str(uuid.uuid4())
        await store.create(request_id, body.model_dump())
        return {'request_id': request_id, 'status': 'pending'}

    @router.get('/approval/pending')
    async def list_pending():
        """List all pending approval requests.

        Returns:
            dict with pending list
        """
        pending = await store.list_pending()
        return {'pending': pending, 'count': len(pending)}

    @router.post('/approval/decision')
    async def submit_decision(body: DecisionRequest):
        """Submit a decision for an approval request.

        Args:
            body: Decision details (request_id, decision, optional reason)

        Returns:
            dict with success status
        """
        if body.decision not in ('approve', 'deny'):
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'approve' or 'deny'"
            )

        existing = await store.get(body.request_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f'Approval request not found: {body.request_id}'
            )

        if existing['status'] != 'pending':
            raise HTTPException(
                status_code=409,
                detail=f'Request already decided: {existing["status"]}'
            )

        await store.update(body.request_id, body.decision, body.reason)
        return {'success': True, 'request_id': body.request_id, 'decision': body.decision}

    @router.get('/approval/status/{request_id}')
    async def get_status(request_id: str):
        """Get status of an approval request.

        Args:
            request_id: ID of the approval request

        Returns:
            Full approval request data
        """
        data = await store.get(request_id)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f'Approval request not found: {request_id}'
            )
        return data

    @router.delete('/approval/{request_id}')
    async def delete_request(request_id: str):
        """Delete an approval request.

        Args:
            request_id: ID of the approval request

        Returns:
            dict with success status
        """
        deleted = await store.delete(request_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f'Approval request not found: {request_id}'
            )
        return {'success': True, 'request_id': request_id}

    return router
