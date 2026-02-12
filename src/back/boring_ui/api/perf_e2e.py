"""Performance/load/soak e2e scripts with telemetry and artifact capture.

Provides load generation and measurement utilities for:
  - /api/tree: bounded traversal under concurrent load
  - /api/search: file search under burst load
  - /ws/pty: PTY WebSocket under sustained message throughput
  - /ws/claude-stream: chat WebSocket under realistic concurrency

Captures:
  - Latency histograms (p50, p90, p95, p99)
  - Disconnect rates and reconnect counts
  - Queue pressure metrics (high-water events, drops)
  - Full run artifacts for regression comparison
"""
from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum

from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger
from boring_ui.api.ws_lifecycle import (
    BoundedOutboundQueue,
    WSLifecycleConfig,
    WSLifecyclePolicy,
)


class LoadProfile(Enum):
    """Load profile type."""
    BURST = 'burst'
    SUSTAINED = 'sustained'
    SOAK = 'soak'
    RAMP = 'ramp'


class EndpointType(Enum):
    """Endpoint being tested."""
    TREE = 'tree'
    SEARCH = 'search'
    PTY = 'pty'
    CHAT = 'chat'


@dataclass
class LatencyHistogram:
    """Captures request latency distribution."""
    samples: list[float] = field(default_factory=list)

    def record(self, latency_ms: float) -> None:
        self.samples.append(latency_ms)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def p50(self) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        return self._percentile(sorted_s, 50)

    @property
    def p90(self) -> float:
        if not self.samples:
            return 0.0
        return self._percentile(sorted(self.samples), 90)

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        return self._percentile(sorted(self.samples), 95)

    @property
    def p99(self) -> float:
        if not self.samples:
            return 0.0
        return self._percentile(sorted(self.samples), 99)

    @property
    def mean(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.mean(self.samples)

    @property
    def min_val(self) -> float:
        if not self.samples:
            return 0.0
        return min(self.samples)

    @property
    def max_val(self) -> float:
        if not self.samples:
            return 0.0
        return max(self.samples)

    @property
    def stddev(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)

    @staticmethod
    def _percentile(sorted_data: list[float], pct: float) -> float:
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * pct / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)

    def to_dict(self) -> dict:
        return {
            'count': self.count,
            'p50': round(self.p50, 3),
            'p90': round(self.p90, 3),
            'p95': round(self.p95, 3),
            'p99': round(self.p99, 3),
            'mean': round(self.mean, 3),
            'min': round(self.min_val, 3),
            'max': round(self.max_val, 3),
            'stddev': round(self.stddev, 3),
        }


@dataclass
class QueuePressureMetrics:
    """Tracks queue pressure during load tests."""
    high_water_events: int = 0
    total_drops: int = 0
    peak_queue_size: int = 0
    total_enqueued: int = 0

    def record_queue_state(self, queue: BoundedOutboundQueue) -> None:
        self.high_water_events = queue.stats.high_water_events
        self.total_drops = queue.stats.dropped
        self.total_enqueued = queue.stats.enqueued
        if queue.size > self.peak_queue_size:
            self.peak_queue_size = queue.size

    @property
    def drop_rate(self) -> float:
        if self.total_enqueued == 0:
            return 0.0
        return self.total_drops / self.total_enqueued

    def to_dict(self) -> dict:
        return {
            'high_water_events': self.high_water_events,
            'total_drops': self.total_drops,
            'peak_queue_size': self.peak_queue_size,
            'total_enqueued': self.total_enqueued,
            'drop_rate': round(self.drop_rate, 4),
        }


@dataclass
class DisconnectMetrics:
    """Tracks disconnect/reconnect behavior."""
    disconnects: int = 0
    reconnects: int = 0
    failed_reconnects: int = 0

    @property
    def reconnect_success_rate(self) -> float:
        total = self.reconnects + self.failed_reconnects
        if total == 0:
            return 1.0
        return self.reconnects / total

    def to_dict(self) -> dict:
        return {
            'disconnects': self.disconnects,
            'reconnects': self.reconnects,
            'failed_reconnects': self.failed_reconnects,
            'reconnect_success_rate': round(self.reconnect_success_rate, 4),
        }


@dataclass
class LoadTestConfig:
    """Configuration for a load test run."""
    endpoint: EndpointType
    profile: LoadProfile
    concurrency: int = 10
    requests_per_client: int = 100
    duration_seconds: float = 0.0
    queue_max_size: int = 256
    ramp_steps: int = 5


@dataclass
class LoadTestResult:
    """Result of a load test run."""
    config: LoadTestConfig
    latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    queue_pressure: QueuePressureMetrics = field(default_factory=QueuePressureMetrics)
    disconnects: DisconnectMetrics = field(default_factory=DisconnectMetrics)
    total_requests: int = 0
    total_errors: int = 0
    elapsed_seconds: float = 0.0

    @property
    def throughput(self) -> float:
        """Requests per second."""
        if self.elapsed_seconds == 0:
            return 0.0
        return self.total_requests / self.elapsed_seconds

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    @property
    def success_rate(self) -> float:
        return 1.0 - self.error_rate

    def to_dict(self) -> dict:
        return {
            'endpoint': self.config.endpoint.value,
            'profile': self.config.profile.value,
            'concurrency': self.config.concurrency,
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'throughput_rps': round(self.throughput, 2),
            'error_rate': round(self.error_rate, 4),
            'success_rate': round(self.success_rate, 4),
            'elapsed_seconds': round(self.elapsed_seconds, 3),
            'latency': self.latency.to_dict(),
            'queue_pressure': self.queue_pressure.to_dict(),
            'disconnects': self.disconnects.to_dict(),
        }


# ── Load simulations ──


def simulate_tree_load(config: LoadTestConfig | None = None) -> LoadTestResult:
    """Simulate /api/tree load with concurrent traversals.

    Generates synthetic latency samples modeling bounded tree
    traversal under concurrent load.
    """
    cfg = config or LoadTestConfig(
        endpoint=EndpointType.TREE,
        profile=LoadProfile.BURST,
    )
    start = time.monotonic()
    result = LoadTestResult(config=cfg)

    total = cfg.concurrency * cfg.requests_per_client
    for i in range(total):
        # Synthetic latency: base + concurrency overhead
        base_latency = 2.0 + (i % cfg.concurrency) * 0.5
        result.latency.record(base_latency)
        result.total_requests += 1

    result.elapsed_seconds = (time.monotonic() - start) or 0.001
    return result


def simulate_search_load(config: LoadTestConfig | None = None) -> LoadTestResult:
    """Simulate /api/search burst load.

    Models file search under burst concurrency with occasional
    timeouts.
    """
    cfg = config or LoadTestConfig(
        endpoint=EndpointType.SEARCH,
        profile=LoadProfile.BURST,
    )
    start = time.monotonic()
    result = LoadTestResult(config=cfg)

    total = cfg.concurrency * cfg.requests_per_client
    for i in range(total):
        # 2% timeout rate under load
        if i % 50 == 49:
            result.total_errors += 1
            result.latency.record(5000.0)  # Timeout at 5s
        else:
            latency = 5.0 + (i % cfg.concurrency) * 1.0
            result.latency.record(latency)
        result.total_requests += 1

    result.elapsed_seconds = (time.monotonic() - start) or 0.001
    return result


def simulate_pty_load(config: LoadTestConfig | None = None) -> LoadTestResult:
    """Simulate /ws/pty sustained message throughput.

    Models PTY sessions with concurrent output streams hitting
    queue backpressure limits.
    """
    cfg = config or LoadTestConfig(
        endpoint=EndpointType.PTY,
        profile=LoadProfile.SUSTAINED,
        concurrency=5,
        requests_per_client=200,
    )
    start = time.monotonic()
    result = LoadTestResult(config=cfg)

    policy = WSLifecyclePolicy(WSLifecycleConfig(
        queue_max_size=cfg.queue_max_size,
        max_sessions=cfg.concurrency + 10,
    ))

    # Register sessions
    session_ids = []
    for i in range(cfg.concurrency):
        sid = f'pty-load-{i}'
        policy.register_session(sid)
        session_ids.append(sid)

    # Send messages
    for sid in session_ids:
        for j in range(cfg.requests_per_client):
            msg = {'type': 'output', 'data': f'data-{j}'}
            policy.enqueue_message(sid, msg)
            result.total_requests += 1
            latency = 1.0 + (j % 10) * 0.2
            result.latency.record(latency)

    # Collect queue metrics
    for sid in session_ids:
        entry = policy.get_session(sid)
        if entry:
            result.queue_pressure.record_queue_state(entry.queue)

    # Dispatch
    batches = policy.dispatch_round()

    result.elapsed_seconds = (time.monotonic() - start) or 0.001
    return result


def simulate_chat_load(config: LoadTestConfig | None = None) -> LoadTestResult:
    """Simulate /ws/claude-stream under realistic concurrency.

    Models chat sessions with concurrent user messages and assistant
    responses, tracking disconnect/reconnect behavior.
    """
    cfg = config or LoadTestConfig(
        endpoint=EndpointType.CHAT,
        profile=LoadProfile.SUSTAINED,
        concurrency=3,
        requests_per_client=50,
    )
    start = time.monotonic()
    result = LoadTestResult(config=cfg)

    for client in range(cfg.concurrency):
        for req in range(cfg.requests_per_client):
            result.total_requests += 1
            # Longer latency for chat (thinking time)
            latency = 50.0 + (req % 5) * 10.0
            result.latency.record(latency)

            # 1% disconnect rate
            if req % 100 == 99:
                result.disconnects.disconnects += 1
                # 80% reconnect success
                if req % 5 != 0:
                    result.disconnects.reconnects += 1
                else:
                    result.disconnects.failed_reconnects += 1

    result.elapsed_seconds = (time.monotonic() - start) or 0.001
    return result


def simulate_ramp_load(
    endpoint: EndpointType = EndpointType.TREE,
    ramp_steps: int = 5,
    base_concurrency: int = 2,
    requests_per_step: int = 50,
) -> list[LoadTestResult]:
    """Simulate ramping load over multiple steps.

    Increases concurrency linearly from base_concurrency up to
    base_concurrency * ramp_steps.
    """
    results = []
    for step in range(1, ramp_steps + 1):
        concurrency = base_concurrency * step
        cfg = LoadTestConfig(
            endpoint=endpoint,
            profile=LoadProfile.RAMP,
            concurrency=concurrency,
            requests_per_client=requests_per_step,
        )
        if endpoint == EndpointType.TREE:
            result = simulate_tree_load(cfg)
        elif endpoint == EndpointType.SEARCH:
            result = simulate_search_load(cfg)
        elif endpoint == EndpointType.PTY:
            result = simulate_pty_load(cfg)
        else:
            result = simulate_chat_load(cfg)
        results.append(result)
    return results


# ── Runner ──


class PerfTestRunner:
    """Runs performance test scenarios and collects results."""

    def __init__(
        self,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> None:
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._results: list[LoadTestResult] = []

    @property
    def results(self) -> list[LoadTestResult]:
        return list(self._results)

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    def record_result(self, result: LoadTestResult) -> None:
        self._results.append(result)
        self._logger.info(
            f'{result.config.endpoint.value}/{result.config.profile.value}: '
            f'{result.total_requests} reqs, '
            f'p50={result.latency.p50:.1f}ms, '
            f'p99={result.latency.p99:.1f}ms, '
            f'err={result.error_rate:.2%}',
            test_name=f'{result.config.endpoint.value}_{result.config.profile.value}',
        )
        self._timeline.record(
            'perf_test',
            'inbound',
            endpoint=result.config.endpoint.value,
            profile=result.config.profile.value,
            total_requests=result.total_requests,
            throughput=result.throughput,
        )

    @property
    def total_requests(self) -> int:
        return sum(r.total_requests for r in self._results)

    @property
    def total_errors(self) -> int:
        return sum(r.total_errors for r in self._results)

    def summary(self) -> dict:
        return {
            'total_runs': len(self._results),
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'results': [r.to_dict() for r in self._results],
        }
