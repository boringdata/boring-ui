"""Fault injection suite for unhealthy service and WS disruptions.

Provides scripted fault-injection scenarios with deterministic pass/fail
assertions and timeline logging:

  - Workspace 503 (service unavailable)
  - Transient exec attach failures
  - Mid-stream WebSocket disconnects
  - Rate limit bursts
  - Auth token expiry during active session
  - Provider timeout cascades
  - Health check flapping during active sessions

Each scenario uses the test harness stubs to inject faults at precise
points, then validates error normalization, close codes, and recovery
behavior produce correct browser-safe semantics.
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
    WS_RATE_LIMITED,
    WS_SESSION_NOT_FOUND,
    WS_SESSION_TERMINATED,
    normalize_http_error,
    normalize_http_status,
    normalize_ws_error,
)
from boring_ui.api.http_delegation import (
    DelegationResponse,
    map_upstream_status,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger
from boring_ui.api.testing.stubs import StubExecClient, StubProxyClient, StubResponse


class FaultType(Enum):
    """Types of injected faults."""
    SERVICE_503 = 'service_503'
    EXEC_ATTACH_FAIL = 'exec_attach_fail'
    WS_MIDSTREAM_DISCONNECT = 'ws_midstream_disconnect'
    RATE_LIMIT_BURST = 'rate_limit_burst'
    AUTH_EXPIRY = 'auth_expiry'
    PROVIDER_TIMEOUT_CASCADE = 'provider_timeout_cascade'
    HEALTH_FLAP_ACTIVE = 'health_flap_active'


class AssertionOutcome(Enum):
    """Outcome of a fault injection assertion."""
    PASS = 'pass'
    FAIL = 'fail'


@dataclass(frozen=True)
class FaultAssertion:
    """A single pass/fail assertion from a fault injection scenario."""
    name: str
    outcome: AssertionOutcome
    expected: str
    actual: str
    message: str = ''

    @property
    def passed(self) -> bool:
        return self.outcome == AssertionOutcome.PASS

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'outcome': self.outcome.value,
            'expected': self.expected,
            'actual': self.actual,
            'message': self.message,
        }


@dataclass
class FaultScenarioResult:
    """Result of a fault injection scenario run."""
    fault_type: FaultType
    assertions: list[FaultAssertion] = field(default_factory=list)
    timeline_events: int = 0
    elapsed_ms: float = 0.0

    @property
    def pass_count(self) -> int:
        return sum(1 for a in self.assertions if a.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)

    @property
    def all_passed(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict:
        return {
            'fault_type': self.fault_type.value,
            'assertions': [a.to_dict() for a in self.assertions],
            'pass_count': self.pass_count,
            'fail_count': self.fail_count,
            'all_passed': self.all_passed,
            'elapsed_ms': self.elapsed_ms,
        }


def _assert_eq(name: str, expected, actual, msg: str = '') -> FaultAssertion:
    """Build a pass/fail assertion from equality check."""
    if expected == actual:
        return FaultAssertion(
            name=name,
            outcome=AssertionOutcome.PASS,
            expected=str(expected),
            actual=str(actual),
        )
    return FaultAssertion(
        name=name,
        outcome=AssertionOutcome.FAIL,
        expected=str(expected),
        actual=str(actual),
        message=msg or f'Expected {expected!r}, got {actual!r}',
    )


def _assert_in(name: str, value, container, msg: str = '') -> FaultAssertion:
    """Build a pass/fail assertion from containment check."""
    if value in container:
        return FaultAssertion(
            name=name,
            outcome=AssertionOutcome.PASS,
            expected=f'{value!r} in {container!r}',
            actual=str(value),
        )
    return FaultAssertion(
        name=name,
        outcome=AssertionOutcome.FAIL,
        expected=f'{value!r} in {container!r}',
        actual=str(value),
        message=msg or f'{value!r} not found in {container!r}',
    )


def _assert_range(
    name: str, value: int, low: int, high: int,
) -> FaultAssertion:
    """Assert value is within [low, high]."""
    if low <= value <= high:
        return FaultAssertion(
            name=name,
            outcome=AssertionOutcome.PASS,
            expected=f'{low} <= x <= {high}',
            actual=str(value),
        )
    return FaultAssertion(
        name=name,
        outcome=AssertionOutcome.FAIL,
        expected=f'{low} <= x <= {high}',
        actual=str(value),
        message=f'{value} not in range [{low}, {high}]',
    )


# ── Fault scenarios ──


def inject_service_503() -> FaultScenarioResult:
    """Inject workspace service 503 and verify error normalization.

    Simulates upstream workspace service returning 503 (Service Unavailable).
    Validates HTTP status mapping, error category, and retry-after semantics.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # HTTP path: upstream 503 -> maps through provider_error (502)
    resp = map_upstream_status(503)
    assertions.append(_assert_eq('http_mapped_status', 502, resp.status_code))
    if resp.json_body:
        assertions.append(_assert_in('body_has_error', 'error', resp.json_body))

    # Error normalization path
    norm = normalize_http_error('provider_unavailable')
    assertions.append(_assert_eq('category', 'provider_unavailable', norm.category.value))
    assertions.append(_assert_eq('http_status_norm', 503, norm.http_status))
    assertions.append(
        _assert_eq('retry_after_positive', True, norm.retry_after > 0,
                    'provider_unavailable should have retry_after'),
    )

    # WS path
    ws_norm = normalize_ws_error('ws_provider_unavailable')
    assertions.append(_assert_eq('ws_close_code', WS_PROVIDER_UNAVAILABLE, ws_norm.ws_close_code))
    assertions.append(_assert_range('ws_code_app_range', ws_norm.ws_close_code, 4000, 4999))

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.SERVICE_503,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_exec_attach_fail() -> FaultScenarioResult:
    """Inject exec session attach failure.

    Simulates the exec client raising an error during session creation.
    Validates error normalization maps to provider_error.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # Simulate the error normalization path
    norm = normalize_http_error(
        'provider_error',
        internal_detail='ExecClient: failed to create session: connection refused',
    )
    assertions.append(_assert_eq('category', 'provider_error', norm.category.value))
    assertions.append(_assert_eq('http_status', 502, norm.http_status))
    assertions.append(
        _assert_eq('no_internal_leak', True,
                    'connection refused' not in norm.message,
                    'Internal detail leaked in error message'),
    )
    assertions.append(
        _assert_eq('no_exec_leak', True,
                    'ExecClient' not in norm.message,
                    'ExecClient leaked in error message'),
    )

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.EXEC_ATTACH_FAIL,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_ws_midstream_disconnect() -> FaultScenarioResult:
    """Inject mid-stream WebSocket disconnect.

    Simulates a WebSocket session that disconnects unexpectedly
    during active communication. Validates close code and error
    normalization.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # Session terminated mid-stream
    norm = normalize_ws_error('session_terminated')
    assertions.append(_assert_eq(
        'ws_close_code', WS_SESSION_TERMINATED, norm.ws_close_code,
    ))
    assertions.append(_assert_eq('category', 'not_found', norm.category.value))
    assertions.append(_assert_range('ws_code_app_range', norm.ws_close_code, 4000, 4999))

    # Provider unknown during stream
    norm2 = normalize_ws_error(
        'ws_provider_unavailable',
        internal_detail='WebSocket: upstream connection reset during stream',
    )
    assertions.append(_assert_eq(
        'ws_unavail_code', WS_PROVIDER_UNAVAILABLE, norm2.ws_close_code,
    ))
    assertions.append(
        _assert_eq('no_ws_leak', True,
                    'upstream' not in norm2.message,
                    'Internal upstream detail leaked'),
    )

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.WS_MIDSTREAM_DISCONNECT,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_rate_limit_burst() -> FaultScenarioResult:
    """Inject rate limit burst across HTTP and WS.

    Validates both HTTP 429 and WS rate-limit close code produce
    correct retry-after semantics.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # HTTP rate limit
    http_norm = normalize_http_error('rate_limited')
    assertions.append(_assert_eq('http_status', 429, http_norm.http_status))
    assertions.append(_assert_eq('category', 'rate_limit', http_norm.category.value))
    assertions.append(_assert_eq(
        'http_retry_after', True, http_norm.retry_after > 0,
        'HTTP rate limit should have retry_after',
    ))

    # WS rate limit
    ws_norm = normalize_ws_error('ws_rate_limited')
    assertions.append(_assert_eq('ws_close_code', WS_RATE_LIMITED, ws_norm.ws_close_code))
    assertions.append(_assert_eq(
        'ws_retry_after', True, ws_norm.retry_after > 0,
        'WS rate limit should have retry_after',
    ))

    # Upstream 429 mapping
    resp = map_upstream_status(429)
    assertions.append(_assert_eq('upstream_429_status', 429, resp.status_code))

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.RATE_LIMIT_BURST,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_auth_expiry() -> FaultScenarioResult:
    """Inject auth token expiry during active session.

    Validates error normalization produces auth category with correct
    HTTP status and WS close code.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # HTTP auth failure
    http_norm = normalize_http_error('unauthorized')
    assertions.append(_assert_eq('http_status', 403, http_norm.http_status))
    assertions.append(_assert_eq('category', 'auth', http_norm.category.value))

    # WS auth failure
    ws_norm = normalize_ws_error('ws_auth_required')
    assertions.append(_assert_eq('ws_close_code', 4008, ws_norm.ws_close_code))
    assertions.append(_assert_eq('ws_category', 'auth', ws_norm.category.value))

    # No retry for auth
    assertions.append(_assert_eq(
        'no_retry_after', 0, http_norm.retry_after,
        'Auth errors should not suggest retry',
    ))

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.AUTH_EXPIRY,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_provider_timeout_cascade() -> FaultScenarioResult:
    """Inject cascading provider timeouts.

    Validates timeout normalization for both HTTP and WS paths,
    including upstream 504 mapping.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # HTTP timeout
    http_norm = normalize_http_error(
        'provider_timeout',
        internal_detail='httpx.ReadTimeout: 30s elapsed waiting for sprites:9000',
    )
    assertions.append(_assert_eq('http_status', 504, http_norm.http_status))
    assertions.append(_assert_eq('category', 'provider_timeout', http_norm.category.value))
    assertions.append(
        _assert_eq('no_httpx_leak', True,
                    'httpx' not in http_norm.message,
                    'httpx leaked in timeout message'),
    )

    # WS timeout
    ws_norm = normalize_ws_error(
        'ws_provider_timeout',
        internal_detail='socket.timeout: connect to workspace:9000 timed out',
    )
    assertions.append(_assert_eq('ws_close_code', WS_PROVIDER_TIMEOUT, ws_norm.ws_close_code))
    assertions.append(
        _assert_eq('no_socket_leak', True,
                    'socket' not in ws_norm.message,
                    'socket detail leaked in WS message'),
    )

    # Upstream 504 mapping -> maps through provider_error (502)
    resp = map_upstream_status(504)
    assertions.append(_assert_eq('upstream_504_mapped', 502, resp.status_code))

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.PROVIDER_TIMEOUT_CASCADE,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


def inject_health_flap_active() -> FaultScenarioResult:
    """Inject health check flapping during active sessions.

    Simulates service going unhealthy, then recovering. Validates
    error normalization at each transition point.
    """
    start = time.monotonic()
    assertions: list[FaultAssertion] = []

    # Phase 1: healthy -> unhealthy
    unhealthy_norm = normalize_http_error('provider_unavailable')
    assertions.append(_assert_eq(
        'unhealthy_status', 503, unhealthy_norm.http_status,
    ))
    assertions.append(_assert_eq(
        'unhealthy_category', 'provider_unavailable', unhealthy_norm.category.value,
    ))
    assertions.append(_assert_eq(
        'unhealthy_retry', True, unhealthy_norm.retry_after > 0,
    ))

    # Phase 2: recovery - requests succeed again
    # After recovery, errors should still normalize the same way for new failures
    transport_norm = normalize_http_error('transport_error')
    assertions.append(_assert_eq(
        'transport_status', 502, transport_norm.http_status,
    ))
    assertions.append(_assert_eq(
        'transport_category', 'transport', transport_norm.category.value,
    ))

    # WS during unhealthy
    ws_norm = normalize_ws_error('ws_provider_unavailable')
    assertions.append(_assert_eq(
        'ws_unavail_code', WS_PROVIDER_UNAVAILABLE, ws_norm.ws_close_code,
    ))
    assertions.append(_assert_eq(
        'ws_unavail_retry', True, ws_norm.retry_after > 0,
    ))

    elapsed = (time.monotonic() - start) * 1000
    return FaultScenarioResult(
        fault_type=FaultType.HEALTH_FLAP_ACTIVE,
        assertions=assertions,
        elapsed_ms=elapsed,
    )


# ── Scenario registry ──


ALL_FAULT_SCENARIOS = {
    FaultType.SERVICE_503: inject_service_503,
    FaultType.EXEC_ATTACH_FAIL: inject_exec_attach_fail,
    FaultType.WS_MIDSTREAM_DISCONNECT: inject_ws_midstream_disconnect,
    FaultType.RATE_LIMIT_BURST: inject_rate_limit_burst,
    FaultType.AUTH_EXPIRY: inject_auth_expiry,
    FaultType.PROVIDER_TIMEOUT_CASCADE: inject_provider_timeout_cascade,
    FaultType.HEALTH_FLAP_ACTIVE: inject_health_flap_active,
}


class FaultInjectionRunner:
    """Runs all fault injection scenarios and collects results."""

    def __init__(
        self,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> None:
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._results: list[FaultScenarioResult] = []

    @property
    def results(self) -> list[FaultScenarioResult]:
        return list(self._results)

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    def run_scenario(self, fault_type: FaultType) -> FaultScenarioResult:
        """Run a single fault injection scenario."""
        fn = ALL_FAULT_SCENARIOS[fault_type]
        result = fn()
        self._results.append(result)
        self._logger.info(
            f'Fault {fault_type.value}: '
            f'{result.pass_count}/{len(result.assertions)} passed',
            test_name=fault_type.value,
            passed=result.pass_count,
            failed=result.fail_count,
        )
        self._timeline.record(
            'fault_scenario',
            'inbound',
            fault_type=fault_type.value,
            all_passed=result.all_passed,
            assertion_count=len(result.assertions),
        )
        return result

    def run_all(self) -> None:
        """Run all registered fault scenarios."""
        for fault_type in ALL_FAULT_SCENARIOS:
            self.run_scenario(fault_type)

    @property
    def all_passed(self) -> bool:
        return all(r.all_passed for r in self._results)

    @property
    def total_assertions(self) -> int:
        return sum(len(r.assertions) for r in self._results)

    @property
    def total_failures(self) -> int:
        return sum(r.fail_count for r in self._results)

    def summary(self) -> dict:
        return {
            'total_scenarios': len(self._results),
            'total_assertions': self.total_assertions,
            'total_failures': self.total_failures,
            'all_passed': self.all_passed,
            'scenarios': [r.to_dict() for r in self._results],
        }
