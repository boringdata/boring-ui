"""Metrics endpoint router for dashboards and monitoring (bd-1pwb.9.3)."""

from fastapi import APIRouter, Request
from typing import Dict, Any

from ..metrics import metrics_collector


def create_metrics_router() -> APIRouter:
    """Create metrics router for dashboard and monitoring access.

    Provides:
    - GET /metrics - Current metrics snapshot for dashboards
    - GET /metrics/health - Health status and SLO compliance
    - GET /metrics/alerts - Active alerts and thresholds

    Returns:
        FastAPI router with metrics endpoints
    """
    router = APIRouter(prefix="/metrics", tags=["observability"])

    @router.get("")
    async def get_metrics() -> Dict[str, Any]:
        """Get current metrics snapshot for dashboards.

        Returns:
            Metrics snapshot including auth, operations, sandbox, and error metrics
        """
        return metrics_collector.get_snapshot()

    @router.get("/health")
    async def get_health() -> Dict[str, Any]:
        """Get service health and SLO compliance.

        Returns:
            Health status with success rates and SLO compliance indicators
        """
        snapshot = metrics_collector.get_snapshot()
        health = snapshot.get("health", {})

        return {
            "status": "healthy" if all([
                health.get("auth_success_rate_percent", 0) > 95,
                health.get("sandbox_health_percent", 0) > 95,
                health.get("error_rate", 0) < 10,
            ]) else "degraded",
            "metrics": health,
            "timestamp": snapshot.get("timestamp"),
        }

    @router.get("/alerts")
    async def get_alerts() -> Dict[str, Any]:
        """Get active alerts and SLO thresholds.

        Returns:
            Active alerts and alert thresholds for monitoring systems
        """
        snapshot = metrics_collector.get_snapshot()
        health = snapshot.get("health", {})
        auth_success_rate = health.get("auth_success_rate_percent", 0)
        sandbox_health = health.get("sandbox_health_percent", 0)
        error_rate = health.get("error_rate", 0)

        alerts = {
            "active_alerts": [],
            "thresholds": {
                "auth_success_rate_percent": 95,
                "sandbox_health_percent": 95,
                "error_rate_max": 10,
                "proxy_latency_p99_ms": 2000,
                "file_operation_latency_p99_ms": 5000,
            },
        }

        # Populate active alerts
        if auth_success_rate < 95:
            alerts["active_alerts"].append({
                "name": "auth_success_rate_low",
                "severity": "critical" if auth_success_rate < 90 else "warning",
                "message": f"Auth success rate {auth_success_rate:.1f}%",
                "runbook": "OPERATIONAL_RUNBOOKS.md#alert-high-authentication-failure-rate",
            })

        if sandbox_health < 95:
            alerts["active_alerts"].append({
                "name": "sandbox_health_low",
                "severity": "critical" if sandbox_health < 90 else "warning",
                "message": f"Sandbox health {sandbox_health:.1f}%",
                "runbook": "OPERATIONAL_RUNBOOKS.md#alert-sandbox-operation-failures",
            })

        if error_rate > 10:
            alerts["active_alerts"].append({
                "name": "error_rate_high",
                "severity": "critical" if error_rate > 20 else "warning",
                "message": f"Error count: {int(error_rate)}",
                "runbook": "OPERATIONAL_RUNBOOKS.md#incident-response-checklist",
            })

        auth_ops = snapshot.get("operations", {}).get("file", {})
        if auth_ops.get("success_rate_percent", 100) < 99:
            alerts["active_alerts"].append({
                "name": "file_operation_errors",
                "severity": "warning",
                "message": f"File op success rate {auth_ops.get('success_rate_percent', 0):.1f}%",
                "runbook": "OPERATIONAL_RUNBOOKS.md#alert-high-file-operation-latency",
            })

        return alerts

    return router
