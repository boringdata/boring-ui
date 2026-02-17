"""Sprite bearer rotation runbook and smoke sequence.

Bead: bd-223o.15.3 (J3)

Codifies the rotation procedure for the static server-side Sprite bearer
token used by the control plane proxy. The token is sourced from Modal
secrets and injected into workspace-plane requests via
``proxy_security.build_proxy_config()``.

Rotation steps:
  1. Generate a cryptographically strong replacement token.
  2. Update the Modal secret with the new value.
  3. Redeploy the control plane to pick up the new token.
  4. Verify runtime proxy health (smoke sequence).
  5. Confirm old token is no longer accepted.

The rotation is zero-downtime when executed correctly: Modal redeploy
replaces running containers atomically, and the Sprite runtime accepts
the new bearer on the next proxied request.

Smoke checks validate post-rotation health without credential leakage.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class RotationPhase(Enum):
    """Phases of the Sprite bearer rotation procedure."""

    GENERATE = 'generate'
    UPDATE_SECRET = 'update_secret'
    REDEPLOY = 'redeploy'
    SMOKE_TEST = 'smoke_test'
    CONFIRM_OLD_REVOKED = 'confirm_old_revoked'


class SmokeCheckType(Enum):
    """Types of post-rotation smoke checks."""

    PROXY_HEALTH = 'proxy_health'
    AUTH_ROUND_TRIP = 'auth_round_trip'
    RESPONSE_REDACTION = 'response_redaction'
    OLD_TOKEN_REJECTED = 'old_token_rejected'


@dataclass(frozen=True, slots=True)
class RotationStep:
    """Single step in the rotation runbook.

    Attributes:
        phase: Which rotation phase this step belongs to.
        order: Execution order (1-indexed).
        action: Human-readable action description.
        command: Shell command or API call template.
        rollback: What to do if this step fails.
        timeout_seconds: Max time before escalation.
    """

    phase: RotationPhase
    order: int
    action: str
    command: str
    rollback: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class SmokeCheck:
    """Post-rotation smoke check specification.

    Attributes:
        check_type: Category of the smoke check.
        description: What is being validated.
        endpoint: API path or URL to test.
        expected_status: Expected HTTP status code.
        must_not_contain: Strings that must NOT appear in the response.
    """

    check_type: SmokeCheckType
    description: str
    endpoint: str
    expected_status: int
    must_not_contain: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RotationRunbook:
    """Complete Sprite bearer rotation runbook.

    Attributes:
        steps: Ordered rotation steps.
        smoke_checks: Post-rotation verification checks.
        owner: Escalation owner from the SLO catalog.
        estimated_duration_minutes: Expected total rotation time.
    """

    steps: tuple[RotationStep, ...]
    smoke_checks: tuple[SmokeCheck, ...]
    owner: str
    estimated_duration_minutes: int

    @property
    def phases(self) -> tuple[RotationPhase, ...]:
        """Distinct phases in execution order."""
        seen = set()
        result = []
        for step in self.steps:
            if step.phase not in seen:
                seen.add(step.phase)
                result.append(step.phase)
        return tuple(result)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def smoke_check_count(self) -> int:
        return len(self.smoke_checks)


# ── Token generation ────────────────────────────────────────────────


def generate_sprite_bearer_token(length: int = 48) -> str:
    """Generate a cryptographically strong Sprite bearer token.

    Uses ``secrets.token_urlsafe()`` for URL-safe characters suitable
    for HTTP Bearer headers.

    Args:
        length: Number of random bytes (output is ~4/3 longer base64).

    Returns:
        URL-safe bearer token string.
    """
    if length < 32:
        raise ValueError('Token length must be >= 32 bytes for security')
    return secrets.token_urlsafe(length)


# ── Runbook factory ─────────────────────────────────────────────────


def build_sprite_rotation_runbook() -> RotationRunbook:
    """Build the canonical Sprite bearer rotation runbook.

    Returns:
        RotationRunbook with all steps and smoke checks.
    """
    steps = (
        RotationStep(
            phase=RotationPhase.GENERATE,
            order=1,
            action='Generate new Sprite bearer token',
            command='python3 -c "from control_plane.app.operations.sprite_rotation import generate_sprite_bearer_token; print(generate_sprite_bearer_token())"',
            rollback='No action needed — token is not yet deployed.',
            timeout_seconds=10,
        ),
        RotationStep(
            phase=RotationPhase.UPDATE_SECRET,
            order=2,
            action='Update Modal secret with new token',
            command='modal secret set sprite-bearer SPRITE_BEARER_TOKEN=<new_token>',
            rollback='Verify old Modal secret is still active: modal secret list.',
            timeout_seconds=30,
        ),
        RotationStep(
            phase=RotationPhase.UPDATE_SECRET,
            order=3,
            action='Verify Modal secret was updated',
            command='modal secret list | grep sprite-bearer',
            rollback='Re-run secret update from step 2.',
            timeout_seconds=15,
        ),
        RotationStep(
            phase=RotationPhase.REDEPLOY,
            order=4,
            action='Redeploy control plane to pick up new secret',
            command='modal deploy modal_app.py',
            rollback='Rollback: modal app rollback boring-ui.',
            timeout_seconds=120,
        ),
        RotationStep(
            phase=RotationPhase.REDEPLOY,
            order=5,
            action='Wait for new deployment to be healthy',
            command='curl -sf https://<control-plane-host>/health',
            rollback='Check Modal logs: modal app logs boring-ui.',
            timeout_seconds=60,
        ),
        RotationStep(
            phase=RotationPhase.SMOKE_TEST,
            order=6,
            action='Run post-rotation smoke sequence',
            command='python3 -m pytest tests/smoke/test_rotation_smoke.py -v',
            rollback='If smoke fails, rollback deployment: modal app rollback boring-ui.',
            timeout_seconds=120,
        ),
        RotationStep(
            phase=RotationPhase.CONFIRM_OLD_REVOKED,
            order=7,
            action='Confirm old bearer token is no longer accepted',
            command='curl -sf -H "Authorization: Bearer <old_token>" https://<runtime-host>/health | grep -q 401',
            rollback='If old token still works, the runtime may need restart.',
            timeout_seconds=30,
        ),
    )

    smoke_checks = (
        SmokeCheck(
            check_type=SmokeCheckType.PROXY_HEALTH,
            description='Control plane health endpoint returns 200',
            endpoint='/health',
            expected_status=200,
        ),
        SmokeCheck(
            check_type=SmokeCheckType.AUTH_ROUND_TRIP,
            description='Authenticated user can reach /api/v1/me',
            endpoint='/api/v1/me',
            expected_status=200,
        ),
        SmokeCheck(
            check_type=SmokeCheckType.RESPONSE_REDACTION,
            description='Proxied response does not leak bearer token',
            endpoint='/api/v1/workspaces/{workspace_id}/proxy/health',
            expected_status=200,
            must_not_contain=(
                'sprite-bearer',
                'x-runtime-token',
                'x-service-role',
            ),
        ),
        SmokeCheck(
            check_type=SmokeCheckType.OLD_TOKEN_REJECTED,
            description='Old bearer token is rejected by runtime',
            endpoint='/runtime/health',
            expected_status=401,
        ),
    )

    return RotationRunbook(
        steps=steps,
        smoke_checks=smoke_checks,
        owner='runtime_owner',
        estimated_duration_minutes=10,
    )


DEFAULT_ROTATION_RUNBOOK = build_sprite_rotation_runbook()


# ── Validation ──────────────────────────────────────────────────────


REQUIRED_PHASES = frozenset(RotationPhase)
REQUIRED_SMOKE_TYPES = frozenset({
    SmokeCheckType.PROXY_HEALTH,
    SmokeCheckType.AUTH_ROUND_TRIP,
    SmokeCheckType.RESPONSE_REDACTION,
    SmokeCheckType.OLD_TOKEN_REJECTED,
})


def validate_rotation_runbook(runbook: RotationRunbook) -> None:
    """Validate that a rotation runbook covers all required phases.

    Raises:
        ValueError: If any required phase or smoke check type is missing.
    """
    covered_phases = {step.phase for step in runbook.steps}
    missing_phases = REQUIRED_PHASES - covered_phases
    if missing_phases:
        raise ValueError(
            f'Rotation runbook missing phases: '
            f'{sorted(p.value for p in missing_phases)}'
        )

    covered_checks = {check.check_type for check in runbook.smoke_checks}
    missing_checks = REQUIRED_SMOKE_TYPES - covered_checks
    if missing_checks:
        raise ValueError(
            f'Rotation runbook missing smoke checks: '
            f'{sorted(c.value for c in missing_checks)}'
        )

    # Steps must be in order.
    orders = [step.order for step in runbook.steps]
    if orders != sorted(orders):
        raise ValueError('Rotation steps are not in ascending order')

    # All steps must have non-empty rollback instructions.
    for step in runbook.steps:
        if not step.rollback.strip():
            raise ValueError(
                f'Step {step.order} ({step.action!r}) has no rollback plan'
            )

    # Owner must match the escalation model.
    if not runbook.owner:
        raise ValueError('Rotation runbook has no owner')
