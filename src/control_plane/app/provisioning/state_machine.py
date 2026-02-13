"""Provisioning state-machine and timeout handling contract.

Bead: bd-223o.10.2 (D2)

Implements the canonical provisioning flow:
  queued -> release_resolve -> creating_sandbox -> uploading_artifact
  -> bootstrapping -> health_check -> ready

And deterministic error transitions:
  any active step -> error
  error --(explicit retry)--> queued
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

STEP_TIMEOUT_CODE = 'STEP_TIMEOUT'

PROVISIONING_SEQUENCE = (
    'queued',
    'release_resolve',
    'creating_sandbox',
    'uploading_artifact',
    'bootstrapping',
    'health_check',
    'ready',
)

TERMINAL_STATES = frozenset({'ready', 'error'})
ACTIVE_STATES = frozenset(
    {
        'queued',
        'release_resolve',
        'creating_sandbox',
        'uploading_artifact',
        'bootstrapping',
        'health_check',
    }
)

ALLOWED_TRANSITIONS = MappingProxyType(
    {
        'queued': frozenset({'release_resolve'}),
        'release_resolve': frozenset({'creating_sandbox', 'error'}),
        'creating_sandbox': frozenset({'uploading_artifact', 'error'}),
        'uploading_artifact': frozenset({'bootstrapping', 'error'}),
        'bootstrapping': frozenset({'health_check', 'error'}),
        'health_check': frozenset({'ready', 'error'}),
        'ready': frozenset(),
        'error': frozenset({'queued'}),
    }
)

DEFAULT_STEP_TIMEOUT_SECONDS: Mapping[str, int] = MappingProxyType(
    {
        'release_resolve': 15,
        'creating_sandbox': 60,
        'uploading_artifact': 60,
        'bootstrapping': 120,
        'health_check': 30,
    }
)


@dataclass(frozen=True, slots=True)
class ProvisioningJobState:
    """State snapshot for one workspace provisioning job."""

    workspace_id: str
    state: str = 'queued'
    attempt: int = 1
    state_entered_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error_code: str | None = None
    last_error_detail: str | None = None


class InvalidStateTransition(ValueError):
    """Raised for invalid provisioning state transitions."""

    def __init__(self, from_state: str, to_state: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f'invalid state transition: {from_state!r} -> {to_state!r}'
        )


def create_queued_job(
    *,
    workspace_id: str,
    attempt: int = 1,
    now: datetime | None = None,
) -> ProvisioningJobState:
    """Create a new queued job snapshot."""
    if attempt < 1:
        raise ValueError('attempt must be >= 1')
    if now is not None:
        _require_aware_datetime(now)
    return ProvisioningJobState(
        workspace_id=workspace_id,
        state='queued',
        attempt=attempt,
        state_entered_at=now,
        started_at=now,
    )


def advance_state(
    job: ProvisioningJobState,
    *,
    now: datetime,
) -> ProvisioningJobState:
    """Advance provisioning by exactly one deterministic step."""
    _require_aware_datetime(now)
    if job.state == 'error':
        raise InvalidStateTransition('error', 'next')
    if job.state == 'ready':
        raise InvalidStateTransition('ready', 'next')

    current_index = PROVISIONING_SEQUENCE.index(job.state)
    next_state = PROVISIONING_SEQUENCE[current_index + 1]
    return _transition(job, to_state=next_state, now=now)


def retry_from_error(
    job: ProvisioningJobState,
    *,
    now: datetime,
) -> ProvisioningJobState:
    """Explicit retry transition from ``error`` to ``queued``."""
    _require_aware_datetime(now)
    if job.state != 'error':
        raise InvalidStateTransition(job.state, 'queued')

    return _transition(
        job,
        to_state='queued',
        now=now,
        attempt=job.attempt + 1,
        clear_error=True,
    )


def transition_to_error(
    job: ProvisioningJobState,
    *,
    now: datetime,
    error_code: str,
    error_detail: str,
) -> ProvisioningJobState:
    """Move any active provisioning state to terminal ``error``."""
    _require_aware_datetime(now)
    if job.state not in ACTIVE_STATES - {'queued'}:
        raise InvalidStateTransition(job.state, 'error')

    return _transition(
        job,
        to_state='error',
        now=now,
        error_code=error_code,
        error_detail=error_detail,
    )


def apply_step_timeout(
    job: ProvisioningJobState,
    *,
    now: datetime,
    step_timeouts: Mapping[str, int] = DEFAULT_STEP_TIMEOUT_SECONDS,
) -> ProvisioningJobState:
    """Apply timeout transition to ``error`` when active step exceeds limit."""
    _require_aware_datetime(now)
    if job.state in TERMINAL_STATES or job.state == 'queued':
        return job
    if job.state_entered_at is None:
        return job

    timeout_seconds = step_timeouts.get(job.state)
    if timeout_seconds is None:
        return job

    elapsed_seconds = (now - job.state_entered_at).total_seconds()
    if elapsed_seconds <= timeout_seconds:
        return job

    return transition_to_error(
        job,
        now=now,
        error_code=STEP_TIMEOUT_CODE,
        error_detail=(
            f'step {job.state!r} exceeded timeout '
            f'({int(elapsed_seconds)}s > {timeout_seconds}s)'
        ),
    )


def _transition(
    job: ProvisioningJobState,
    *,
    to_state: str,
    now: datetime,
    attempt: int | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    clear_error: bool = False,
) -> ProvisioningJobState:
    allowed = ALLOWED_TRANSITIONS.get(job.state, frozenset())
    if to_state not in allowed:
        raise InvalidStateTransition(job.state, to_state)

    return replace(
        job,
        state=to_state,
        attempt=attempt if attempt is not None else job.attempt,
        state_entered_at=now,
        finished_at=now if to_state in TERMINAL_STATES else None,
        last_error_code=None if clear_error else error_code,
        last_error_detail=None if clear_error else error_detail,
        started_at=job.started_at or now,
    )


def _require_aware_datetime(value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError('now must be timezone-aware')
