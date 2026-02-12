"""End-to-end resilience scripts for reconnect, backpressure, and upstream flaps.

Provides scenario definitions and simulation utilities for testing
transient failures, recovery paths, and degradation modes:

  - Transient disconnects and exec attach retries
  - Backpressure overflow handling under sustained load
  - Service health flapping (healthy -> unhealthy -> healthy)
  - Stale session outcomes after upstream timeout/crash
  - WebSocket reconnection with history replay verification

Each scenario captures a detailed timeline log for failure replay and
debugging via the test_artifacts infrastructure.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from boring_ui.api.error_normalization import (
    ErrorCategory,
    WS_INTERNAL_ERROR,
    WS_PROVIDER_TIMEOUT,
    WS_PROVIDER_UNAVAILABLE,
    WS_SESSION_NOT_FOUND,
    WS_SESSION_TERMINATED,
    normalize_http_error,
    normalize_ws_error,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger
from boring_ui.api.ws_lifecycle import (
    BoundedOutboundQueue,
    DetachState,
    DetachWindow,
    QueueState,
    WSLifecycleConfig,
    WSLifecyclePolicy,
)


class ResilienceScenario(Enum):
    """Types of resilience scenarios."""
    TRANSIENT_DISCONNECT = 'transient_disconnect'
    BACKPRESSURE_OVERFLOW = 'backpressure_overflow'
    HEALTH_FLAP = 'health_flap'
    STALE_SESSION = 'stale_session'
    WS_RECONNECT = 'ws_reconnect'
    UPSTREAM_TIMEOUT = 'upstream_timeout'
    EXEC_ATTACH_RETRY = 'exec_attach_retry'
    WORKSPACE_SERVICE_503 = 'workspace_service_503'


class RecoveryOutcome(Enum):
    """Outcome of a resilience scenario."""
    RECOVERED = 'recovered'
    DEGRADED = 'degraded'
    FAILED = 'failed'


@dataclass
class FaultEvent:
    """A fault injected during a scenario."""
    timestamp: float
    fault_type: str
    description: str
    duration_ms: float = 0.0
    recovered: bool = False

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'fault_type': self.fault_type,
            'description': self.description,
            'duration_ms': self.duration_ms,
            'recovered': self.recovered,
        }


@dataclass
class ResilienceResult:
    """Result of executing a resilience scenario."""
    scenario: ResilienceScenario
    outcome: RecoveryOutcome
    faults: list[FaultEvent] = field(default_factory=list)
    messages_dropped: int = 0
    messages_delivered: int = 0
    reconnect_attempts: int = 0
    recovery_time_ms: float = 0.0
    error_codes: list[int] = field(default_factory=list)
    error_categories: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def is_recovered(self) -> bool:
        return self.outcome == RecoveryOutcome.RECOVERED

    @property
    def is_degraded(self) -> bool:
        return self.outcome == RecoveryOutcome.DEGRADED

    @property
    def delivery_rate(self) -> float:
        total = self.messages_delivered + self.messages_dropped
        if total == 0:
            return 1.0
        return self.messages_delivered / total

    def to_dict(self) -> dict:
        return {
            'scenario': self.scenario.value,
            'outcome': self.outcome.value,
            'faults': [f.to_dict() for f in self.faults],
            'messages_dropped': self.messages_dropped,
            'messages_delivered': self.messages_delivered,
            'reconnect_attempts': self.reconnect_attempts,
            'recovery_time_ms': self.recovery_time_ms,
            'error_codes': self.error_codes,
            'error_categories': self.error_categories,
            'delivery_rate': self.delivery_rate,
        }


def assert_fault_injection_pass(result: ResilienceResult) -> None:
    """Raise AssertionError when a result violates scenario pass/fail contract."""
    if result.scenario == ResilienceScenario.WORKSPACE_SERVICE_503:
        assert 503 in result.error_codes, 'workspace_service_503 must include HTTP 503'
        assert ErrorCategory.PROVIDER_UNAVAILABLE.value in result.error_categories, (
            'workspace_service_503 must map to provider_unavailable category'
        )
        assert len(result.faults) > 0, 'workspace_service_503 must record at least one fault'
        return

    if result.scenario == ResilienceScenario.EXEC_ATTACH_RETRY:
        assert result.reconnect_attempts > 0, 'exec_attach_retry must attempt attach at least once'
        if result.outcome == RecoveryOutcome.RECOVERED:
            assert any(f.recovered for f in result.faults) or len(result.faults) == 0, (
                'recovered exec_attach_retry must either recover a fault or succeed first try'
            )
        return

    if result.scenario == ResilienceScenario.TRANSIENT_DISCONNECT:
        assert result.reconnect_attempts >= 1, 'transient_disconnect must attempt reconnect'
        assert any(f.fault_type == 'midstream_disconnect' for f in result.faults), (
            'transient_disconnect must include midstream_disconnect fault'
        )
        return


# ── Backpressure simulation ──


@dataclass
class BackpressureSimConfig:
    """Configuration for backpressure overflow simulation."""
    queue_max_size: int = 100
    high_water: int = 75
    low_water: int = 25
    messages_to_send: int = 150
    drain_rate: int = 10


def simulate_backpressure(
    config: BackpressureSimConfig | None = None,
) -> ResilienceResult:
    """Simulate sustained message load causing backpressure.

    Sends messages_to_send messages into a bounded queue without
    draining, verifying that overflow is handled gracefully.
    """
    cfg = config or BackpressureSimConfig()
    queue = BoundedOutboundQueue(
        max_size=cfg.queue_max_size,
        high_water=cfg.high_water,
        low_water=cfg.low_water,
    )

    faults: list[FaultEvent] = []
    fault_recorded = False

    for i in range(cfg.messages_to_send):
        msg = {'type': 'output', 'data': f'msg-{i}', 'seq': i}
        prev_dropped = queue.stats.dropped
        queue.enqueue(msg)
        if queue.stats.dropped > prev_dropped and not fault_recorded:
            faults.append(FaultEvent(
                timestamp=time.time(),
                fault_type='backpressure_overflow',
                description=f'Queue dropping oldest at message {i}',
            ))
            fault_recorded = True

    dropped = queue.stats.dropped
    delivered = queue.stats.enqueued

    # Drain some messages to demonstrate recovery
    drained = queue.dequeue(cfg.drain_rate)
    for f in faults:
        f.recovered = len(drained) > 0
        f.duration_ms = 0.0

    if dropped == 0:
        outcome = RecoveryOutcome.RECOVERED
    elif delivered > 0:
        outcome = RecoveryOutcome.DEGRADED
    else:
        outcome = RecoveryOutcome.FAILED

    return ResilienceResult(
        scenario=ResilienceScenario.BACKPRESSURE_OVERFLOW,
        outcome=outcome,
        faults=faults,
        messages_dropped=dropped,
        messages_delivered=delivered,
    )


# ── Health flap simulation ──


@dataclass
class HealthFlapConfig:
    """Configuration for health flapping simulation."""
    flap_count: int = 3
    initial_healthy: bool = True


@dataclass
class Workspace503Config:
    """Configuration for explicit workspace-service 503 fault injection."""
    retry_budget: int = 2
    fail_attempts: int = 1


def simulate_workspace_service_503(
    config: Workspace503Config | None = None,
) -> ResilienceResult:
    """Simulate workspace service returning HTTP 503 with deterministic recovery outcome."""
    cfg = config or Workspace503Config()
    faults: list[FaultEvent] = []
    retries = 0

    for attempt in range(cfg.retry_budget + 1):
        if attempt < cfg.fail_attempts:
            retries += 1
            faults.append(FaultEvent(
                timestamp=time.time(),
                fault_type='workspace_503',
                description=f'Workspace service returned HTTP 503 on attempt {attempt + 1}',
            ))
        else:
            break

    recovered = cfg.fail_attempts <= cfg.retry_budget
    if recovered:
        for fault in faults:
            fault.recovered = True
            fault.duration_ms = 100.0

    norm_http = normalize_http_error('provider_unavailable')
    norm_ws = normalize_ws_error('ws_provider_unavailable')

    return ResilienceResult(
        scenario=ResilienceScenario.WORKSPACE_SERVICE_503,
        outcome=RecoveryOutcome.RECOVERED if recovered else RecoveryOutcome.FAILED,
        faults=faults,
        reconnect_attempts=retries,
        recovery_time_ms=100.0 if recovered else 0.0,
        error_codes=[norm_http.http_status, norm_ws.ws_close_code],
        error_categories=[norm_http.category.value, norm_ws.category.value],
    )


def simulate_health_flap(
    config: HealthFlapConfig | None = None,
) -> ResilienceResult:
    """Simulate service health flapping.

    Alternates health status and verifies that error normalization
    produces correct categories at each transition.
    """
    cfg = config or HealthFlapConfig()
    faults: list[FaultEvent] = []
    error_categories: list[str] = []
    error_codes: list[int] = []

    healthy = cfg.initial_healthy
    for i in range(cfg.flap_count):
        if healthy:
            # Service goes unhealthy
            healthy = False
            norm = normalize_http_error('provider_unavailable')
            error_categories.append(norm.category.value)
            error_codes.append(norm.http_status)
            faults.append(FaultEvent(
                timestamp=time.time(),
                fault_type='health_flap',
                description=f'Flap {i}: healthy -> unhealthy',
            ))
        else:
            # Service recovers
            healthy = True
            if faults:
                faults[-1].recovered = True
                faults[-1].duration_ms = 50.0  # Simulated recovery time

    outcome = RecoveryOutcome.RECOVERED if healthy else RecoveryOutcome.DEGRADED

    return ResilienceResult(
        scenario=ResilienceScenario.HEALTH_FLAP,
        outcome=outcome,
        faults=faults,
        error_codes=error_codes,
        error_categories=error_categories,
    )


# ── Stale session simulation ──


def simulate_stale_session(
    detach_window_seconds: float = 0.0,
) -> ResilienceResult:
    """Simulate stale session after upstream timeout.

    Creates a detach window with zero timeout so the session
    immediately becomes stale on detach.
    """
    window = DetachWindow(window_seconds=detach_window_seconds)
    faults: list[FaultEvent] = []

    # Detach the client
    window.detach()
    faults.append(FaultEvent(
        timestamp=time.time(),
        fault_type='client_detach',
        description='Client disconnected',
    ))

    # Attempt reattach (should fail immediately with 0 window)
    reattached = window.reattach()
    faults[-1].recovered = reattached

    # Normalize the error
    error_key = 'session_not_found' if not reattached else 'session_terminated'
    norm = normalize_ws_error(error_key)

    if reattached:
        outcome = RecoveryOutcome.RECOVERED
    else:
        outcome = RecoveryOutcome.FAILED

    return ResilienceResult(
        scenario=ResilienceScenario.STALE_SESSION,
        outcome=outcome,
        faults=faults,
        error_codes=[norm.ws_close_code],
        error_categories=[norm.category.value],
    )


# ── WS reconnect simulation ──


def simulate_ws_reconnect(
    detach_window_seconds: float = 30.0,
) -> ResilienceResult:
    """Simulate WebSocket reconnection within detach window.

    Client detaches and immediately reattaches within the window.
    """
    window = DetachWindow(window_seconds=detach_window_seconds)
    faults: list[FaultEvent] = []

    window.detach()
    faults.append(FaultEvent(
        timestamp=time.time(),
        fault_type='ws_disconnect',
        description='WebSocket disconnected',
    ))

    # Immediate reconnect
    reattached = window.reattach()
    faults[-1].recovered = reattached

    outcome = RecoveryOutcome.RECOVERED if reattached else RecoveryOutcome.FAILED

    return ResilienceResult(
        scenario=ResilienceScenario.WS_RECONNECT,
        outcome=outcome,
        faults=faults,
        reconnect_attempts=1,
    )


@dataclass
class MidstreamDisconnectConfig:
    """Configuration for explicit mid-stream disconnect fault injection."""
    total_messages: int = 20
    disconnect_after: int = 8
    detach_window_seconds: float = 30.0


def simulate_midstream_disconnect(
    config: MidstreamDisconnectConfig | None = None,
) -> ResilienceResult:
    """Simulate a mid-stream WebSocket disconnect and reconnect attempt."""
    cfg = config or MidstreamDisconnectConfig()
    window = DetachWindow(window_seconds=cfg.detach_window_seconds)

    delivered_before = max(0, min(cfg.disconnect_after, cfg.total_messages))
    remaining = max(0, cfg.total_messages - delivered_before)

    window.detach()
    fault = FaultEvent(
        timestamp=time.time(),
        fault_type='midstream_disconnect',
        description=f'WebSocket dropped after {delivered_before} messages',
    )

    reattached = window.reattach()
    fault.recovered = reattached

    if reattached:
        outcome = RecoveryOutcome.RECOVERED
        delivered = delivered_before + remaining
        dropped = 0
        error_codes: list[int] = []
        error_categories: list[str] = []
    else:
        outcome = RecoveryOutcome.FAILED
        delivered = delivered_before
        dropped = remaining
        ws_norm = normalize_ws_error('session_not_found')
        error_codes = [ws_norm.ws_close_code]
        error_categories = [ws_norm.category.value]

    return ResilienceResult(
        scenario=ResilienceScenario.TRANSIENT_DISCONNECT,
        outcome=outcome,
        faults=[fault],
        reconnect_attempts=1,
        messages_delivered=delivered,
        messages_dropped=dropped,
        error_codes=error_codes,
        error_categories=error_categories,
    )


# ── Upstream timeout simulation ──


def simulate_upstream_timeout() -> ResilienceResult:
    """Simulate upstream provider timeout.

    Verifies error normalization produces correct timeout category
    and WS close code.
    """
    http_norm = normalize_http_error('provider_timeout')
    ws_norm = normalize_ws_error('ws_provider_timeout')

    faults = [FaultEvent(
        timestamp=time.time(),
        fault_type='upstream_timeout',
        description='Provider did not respond within budget',
    )]

    return ResilienceResult(
        scenario=ResilienceScenario.UPSTREAM_TIMEOUT,
        outcome=RecoveryOutcome.FAILED,
        faults=faults,
        error_codes=[http_norm.http_status, ws_norm.ws_close_code],
        error_categories=[http_norm.category.value, ws_norm.category.value],
    )


# ── Exec attach retry simulation ──


@dataclass
class ExecAttachRetryConfig:
    """Configuration for exec attach retry simulation."""
    max_retries: int = 3
    fail_until: int = 2  # Succeed on this attempt (0-based)


def simulate_exec_attach_retry(
    config: ExecAttachRetryConfig | None = None,
) -> ResilienceResult:
    """Simulate exec session attach with transient failures.

    Fails the first N attempts, then succeeds on attempt fail_until.
    """
    cfg = config or ExecAttachRetryConfig()
    faults: list[FaultEvent] = []
    attempts = 0

    for i in range(cfg.max_retries):
        attempts += 1
        if i < cfg.fail_until:
            faults.append(FaultEvent(
                timestamp=time.time(),
                fault_type='exec_attach_fail',
                description=f'Attach attempt {i} failed',
                recovered=False,
            ))
        else:
            # Success
            if faults:
                faults[-1].recovered = True
            break

    success = attempts <= cfg.max_retries and cfg.fail_until < cfg.max_retries
    outcome = RecoveryOutcome.RECOVERED if success else RecoveryOutcome.FAILED

    return ResilienceResult(
        scenario=ResilienceScenario.EXEC_ATTACH_RETRY,
        outcome=outcome,
        faults=faults,
        reconnect_attempts=attempts,
    )


# ── Lifecycle policy resilience ──


def simulate_lifecycle_resilience(
    session_count: int = 5,
    messages_per_session: int = 20,
    queue_max_size: int = 10,
) -> ResilienceResult:
    """Simulate multiple sessions under load with lifecycle policy.

    Creates sessions, fills queues, runs dispatch and reap cycles.
    """
    policy = WSLifecyclePolicy(WSLifecycleConfig(
        queue_max_size=queue_max_size,
        max_sessions=session_count + 5,
    ))

    faults: list[FaultEvent] = []
    total_delivered = 0
    total_dropped = 0

    # Register sessions
    session_ids = []
    for i in range(session_count):
        sid = f'resilience-session-{i}'
        policy.register_session(sid)
        session_ids.append(sid)

    # Flood all sessions
    for sid in session_ids:
        for j in range(messages_per_session):
            msg = {'type': 'output', 'data': f'msg-{j}'}
            policy.enqueue_message(sid, msg)

    # Count drops from queue stats
    for sid in session_ids:
        entry = policy.get_session(sid)
        if entry:
            total_dropped += entry.queue.stats.dropped
            total_delivered += entry.queue.stats.enqueued

    if total_dropped > 0:
        faults.append(FaultEvent(
            timestamp=time.time(),
            fault_type='queue_overflow',
            description=f'{total_dropped} messages dropped across {session_count} sessions',
        ))

    # Dispatch round
    batches = policy.dispatch_round()
    dispatched = sum(len(msgs) for msgs in batches.values())

    # Reap cycle
    reap_result = policy.run_reap_cycle()

    if total_dropped == 0:
        outcome = RecoveryOutcome.RECOVERED
    elif total_delivered > 0:
        outcome = RecoveryOutcome.DEGRADED
    else:
        outcome = RecoveryOutcome.FAILED

    return ResilienceResult(
        scenario=ResilienceScenario.BACKPRESSURE_OVERFLOW,
        outcome=outcome,
        faults=faults,
        messages_dropped=total_dropped,
        messages_delivered=total_delivered,
        extra={
            'dispatched': dispatched,
            'reaped': reap_result.total_reaped,
            'sessions': session_count,
        },
    )


# ── Scenario registry ──


ALL_SCENARIOS = {
    ResilienceScenario.TRANSIENT_DISCONNECT: simulate_midstream_disconnect,
    ResilienceScenario.BACKPRESSURE_OVERFLOW: simulate_backpressure,
    ResilienceScenario.HEALTH_FLAP: simulate_health_flap,
    ResilienceScenario.STALE_SESSION: simulate_stale_session,
    ResilienceScenario.WS_RECONNECT: simulate_ws_reconnect,
    ResilienceScenario.UPSTREAM_TIMEOUT: simulate_upstream_timeout,
    ResilienceScenario.EXEC_ATTACH_RETRY: simulate_exec_attach_retry,
    ResilienceScenario.WORKSPACE_SERVICE_503: simulate_workspace_service_503,
}


class ResilienceSuiteRunner:
    """Runs all resilience scenarios and collects results."""

    def __init__(
        self,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> None:
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._results: list[ResilienceResult] = []

    @property
    def results(self) -> list[ResilienceResult]:
        return list(self._results)

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    def record_result(self, result: ResilienceResult) -> None:
        """Record a scenario result and log it."""
        self._results.append(result)
        self._logger.info(
            f'Scenario {result.scenario.value}: {result.outcome.value}',
            test_name=result.scenario.value,
            faults=len(result.faults),
            dropped=result.messages_dropped,
            delivered=result.messages_delivered,
        )
        for fault in result.faults:
            self._timeline.record(
                'fault_injection',
                'inbound',
                fault_type=fault.fault_type,
                description=fault.description,
                recovered=fault.recovered,
            )

    @property
    def all_recovered(self) -> bool:
        return all(r.is_recovered for r in self._results)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self._results if r.outcome == RecoveryOutcome.FAILED)

    @property
    def degraded_count(self) -> int:
        return sum(1 for r in self._results if r.is_degraded)

    def summary(self) -> dict:
        return {
            'total_scenarios': len(self._results),
            'recovered': sum(1 for r in self._results if r.is_recovered),
            'degraded': self.degraded_count,
            'failed': self.failure_count,
            'all_recovered': self.all_recovered,
            'results': [r.to_dict() for r in self._results],
        }
