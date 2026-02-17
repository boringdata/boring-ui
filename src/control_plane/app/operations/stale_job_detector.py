"""Stale provisioning-job detector and repair action.

Bead: bd-223o.15.2 (J2)

Scans active provisioning jobs for those exceeding step timeout windows
and transitions them to actionable error states. Integrates with the
state machine's ``apply_step_timeout()`` for deterministic timeout
detection.

Usage::

    detector = StaleJobDetector()
    report = detector.sweep(active_jobs, now=datetime.now(UTC))
    # report.stale contains jobs transitioned to error
    # report.healthy contains jobs still within timeout

The detector feeds into the ``provisioning_error_rate_burn`` alert
(J1) which groups by ``last_error_code``, so stale jobs surface as
STEP_TIMEOUT in operational dashboards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

from control_plane.app.provisioning.state_machine import (
    ACTIVE_STATES,
    DEFAULT_STEP_TIMEOUT_SECONDS,
    STEP_TIMEOUT_CODE,
    TERMINAL_STATES,
    ProvisioningJobState,
    apply_step_timeout,
)


@dataclass(frozen=True, slots=True)
class StaleJobEntry:
    """A single stale job with its before/after state."""

    before: ProvisioningJobState
    after: ProvisioningJobState
    elapsed_seconds: float
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class SweepReport:
    """Result of a stale-job sweep across active provisioning jobs.

    Attributes:
        stale: Jobs that exceeded their timeout and were transitioned.
        healthy: Active jobs still within timeout.
        skipped: Terminal or queued jobs that were not evaluated.
        sweep_ts: Timestamp of the sweep.
    """

    stale: tuple[StaleJobEntry, ...]
    healthy: tuple[ProvisioningJobState, ...]
    skipped: tuple[ProvisioningJobState, ...]
    sweep_ts: datetime

    @property
    def stale_count(self) -> int:
        return len(self.stale)

    @property
    def healthy_count(self) -> int:
        return len(self.healthy)

    @property
    def total_scanned(self) -> int:
        return len(self.stale) + len(self.healthy) + len(self.skipped)

    @property
    def stale_by_state(self) -> dict[str, int]:
        """Count of stale jobs grouped by their original state."""
        counts: dict[str, int] = {}
        for entry in self.stale:
            state = entry.before.state
            counts[state] = counts.get(state, 0) + 1
        return counts


class StaleJobDetector:
    """Detects stuck provisioning jobs and applies timeout transitions.

    Args:
        step_timeouts: Per-state timeout overrides. Defaults to the
            canonical provisioning step timeouts.
    """

    def __init__(
        self,
        step_timeouts: Mapping[str, int] | None = None,
    ) -> None:
        self._step_timeouts = step_timeouts or DEFAULT_STEP_TIMEOUT_SECONDS

    def sweep(
        self,
        jobs: Sequence[ProvisioningJobState],
        *,
        now: datetime,
    ) -> SweepReport:
        """Scan all jobs and detect/repair stale ones.

        Args:
            jobs: All provisioning jobs to evaluate.
            now: Current timestamp (must be timezone-aware).

        Returns:
            SweepReport with categorized results.
        """
        stale: list[StaleJobEntry] = []
        healthy: list[ProvisioningJobState] = []
        skipped: list[ProvisioningJobState] = []

        for job in jobs:
            # Skip terminal and queued jobs.
            if job.state in TERMINAL_STATES or job.state == 'queued':
                skipped.append(job)
                continue

            # Skip jobs without timestamp (cannot evaluate timeout).
            if job.state_entered_at is None:
                skipped.append(job)
                continue

            # Apply timeout check.
            result = apply_step_timeout(
                job, now=now, step_timeouts=self._step_timeouts,
            )

            if result.state == 'error' and result is not job:
                timeout_seconds = self._step_timeouts.get(job.state, 0)
                elapsed = (now - job.state_entered_at).total_seconds()
                stale.append(StaleJobEntry(
                    before=job,
                    after=result,
                    elapsed_seconds=elapsed,
                    timeout_seconds=timeout_seconds,
                ))
            else:
                healthy.append(job)

        return SweepReport(
            stale=tuple(stale),
            healthy=tuple(healthy),
            skipped=tuple(skipped),
            sweep_ts=now,
        )

    def detect_only(
        self,
        jobs: Sequence[ProvisioningJobState],
        *,
        now: datetime,
    ) -> list[ProvisioningJobState]:
        """Return only jobs that are stale, without applying transitions.

        Useful for dry-run detection or alerting without mutation.
        """
        report = self.sweep(jobs, now=now)
        return [entry.before for entry in report.stale]
