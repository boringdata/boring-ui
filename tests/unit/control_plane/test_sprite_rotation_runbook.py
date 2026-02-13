"""Sprite bearer rotation runbook and smoke sequence tests.

Bead: bd-223o.15.3 (J3)

Validates:
  - Runbook covers all required rotation phases
  - Steps are ordered and have rollback instructions
  - Smoke checks cover proxy health, auth, redaction, and revocation
  - Token generation produces cryptographically strong output
  - Validation rejects incomplete runbooks
  - Runbook owner matches escalation model
  - Default runbook passes all validation
  - Frozen dataclass invariants hold
"""

from __future__ import annotations

import pytest

from control_plane.app.operations.sprite_rotation import (
    DEFAULT_ROTATION_RUNBOOK,
    REQUIRED_PHASES,
    REQUIRED_SMOKE_TYPES,
    RotationPhase,
    RotationRunbook,
    RotationStep,
    SmokeCheck,
    SmokeCheckType,
    build_sprite_rotation_runbook,
    generate_sprite_bearer_token,
    validate_rotation_runbook,
)


@pytest.fixture
def runbook():
    return DEFAULT_ROTATION_RUNBOOK


# =====================================================================
# 1. Phase coverage
# =====================================================================


class TestPhaseCoverage:
    """Runbook must cover all rotation phases."""

    def test_all_required_phases_covered(self, runbook):
        covered = {step.phase for step in runbook.steps}
        assert REQUIRED_PHASES.issubset(covered), (
            f'Missing phases: {REQUIRED_PHASES - covered}'
        )

    def test_generate_phase_present(self, runbook):
        phases = runbook.phases
        assert RotationPhase.GENERATE in phases

    def test_update_secret_phase_present(self, runbook):
        phases = runbook.phases
        assert RotationPhase.UPDATE_SECRET in phases

    def test_redeploy_phase_present(self, runbook):
        phases = runbook.phases
        assert RotationPhase.REDEPLOY in phases

    def test_smoke_test_phase_present(self, runbook):
        phases = runbook.phases
        assert RotationPhase.SMOKE_TEST in phases

    def test_confirm_old_revoked_phase_present(self, runbook):
        phases = runbook.phases
        assert RotationPhase.CONFIRM_OLD_REVOKED in phases


# =====================================================================
# 2. Step ordering and rollback
# =====================================================================


class TestStepOrdering:
    """Steps must be in ascending order with rollback instructions."""

    def test_steps_in_ascending_order(self, runbook):
        orders = [step.order for step in runbook.steps]
        assert orders == sorted(orders)

    def test_no_duplicate_order_numbers(self, runbook):
        orders = [step.order for step in runbook.steps]
        assert len(orders) == len(set(orders))

    def test_all_steps_have_rollback(self, runbook):
        for step in runbook.steps:
            assert step.rollback.strip(), (
                f'Step {step.order} ({step.action!r}) has no rollback'
            )

    def test_all_steps_have_command(self, runbook):
        for step in runbook.steps:
            assert step.command.strip(), (
                f'Step {step.order} ({step.action!r}) has no command'
            )

    def test_all_steps_have_timeout(self, runbook):
        for step in runbook.steps:
            assert step.timeout_seconds > 0

    def test_generate_is_first(self, runbook):
        assert runbook.steps[0].phase == RotationPhase.GENERATE

    def test_confirm_revoked_is_last(self, runbook):
        assert runbook.steps[-1].phase == RotationPhase.CONFIRM_OLD_REVOKED


# =====================================================================
# 3. Smoke check coverage
# =====================================================================


class TestSmokeCheckCoverage:
    """Smoke checks must cover all required verification types."""

    def test_all_required_smoke_types_covered(self, runbook):
        covered = {check.check_type for check in runbook.smoke_checks}
        assert REQUIRED_SMOKE_TYPES.issubset(covered), (
            f'Missing smoke checks: {REQUIRED_SMOKE_TYPES - covered}'
        )

    def test_proxy_health_check_present(self, runbook):
        types = {check.check_type for check in runbook.smoke_checks}
        assert SmokeCheckType.PROXY_HEALTH in types

    def test_auth_round_trip_check_present(self, runbook):
        types = {check.check_type for check in runbook.smoke_checks}
        assert SmokeCheckType.AUTH_ROUND_TRIP in types

    def test_response_redaction_check_present(self, runbook):
        types = {check.check_type for check in runbook.smoke_checks}
        assert SmokeCheckType.RESPONSE_REDACTION in types

    def test_old_token_rejected_check_present(self, runbook):
        types = {check.check_type for check in runbook.smoke_checks}
        assert SmokeCheckType.OLD_TOKEN_REJECTED in types

    def test_redaction_check_validates_no_leakage(self, runbook):
        redaction_check = next(
            c for c in runbook.smoke_checks
            if c.check_type == SmokeCheckType.RESPONSE_REDACTION
        )
        assert len(redaction_check.must_not_contain) > 0
        assert 'sprite-bearer' in redaction_check.must_not_contain

    def test_all_checks_have_endpoint(self, runbook):
        for check in runbook.smoke_checks:
            assert check.endpoint.strip()

    def test_all_checks_have_expected_status(self, runbook):
        for check in runbook.smoke_checks:
            assert check.expected_status in (200, 401, 403)


# =====================================================================
# 4. Token generation
# =====================================================================


class TestTokenGeneration:
    """Token generation produces cryptographically strong output."""

    def test_default_token_length(self):
        token = generate_sprite_bearer_token()
        assert len(token) > 40  # 48 bytes → ~64 chars base64.

    def test_two_tokens_are_unique(self):
        t1 = generate_sprite_bearer_token()
        t2 = generate_sprite_bearer_token()
        assert t1 != t2

    def test_token_is_url_safe(self):
        token = generate_sprite_bearer_token()
        # URL-safe base64 uses only [A-Za-z0-9_-].
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_minimum_length_enforced(self):
        with pytest.raises(ValueError, match='32 bytes'):
            generate_sprite_bearer_token(length=16)

    def test_custom_length(self):
        token = generate_sprite_bearer_token(length=64)
        assert len(token) > 64  # Base64 expands.


# =====================================================================
# 5. Validation
# =====================================================================


class TestValidation:
    """validate_rotation_runbook catches incomplete runbooks."""

    def test_default_runbook_passes_validation(self, runbook):
        validate_rotation_runbook(runbook)  # Should not raise.

    def test_built_runbook_passes_validation(self):
        runbook = build_sprite_rotation_runbook()
        validate_rotation_runbook(runbook)

    def test_missing_phase_raises(self):
        # Only include GENERATE phase.
        runbook = RotationRunbook(
            steps=(
                RotationStep(
                    phase=RotationPhase.GENERATE,
                    order=1,
                    action='Generate token',
                    command='echo token',
                    rollback='No action.',
                    timeout_seconds=10,
                ),
            ),
            smoke_checks=DEFAULT_ROTATION_RUNBOOK.smoke_checks,
            owner='runtime_owner',
            estimated_duration_minutes=5,
        )
        with pytest.raises(ValueError, match='missing phases'):
            validate_rotation_runbook(runbook)

    def test_missing_smoke_check_raises(self):
        # Only include proxy health check.
        runbook = RotationRunbook(
            steps=DEFAULT_ROTATION_RUNBOOK.steps,
            smoke_checks=(
                SmokeCheck(
                    check_type=SmokeCheckType.PROXY_HEALTH,
                    description='Health check',
                    endpoint='/health',
                    expected_status=200,
                ),
            ),
            owner='runtime_owner',
            estimated_duration_minutes=5,
        )
        with pytest.raises(ValueError, match='missing smoke checks'):
            validate_rotation_runbook(runbook)

    def test_unordered_steps_raises(self):
        steps = list(DEFAULT_ROTATION_RUNBOOK.steps)
        # Reverse order.
        steps.reverse()
        runbook = RotationRunbook(
            steps=tuple(steps),
            smoke_checks=DEFAULT_ROTATION_RUNBOOK.smoke_checks,
            owner='runtime_owner',
            estimated_duration_minutes=5,
        )
        with pytest.raises(ValueError, match='not in ascending order'):
            validate_rotation_runbook(runbook)

    def test_empty_rollback_raises(self):
        steps = list(DEFAULT_ROTATION_RUNBOOK.steps)
        bad_step = RotationStep(
            phase=steps[0].phase,
            order=steps[0].order,
            action=steps[0].action,
            command=steps[0].command,
            rollback='',  # Empty rollback.
            timeout_seconds=steps[0].timeout_seconds,
        )
        steps[0] = bad_step
        runbook = RotationRunbook(
            steps=tuple(steps),
            smoke_checks=DEFAULT_ROTATION_RUNBOOK.smoke_checks,
            owner='runtime_owner',
            estimated_duration_minutes=5,
        )
        with pytest.raises(ValueError, match='no rollback'):
            validate_rotation_runbook(runbook)

    def test_empty_owner_raises(self):
        runbook = RotationRunbook(
            steps=DEFAULT_ROTATION_RUNBOOK.steps,
            smoke_checks=DEFAULT_ROTATION_RUNBOOK.smoke_checks,
            owner='',
            estimated_duration_minutes=5,
        )
        with pytest.raises(ValueError, match='no owner'):
            validate_rotation_runbook(runbook)


# =====================================================================
# 6. Runbook properties
# =====================================================================


class TestRunbookProperties:
    """Runbook aggregate properties are correct."""

    def test_step_count(self, runbook):
        assert runbook.step_count == len(runbook.steps)
        assert runbook.step_count >= 5  # At least one per phase.

    def test_smoke_check_count(self, runbook):
        assert runbook.smoke_check_count == len(runbook.smoke_checks)
        assert runbook.smoke_check_count >= 4

    def test_owner_is_runtime_owner(self, runbook):
        assert runbook.owner == 'runtime_owner'

    def test_estimated_duration_reasonable(self, runbook):
        assert 5 <= runbook.estimated_duration_minutes <= 30

    def test_phases_property_in_order(self, runbook):
        phases = runbook.phases
        assert phases[0] == RotationPhase.GENERATE
        assert phases[-1] == RotationPhase.CONFIRM_OLD_REVOKED


# =====================================================================
# 7. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:
    """All spec types are frozen."""

    def test_rotation_step_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.steps[0].action = 'mutated'

    def test_smoke_check_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.smoke_checks[0].endpoint = 'mutated'

    def test_runbook_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.owner = 'mutated'


# =====================================================================
# 8. Idempotency
# =====================================================================


class TestIdempotency:
    """build_sprite_rotation_runbook returns equivalent results."""

    def test_two_builds_have_same_steps(self):
        r1 = build_sprite_rotation_runbook()
        r2 = build_sprite_rotation_runbook()
        assert len(r1.steps) == len(r2.steps)
        for s1, s2 in zip(r1.steps, r2.steps):
            assert s1.phase == s2.phase
            assert s1.order == s2.order
            assert s1.action == s2.action

    def test_default_matches_build(self):
        fresh = build_sprite_rotation_runbook()
        assert DEFAULT_ROTATION_RUNBOOK.step_count == fresh.step_count
        assert DEFAULT_ROTATION_RUNBOOK.owner == fresh.owner
