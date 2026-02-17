"""Cross-epic outage drill with request-id evidence capture.

Bead: bd-223o.15.5 (J5)

Defines structured outage drill scenarios that exercise upstream failure
(Supabase or Sprite) and recovery flows with request-correlated proof.

Each drill scenario specifies:
  - Failure injection: what upstream service fails and how
  - Expected degradation: what the user/operator should observe
  - Recovery action: runbook steps to restore service
  - Evidence capture: request IDs, timestamps, status codes proving recovery

Drill scenarios integrate with:
  - SLO alert catalog (J1): alerts should fire during failure
  - Stale job detector (J2): stuck jobs should be detected
  - Sprite rotation runbook (J3): rotation recovery path
  - Checksum failure runbook (J4): artifact recovery path

Evidence is captured as DrillEvidence entries with request correlation
for post-drill analysis and audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Sequence


class DrillType(Enum):
    """Categories of outage drill."""

    SUPABASE_AUTH_OUTAGE = 'supabase_auth_outage'
    SPRITE_RUNTIME_OUTAGE = 'sprite_runtime_outage'
    ARTIFACT_CORRUPTION = 'artifact_corruption'
    COMBINED_DEGRADATION = 'combined_degradation'


class EvidenceType(Enum):
    """Types of evidence captured during drill execution."""

    REQUEST_RESPONSE = 'request_response'
    ALERT_FIRED = 'alert_fired'
    JOB_TRANSITION = 'job_transition'
    RECOVERY_CONFIRMED = 'recovery_confirmed'
    LOG_ENTRY = 'log_entry'


@dataclass(frozen=True, slots=True)
class FailureInjection:
    """Describes how to simulate an upstream failure.

    Attributes:
        target_service: Which upstream service to disrupt.
        method: How the failure is injected.
        duration_seconds: How long the failure persists.
        expected_error_codes: Error codes that should appear.
    """

    target_service: str
    method: str
    duration_seconds: int
    expected_error_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedDegradation:
    """What the system should exhibit during the failure.

    Attributes:
        affected_endpoints: API paths that degrade.
        expected_status_codes: HTTP status codes returned.
        alerts_expected: Alert keys that should fire.
        user_visible_impact: Human-readable impact description.
    """

    affected_endpoints: tuple[str, ...]
    expected_status_codes: tuple[int, ...]
    alerts_expected: tuple[str, ...]
    user_visible_impact: str


@dataclass(frozen=True, slots=True)
class RecoveryAction:
    """Steps to recover from the simulated failure.

    Attributes:
        runbook_reference: Which runbook to follow (J3, J4, etc.).
        steps: Ordered recovery step descriptions.
        max_recovery_minutes: Escalation threshold.
    """

    runbook_reference: str
    steps: tuple[str, ...]
    max_recovery_minutes: int


@dataclass(frozen=True, slots=True)
class DrillEvidence:
    """Single piece of evidence captured during drill execution.

    Attributes:
        evidence_type: Category of evidence.
        request_id: Correlation ID for tracing.
        timestamp: When the evidence was captured.
        endpoint: API path involved (if applicable).
        status_code: HTTP status code (if applicable).
        detail: Structured detail payload.
    """

    evidence_type: EvidenceType
    request_id: str
    timestamp: datetime
    endpoint: str = ''
    status_code: int | None = None
    detail: str = ''


@dataclass(frozen=True, slots=True)
class DrillScenario:
    """Complete outage drill scenario.

    Attributes:
        drill_type: Category of outage being drilled.
        name: Human-readable scenario name.
        description: Detailed scenario description.
        failure: How to inject the failure.
        degradation: Expected behavior during failure.
        recovery: How to recover.
        evidence_requirements: Minimum evidence entries needed.
        owner: Escalation owner responsible for the drill.
    """

    drill_type: DrillType
    name: str
    description: str
    failure: FailureInjection
    degradation: ExpectedDegradation
    recovery: RecoveryAction
    evidence_requirements: tuple[EvidenceType, ...]
    owner: str


@dataclass(frozen=True, slots=True)
class DrillResult:
    """Result of executing a drill scenario.

    Attributes:
        scenario: The drill that was executed.
        evidence: Collected evidence entries.
        passed: Whether the drill met all requirements.
        failure_reason: Why the drill failed (if applicable).
        duration_seconds: Total drill execution time.
    """

    scenario: DrillScenario
    evidence: tuple[DrillEvidence, ...]
    passed: bool
    failure_reason: str = ''
    duration_seconds: float = 0.0

    @property
    def evidence_by_type(self) -> dict[EvidenceType, list[DrillEvidence]]:
        result: dict[EvidenceType, list[DrillEvidence]] = {}
        for e in self.evidence:
            result.setdefault(e.evidence_type, []).append(e)
        return result

    @property
    def has_request_correlation(self) -> bool:
        """All evidence entries have non-empty request IDs."""
        return all(e.request_id for e in self.evidence)


# ── Scenario factory ────────────────────────────────────────────────


def build_supabase_auth_outage_scenario() -> DrillScenario:
    """Supabase auth outage: JWKS endpoint unreachable."""
    return DrillScenario(
        drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
        name='Supabase Auth Outage',
        description=(
            'Simulate Supabase JWKS endpoint becoming unreachable. '
            'Existing sessions should continue working (cached keys), '
            'but new logins fail. Recovery: wait for JWKS restore or '
            'fall back to static JWT secret.'
        ),
        failure=FailureInjection(
            target_service='supabase_auth',
            method='block_jwks_endpoint',
            duration_seconds=300,
            expected_error_codes=('jwks_fetch_error',),
        ),
        degradation=ExpectedDegradation(
            affected_endpoints=(
                '/auth/callback',
                '/api/v1/me',
            ),
            expected_status_codes=(401, 502),
            alerts_expected=('api_5xx_error_rate_burn',),
            user_visible_impact=(
                'New browser logins fail with auth error. '
                'Existing sessions with cached keys continue working.'
            ),
        ),
        recovery=RecoveryAction(
            runbook_reference='J1-SLO-alerts',
            steps=(
                'Verify JWKS endpoint status',
                'If JWKS down: enable static JWT secret fallback',
                'Monitor api_5xx_error_rate_burn alert resolution',
                'Verify new logins succeed',
                'Disable static fallback when JWKS recovers',
            ),
            max_recovery_minutes=15,
        ),
        evidence_requirements=(
            EvidenceType.REQUEST_RESPONSE,
            EvidenceType.ALERT_FIRED,
            EvidenceType.RECOVERY_CONFIRMED,
        ),
        owner='backend_oncall_owner',
    )


def build_sprite_runtime_outage_scenario() -> DrillScenario:
    """Sprite runtime outage: workspace proxy returns 502."""
    return DrillScenario(
        drill_type=DrillType.SPRITE_RUNTIME_OUTAGE,
        name='Sprite Runtime Outage',
        description=(
            'Simulate Sprite runtime becoming unreachable. '
            'Workspace proxy requests fail with 502. '
            'Provisioning jobs in health_check state become stale. '
            'Recovery: restart runtime or rotate bearer token.'
        ),
        failure=FailureInjection(
            target_service='sprite_runtime',
            method='stop_sprite_container',
            duration_seconds=180,
            expected_error_codes=('STEP_TIMEOUT', 'proxy_upstream_error'),
        ),
        degradation=ExpectedDegradation(
            affected_endpoints=(
                '/api/v1/workspaces/{id}/proxy/*',
                '/api/v1/workspaces/{id}/runtime',
            ),
            expected_status_codes=(502, 504),
            alerts_expected=('provisioning_error_rate_burn',),
            user_visible_impact=(
                'Active workspace sessions fail to load. '
                'New provisioning stuck at health_check. '
                'OnboardingStateGate shows error state.'
            ),
        ),
        recovery=RecoveryAction(
            runbook_reference='J3-sprite-rotation',
            steps=(
                'Verify Sprite container status',
                'If container down: restart via Modal',
                'Run stale job sweep to transition stuck jobs',
                'Retry failed provisioning jobs',
                'Verify workspace proxy health',
            ),
            max_recovery_minutes=10,
        ),
        evidence_requirements=(
            EvidenceType.REQUEST_RESPONSE,
            EvidenceType.JOB_TRANSITION,
            EvidenceType.ALERT_FIRED,
            EvidenceType.RECOVERY_CONFIRMED,
        ),
        owner='runtime_owner',
    )


def build_artifact_corruption_scenario() -> DrillScenario:
    """Artifact corruption: checksum mismatch during provisioning."""
    return DrillScenario(
        drill_type=DrillType.ARTIFACT_CORRUPTION,
        name='Artifact Checksum Corruption',
        description=(
            'Simulate bundle artifact corruption. Provisioning fails '
            'at uploading_artifact with CHECKSUM_MISMATCH. Recovery: '
            'rebuild artifact or rollback to previous release.'
        ),
        failure=FailureInjection(
            target_service='artifact_store',
            method='corrupt_bundle_checksum',
            duration_seconds=600,
            expected_error_codes=('CHECKSUM_MISMATCH',),
        ),
        degradation=ExpectedDegradation(
            affected_endpoints=(
                '/api/v1/workspaces',
            ),
            expected_status_codes=(500,),
            alerts_expected=('provisioning_error_rate_burn',),
            user_visible_impact=(
                'New workspace creation fails. '
                'Existing workspaces unaffected.'
            ),
        ),
        recovery=RecoveryAction(
            runbook_reference='J4-checksum-failure',
            steps=(
                'Identify affected release and checksum',
                'Verify artifact integrity independently',
                'Rebuild artifact from source',
                'Update release catalog with correct checksum',
                'Retry failed provisioning jobs',
                'Send resolution communication',
            ),
            max_recovery_minutes=30,
        ),
        evidence_requirements=(
            EvidenceType.REQUEST_RESPONSE,
            EvidenceType.JOB_TRANSITION,
            EvidenceType.RECOVERY_CONFIRMED,
        ),
        owner='runtime_owner',
    )


def build_drill_catalog() -> tuple[DrillScenario, ...]:
    """Build the complete set of outage drill scenarios."""
    return (
        build_supabase_auth_outage_scenario(),
        build_sprite_runtime_outage_scenario(),
        build_artifact_corruption_scenario(),
    )


DEFAULT_DRILL_CATALOG = build_drill_catalog()


# ── Required contracts ──────────────────────────────────────────────

REQUIRED_DRILL_TYPES = frozenset({
    DrillType.SUPABASE_AUTH_OUTAGE,
    DrillType.SPRITE_RUNTIME_OUTAGE,
    DrillType.ARTIFACT_CORRUPTION,
})


# ── Validation ──────────────────────────────────────────────────────


def validate_drill_catalog(
    scenarios: Sequence[DrillScenario],
) -> None:
    """Validate that the drill catalog covers all required scenarios.

    Raises:
        ValueError: If required drill types are missing or scenarios
            are incomplete.
    """
    covered_types = {s.drill_type for s in scenarios}
    missing = REQUIRED_DRILL_TYPES - covered_types
    if missing:
        raise ValueError(
            f'Missing drill types: {sorted(t.value for t in missing)}'
        )

    for scenario in scenarios:
        if not scenario.failure.expected_error_codes:
            raise ValueError(
                f'Drill {scenario.name!r} has no expected error codes'
            )
        if not scenario.degradation.alerts_expected:
            raise ValueError(
                f'Drill {scenario.name!r} has no expected alerts'
            )
        if not scenario.recovery.steps:
            raise ValueError(
                f'Drill {scenario.name!r} has no recovery steps'
            )
        if not scenario.evidence_requirements:
            raise ValueError(
                f'Drill {scenario.name!r} has no evidence requirements'
            )
        if EvidenceType.RECOVERY_CONFIRMED not in scenario.evidence_requirements:
            raise ValueError(
                f'Drill {scenario.name!r} must require RECOVERY_CONFIRMED evidence'
            )
        if not scenario.owner:
            raise ValueError(
                f'Drill {scenario.name!r} has no owner'
            )


def validate_drill_result(result: DrillResult) -> list[str]:
    """Validate drill result meets evidence requirements.

    Returns:
        List of validation errors (empty if all requirements met).
    """
    errors: list[str] = []

    # All required evidence types present.
    collected_types = {e.evidence_type for e in result.evidence}
    for req in result.scenario.evidence_requirements:
        if req not in collected_types:
            errors.append(f'Missing evidence type: {req.value}')

    # All evidence has request correlation.
    if not result.has_request_correlation:
        errors.append('Not all evidence has request ID correlation')

    return errors
