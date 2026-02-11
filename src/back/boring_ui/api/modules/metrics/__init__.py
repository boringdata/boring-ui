"""Metrics API endpoint for observability dashboards (bd-1pwb.9.3)."""

from fastapi import APIRouter, Request
from typing import Any, Dict
from ...metrics import metrics_collector


def create_metrics_router() -> APIRouter:
    """Create metrics API router."""
    router = APIRouter(prefix="/api/v1", tags=["metrics"])

    @router.get("/metrics")
    async def get_metrics(request: Request) -> Dict[str, Any]:
        """Get current metrics snapshot for dashboards."""
        snapshot = metrics_collector.get_snapshot()
        request_id = getattr(request.state, 'request_id', None)
        if request_id:
            snapshot['request_id'] = request_id
        return snapshot

    return router
