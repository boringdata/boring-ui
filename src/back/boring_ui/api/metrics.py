"""Core sandbox metrics for observability.

Provides lightweight in-process metrics collection for:
  - Proxy request latency and status distribution
  - Exec session lifecycle events
  - WebSocket connection/disconnection counts
  - Health check latency and failure rates
  - Readiness state transitions

Metrics are exposed via /metrics endpoint in a simple JSON format
suitable for scraping by monitoring tools.

Note: This is a V0 implementation using in-process counters.
Production deployments should use Prometheus client or similar.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class LatencyHistogram:
    """Simple latency histogram with fixed buckets.

    Tracks count, sum, and bucket distribution of latency values.
    """
    buckets: tuple[float, ...] = (
        0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
    )
    _count: int = 0
    _sum: float = 0.0
    _bucket_counts: dict[float, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self):
        if not self._bucket_counts:
            self._bucket_counts = {b: 0 for b in self.buckets}

    def observe(self, value: float) -> None:
        """Record a latency value."""
        with self._lock:
            self._count += 1
            self._sum += value
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] = self._bucket_counts.get(bucket, 0) + 1

    @property
    def count(self) -> int:
        return self._count

    @property
    def total(self) -> float:
        return self._sum

    @property
    def avg(self) -> float:
        return self._sum / self._count if self._count else 0.0

    def snapshot(self) -> dict:
        """Return a serializable snapshot."""
        with self._lock:
            return {
                'count': self._count,
                'sum': round(self._sum, 6),
                'avg': round(self.avg, 6),
                'buckets': {
                    str(b): self._bucket_counts.get(b, 0)
                    for b in self.buckets
                },
            }


class Counter:
    """Thread-safe counter."""

    def __init__(self) -> None:
        self._value = 0
        self._lock = Lock()

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> int:
        return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0


class LabeledCounter:
    """Thread-safe counter with label dimensions."""

    def __init__(self) -> None:
        self._values: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def inc(self, label: str, amount: int = 1) -> None:
        with self._lock:
            self._values[label] += amount

    def get(self, label: str) -> int:
        return self._values.get(label, 0)

    @property
    def all(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        with self._lock:
            self._values.clear()


class MetricsRegistry:
    """Central registry for all sandbox metrics."""

    def __init__(self) -> None:
        # Proxy metrics
        self.proxy_request_latency = LatencyHistogram()
        self.proxy_request_status = LabeledCounter()
        self.proxy_request_total = Counter()
        self.proxy_error_total = Counter()

        # Exec session metrics
        self.exec_create_total = Counter()
        self.exec_create_errors = Counter()
        self.exec_terminate_total = Counter()
        self.exec_attach_total = Counter()
        self.exec_attach_errors = Counter()

        # WebSocket metrics
        self.ws_connect_total = Counter()
        self.ws_disconnect_total = Counter()
        self.ws_active = Counter()  # Tracks current count

        # Health check metrics
        self.health_check_latency = LatencyHistogram()
        self.health_check_failures = Counter()
        self.health_check_total = Counter()

        # Readiness state
        self.readiness_transitions = LabeledCounter()

    def record_proxy_request(
        self, status_code: int, latency_seconds: float,
    ) -> None:
        """Record a completed proxy request."""
        self.proxy_request_total.inc()
        self.proxy_request_latency.observe(latency_seconds)
        self.proxy_request_status.inc(str(status_code))
        if status_code >= 400:
            self.proxy_error_total.inc()

    def record_exec_create(self, success: bool = True) -> None:
        """Record an exec session creation attempt."""
        self.exec_create_total.inc()
        if not success:
            self.exec_create_errors.inc()

    def record_exec_attach(self, success: bool = True) -> None:
        """Record an exec session attach attempt."""
        self.exec_attach_total.inc()
        if not success:
            self.exec_attach_errors.inc()

    def record_ws_connect(self) -> None:
        """Record a WebSocket connection."""
        self.ws_connect_total.inc()
        self.ws_active.inc()

    def record_ws_disconnect(self) -> None:
        """Record a WebSocket disconnection."""
        self.ws_disconnect_total.inc()
        self.ws_active.inc(-1)

    def record_health_check(
        self, latency_seconds: float, success: bool = True,
    ) -> None:
        """Record a health check execution."""
        self.health_check_total.inc()
        self.health_check_latency.observe(latency_seconds)
        if not success:
            self.health_check_failures.inc()

    def record_readiness_transition(self, to_state: str) -> None:
        """Record a readiness state transition."""
        self.readiness_transitions.inc(to_state)

    def snapshot(self) -> dict:
        """Return a serializable snapshot of all metrics."""
        return {
            'proxy': {
                'request_total': self.proxy_request_total.value,
                'error_total': self.proxy_error_total.value,
                'latency': self.proxy_request_latency.snapshot(),
                'status_codes': self.proxy_request_status.all,
            },
            'exec': {
                'create_total': self.exec_create_total.value,
                'create_errors': self.exec_create_errors.value,
                'terminate_total': self.exec_terminate_total.value,
                'attach_total': self.exec_attach_total.value,
                'attach_errors': self.exec_attach_errors.value,
            },
            'websocket': {
                'connect_total': self.ws_connect_total.value,
                'disconnect_total': self.ws_disconnect_total.value,
                'active': self.ws_active.value,
            },
            'health': {
                'check_total': self.health_check_total.value,
                'check_failures': self.health_check_failures.value,
                'latency': self.health_check_latency.snapshot(),
            },
            'readiness': {
                'transitions': self.readiness_transitions.all,
            },
        }
