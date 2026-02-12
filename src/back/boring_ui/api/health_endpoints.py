"""Structured health and readiness endpoints for sandbox mode.

Provides Kubernetes-style /healthz (liveness) and /readyz (readiness)
endpoints that report dependency states without leaking sensitive
upstream details.

Liveness (/healthz):
  - Always returns 200 if the process is running and responsive.
  - Reports degraded if any non-critical dependency is down.
  - Never returns 5xx (that would trigger restarts).

Readiness (/readyz):
  - Returns 200 only when all critical dependencies are healthy.
  - Returns 503 when not ready to serve traffic.
  - Used by load balancers to exclude unhealthy instances.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DependencyStatus(str, Enum):
    """Status of a single dependency."""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


@dataclass
class DependencyState:
    """Current state of a dependency check."""
    name: str
    status: DependencyStatus = DependencyStatus.UNKNOWN
    message: str = ''
    last_check_ts: float = 0.0
    critical: bool = True  # If True, unhealthy blocks readiness.

    def mark_healthy(self, message: str = '', now: float | None = None) -> None:
        self.status = DependencyStatus.HEALTHY
        self.message = message
        self.last_check_ts = now or time.time()

    def mark_degraded(self, message: str = '', now: float | None = None) -> None:
        self.status = DependencyStatus.DEGRADED
        self.message = message
        self.last_check_ts = now or time.time()

    def mark_unhealthy(self, message: str = '', now: float | None = None) -> None:
        self.status = DependencyStatus.UNHEALTHY
        self.message = message
        self.last_check_ts = now or time.time()


class HealthRegistry:
    """Registry of dependency health states.

    Dependencies register at startup and update their state
    as checks run. The /healthz and /readyz endpoints read
    from this registry.
    """

    def __init__(self) -> None:
        self._deps: dict[str, DependencyState] = {}

    def register(
        self,
        name: str,
        *,
        critical: bool = True,
        initial_status: DependencyStatus = DependencyStatus.UNKNOWN,
    ) -> DependencyState:
        """Register a dependency for health tracking."""
        state = DependencyState(
            name=name, critical=critical, status=initial_status,
        )
        self._deps[name] = state
        return state

    def get(self, name: str) -> DependencyState | None:
        return self._deps.get(name)

    @property
    def all_deps(self) -> list[DependencyState]:
        return list(self._deps.values())

    @property
    def critical_deps(self) -> list[DependencyState]:
        return [d for d in self._deps.values() if d.critical]

    def is_live(self) -> bool:
        """Check liveness: process is running and responsive.

        Always True unless we have an unrecoverable error.
        Degraded dependencies don't affect liveness.
        """
        return True

    def is_ready(self) -> bool:
        """Check readiness: all critical dependencies are healthy.

        Returns False if any critical dependency is unhealthy or unknown.
        """
        for dep in self.critical_deps:
            if dep.status in (DependencyStatus.UNHEALTHY, DependencyStatus.UNKNOWN):
                return False
        return True

    def liveness_response(self) -> dict:
        """Build /healthz response body."""
        overall = 'ok'
        for dep in self._deps.values():
            if dep.status == DependencyStatus.DEGRADED:
                overall = 'degraded'
                break
            if dep.status == DependencyStatus.UNHEALTHY:
                overall = 'degraded'
                break

        return {
            'status': overall,
            'checks': {
                dep.name: {
                    'status': dep.status.value,
                    'message': dep.message,
                }
                for dep in self._deps.values()
            },
        }

    def readiness_response(self) -> tuple[int, dict]:
        """Build /readyz response (status_code, body)."""
        ready = self.is_ready()
        status_code = 200 if ready else 503

        return status_code, {
            'status': 'ready' if ready else 'not_ready',
            'checks': {
                dep.name: {
                    'status': dep.status.value,
                    'critical': dep.critical,
                    'message': dep.message,
                }
                for dep in self._deps.values()
            },
        }


def create_default_registry() -> HealthRegistry:
    """Create a health registry with standard sandbox dependencies."""
    registry = HealthRegistry()
    registry.register('workspace_service', critical=True)
    registry.register('workspace_version', critical=True)
    return registry
