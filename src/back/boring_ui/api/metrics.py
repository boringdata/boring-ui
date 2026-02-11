"""Metrics collection and dashboarding for boring-ui observability (bd-1pwb.9.3).

Provides comprehensive metrics for:
- Authentication (success/failure rates)
- Authorization (denial rates)
- Operations (file, git, exec latency)
- Sandbox operations (startup time, health)
- System health (uptime, error rates)

Metrics are designed for:
- Real-time dashboards (Grafana, CloudWatch, etc.)
- SLO monitoring and alerting
- Incident diagnosis and remediation
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from collections import defaultdict


@dataclass
class OperationMetrics:
    """Metrics for a specific operation type."""
    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0

    def record(self, latency_ms: float, success: bool = True):
        """Record a single operation."""
        self.count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.count if self.count > 0 else 0.0

    @property
    def success_rate(self) -> float:
        return (self.success_count / self.count * 100) if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate_percent": round(self.success_rate, 2),
            "latency_ms": {
                "avg": round(self.avg_latency_ms, 2),
                "min": round(self.min_latency_ms, 2) if self.min_latency_ms != float('inf') else 0,
                "max": round(self.max_latency_ms, 2),
                "total": round(self.total_latency_ms, 2),
            },
        }


class MetricsCollector:
    """Centralized metrics collection for observability (bd-1pwb.9.3)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = datetime.now(timezone.utc)

        # Auth metrics
        self.auth_success_count = 0
        self.auth_failure_count = 0
        self.auth_failure_reasons: Dict[str, int] = defaultdict(int)

        # Authz metrics
        self.authz_denied_count = 0
        self.authz_denied_reasons: Dict[str, int] = defaultdict(int)

        # Operation metrics
        self.file_operations = OperationMetrics()
        self.git_operations = OperationMetrics()
        self.exec_operations = OperationMetrics()
        self.proxy_operations = OperationMetrics()

        # Sandbox metrics
        self.sandbox_start_count = 0
        self.sandbox_start_latencies_ms: List[float] = []
        self.sandbox_health_checks_count = 0
        self.sandbox_health_checks_passed = 0

        # Error tracking
        self.error_count = 0
        self.error_types: Dict[str, int] = defaultdict(int)

    def record_auth_success(self):
        with self._lock:
            self.auth_success_count += 1

    def record_auth_failure(self, reason: str = "unknown"):
        with self._lock:
            self.auth_failure_count += 1
            self.auth_failure_reasons[reason] += 1

    def record_authz_denied(self, reason: str = "unknown"):
        with self._lock:
            self.authz_denied_count += 1
            self.authz_denied_reasons[reason] += 1

    def record_file_operation(self, latency_ms: float, success: bool = True):
        with self._lock:
            self.file_operations.record(latency_ms, success)

    def record_git_operation(self, latency_ms: float, success: bool = True):
        with self._lock:
            self.git_operations.record(latency_ms, success)

    def record_exec_operation(self, latency_ms: float, success: bool = True):
        with self._lock:
            self.exec_operations.record(latency_ms, success)

    def record_proxy_operation(self, latency_ms: float, success: bool = True):
        with self._lock:
            self.proxy_operations.record(latency_ms, success)

    def record_sandbox_startup(self, latency_ms: float, success: bool = True):
        with self._lock:
            self.sandbox_start_count += 1
            if success:
                self.sandbox_start_latencies_ms.append(latency_ms)

    def record_sandbox_health_check(self, passed: bool = True):
        with self._lock:
            self.sandbox_health_checks_count += 1
            if passed:
                self.sandbox_health_checks_passed += 1

    def record_error(self, error_type: str = "unknown"):
        with self._lock:
            self.error_count += 1
            self.error_types[error_type] += 1

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            total_auth = self.auth_success_count + self.auth_failure_count
            auth_success_rate = (self.auth_success_count / total_auth * 100) if total_auth > 0 else 0
            sandbox_health = (self.sandbox_health_checks_passed / self.sandbox_health_checks_count * 100) if self.sandbox_health_checks_count > 0 else 0
            avg_sandbox_startup = sum(self.sandbox_start_latencies_ms) / len(self.sandbox_start_latencies_ms) if self.sandbox_start_latencies_ms else 0

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": round(uptime_seconds, 2),
                "health": {
                    "auth_success_rate_percent": round(auth_success_rate, 2),
                    "authz_denial_rate_percent": round((self.authz_denied_count / total_auth * 100) if total_auth > 0 else 0, 2),
                    "sandbox_health_percent": round(sandbox_health, 2),
                    "error_rate": self.error_count,
                },
                "authentication": {
                    "success": self.auth_success_count,
                    "failure": self.auth_failure_count,
                    "failure_reasons": dict(self.auth_failure_reasons),
                    "total": total_auth,
                },
                "authorization": {
                    "denied": self.authz_denied_count,
                    "denial_reasons": dict(self.authz_denied_reasons),
                },
                "operations": {
                    "file": self.file_operations.to_dict(),
                    "git": self.git_operations.to_dict(),
                    "exec": self.exec_operations.to_dict(),
                    "proxy": self.proxy_operations.to_dict(),
                },
                "sandbox": {
                    "startups": self.sandbox_start_count,
                    "avg_startup_latency_ms": round(avg_sandbox_startup, 2),
                    "health_checks_passed": self.sandbox_health_checks_passed,
                    "health_checks_total": self.sandbox_health_checks_count,
                },
                "errors": {
                    "total": self.error_count,
                    "by_type": dict(self.error_types),
                },
            }


metrics_collector = MetricsCollector()
