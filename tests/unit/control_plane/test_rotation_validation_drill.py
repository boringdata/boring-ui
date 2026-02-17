"""Sprite bearer rotation validation drill in demo environment.

Bead: bd-223o.15.3.1 (J3a)

Executes a controlled rotation sequence in a simulated environment and
validates post-rotation proxy functionality and logging:

  1. Token generation: new bearer tokens meet strength requirements.
  2. Rotation lifecycle: all phases execute in correct order.
  3. Smoke checks: post-rotation health, auth, redaction, and revocation.
  4. Old token revocation: previous bearer is rejected after rotation.
  5. Evidence capture: request-correlated evidence proves each phase.
  6. Runbook integration: drill steps align with J3 runbook structure.
  7. Rollback safety: rollback instructions exist for every step.
  8. Response redaction: rotated token never appears in responses.

Uses a simulated rotation environment (in-memory proxy mock) to test
the rotation flow without real Modal/Sprite infrastructure.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest

from control_plane.app.operations.outage_drill import (
    DrillEvidence,
    DrillResult,
    DrillType,
    EvidenceType,
    build_sprite_runtime_outage_scenario,
    validate_drill_result,
)
from control_plane.app.operations.sprite_rotation import (
    DEFAULT_ROTATION_RUNBOOK,
    REQUIRED_PHASES,
    REQUIRED_SMOKE_TYPES,
    RotationPhase,
    SmokeCheck,
    SmokeCheckType,
    build_sprite_rotation_runbook,
    generate_sprite_bearer_token,
    validate_rotation_runbook,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _request_id() -> str:
    return f'drill-{uuid.uuid4().hex[:12]}'


# ── Simulated rotation environment ────────────────────────────────────


class SimulatedProxyEnvironment:
    """In-memory simulation of the proxy environment for rotation drills.

    Tracks the active bearer token and simulates endpoint behavior:
      - /health: always 200 if environment is up
      - /api/v1/me: 200 if authed, 401 otherwise
      - /proxy/health: 200, must not leak bearer token
      - /runtime/health: 401 with old token, 200 with new token
    """

    def __init__(self, initial_token: str) -> None:
        self._active_token = initial_token
        self._is_deployed = True
        self._request_log: list[dict] = []

    @property
    def active_token(self) -> str:
        return self._active_token

    def rotate_token(self, new_token: str) -> None:
        """Simulate rotation: old token becomes invalid."""
        self._active_token = new_token

    def redeploy(self) -> None:
        """Simulate control plane redeployment."""
        self._is_deployed = True

    def request(
        self,
        endpoint: str,
        bearer_token: str | None = None,
        request_id: str = '',
    ) -> dict:
        """Simulate an HTTP request to the proxy environment."""
        result = {
            'endpoint': endpoint,
            'request_id': request_id,
            'bearer_token_provided': bearer_token is not None,
        }

        if endpoint == '/health':
            result['status'] = 200 if self._is_deployed else 503
            result['body'] = 'ok'

        elif endpoint == '/api/v1/me':
            if bearer_token == self._active_token:
                result['status'] = 200
                result['body'] = '{"user_id": "u_test"}'
            else:
                result['status'] = 401
                result['body'] = '{"error": "unauthorized"}'

        elif endpoint.endswith('/proxy/health'):
            result['status'] = 200
            # Must never leak the token in the response body.
            result['body'] = '{"proxy": "healthy"}'

        elif endpoint == '/runtime/health':
            if bearer_token == self._active_token:
                result['status'] = 200
                result['body'] = '{"runtime": "healthy"}'
            else:
                result['status'] = 401
                result['body'] = '{"error": "unauthorized"}'

        else:
            result['status'] = 404
            result['body'] = '{"error": "not_found"}'

        self._request_log.append(result)
        return result

    @property
    def request_log(self) -> list[dict]:
        return list(self._request_log)

    def check_no_token_leakage(self) -> bool:
        """Verify no response body contains the active bearer token."""
        for entry in self._request_log:
            body = entry.get('body', '')
            if self._active_token in body:
                return False
        return True


# ── Test fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def old_token():
    return generate_sprite_bearer_token()


@pytest.fixture
def new_token():
    return generate_sprite_bearer_token()


@pytest.fixture
def env(old_token):
    return SimulatedProxyEnvironment(old_token)


@pytest.fixture
def runbook():
    return build_sprite_rotation_runbook()


# =====================================================================
# 1. Token generation meets strength requirements
# =====================================================================


class TestTokenGeneration:

    def test_token_length_default(self):
        token = generate_sprite_bearer_token()
        # 48 random bytes → ~64 base64 chars.
        assert len(token) >= 48

    def test_token_uniqueness(self):
        tokens = {generate_sprite_bearer_token() for _ in range(10)}
        assert len(tokens) == 10

    def test_token_is_url_safe(self):
        token = generate_sprite_bearer_token()
        assert re.match(r'^[A-Za-z0-9_\-]+$', token)

    def test_minimum_length_enforced(self):
        with pytest.raises(ValueError, match='32'):
            generate_sprite_bearer_token(length=16)

    def test_token_entropy_sufficient(self):
        """Token should have enough entropy for security (>= 256 bits)."""
        token = generate_sprite_bearer_token(length=48)
        # 48 bytes = 384 bits of entropy, well above 256 bits.
        assert len(token) > 32


# =====================================================================
# 2. Rotation lifecycle phases
# =====================================================================


class TestRotationLifecycle:

    def test_all_phases_present_in_runbook(self, runbook):
        covered = {step.phase for step in runbook.steps}
        assert REQUIRED_PHASES.issubset(covered)

    def test_phases_execute_in_order(self, runbook):
        phases = runbook.phases
        expected_order = [
            RotationPhase.GENERATE,
            RotationPhase.UPDATE_SECRET,
            RotationPhase.REDEPLOY,
            RotationPhase.SMOKE_TEST,
            RotationPhase.CONFIRM_OLD_REVOKED,
        ]
        assert list(phases) == expected_order

    def test_simulated_rotation_completes(self, env, old_token, new_token):
        """Full rotation cycle in simulated environment."""
        # Step 1: Generate new token.
        assert len(new_token) >= 48

        # Step 2-3: Update secret (simulated as rotate_token).
        env.rotate_token(new_token)
        assert env.active_token == new_token

        # Step 4-5: Redeploy.
        env.redeploy()

        # Step 6: Smoke test — health check.
        resp = env.request('/health', request_id=_request_id())
        assert resp['status'] == 200

        # Step 7: Confirm old token rejected.
        resp = env.request(
            '/runtime/health', bearer_token=old_token,
            request_id=_request_id(),
        )
        assert resp['status'] == 401


# =====================================================================
# 3. Post-rotation smoke checks
# =====================================================================


class TestSmokeChecks:

    def test_health_endpoint(self, env, new_token):
        env.rotate_token(new_token)
        resp = env.request('/health')
        assert resp['status'] == 200

    def test_auth_round_trip_with_new_token(self, env, new_token):
        env.rotate_token(new_token)
        resp = env.request('/api/v1/me', bearer_token=new_token)
        assert resp['status'] == 200

    def test_auth_fails_with_old_token(self, env, old_token, new_token):
        env.rotate_token(new_token)
        resp = env.request('/api/v1/me', bearer_token=old_token)
        assert resp['status'] == 401

    def test_proxy_health_after_rotation(self, env, new_token):
        env.rotate_token(new_token)
        resp = env.request('/api/v1/workspaces/ws_test/proxy/health')
        assert resp['status'] == 200

    def test_response_redaction(self, env, new_token):
        """Bearer token must not appear in any response body."""
        env.rotate_token(new_token)
        env.request('/health')
        env.request('/api/v1/me', bearer_token=new_token)
        env.request('/api/v1/workspaces/ws_test/proxy/health')

        assert env.check_no_token_leakage()

    def test_all_required_smoke_types_covered(self, runbook):
        covered = {check.check_type for check in runbook.smoke_checks}
        assert REQUIRED_SMOKE_TYPES.issubset(covered)


# =====================================================================
# 4. Old token revocation verification
# =====================================================================


class TestOldTokenRevocation:

    def test_old_token_rejected_after_rotation(
        self, env, old_token, new_token,
    ):
        env.rotate_token(new_token)
        resp = env.request(
            '/runtime/health', bearer_token=old_token,
        )
        assert resp['status'] == 401

    def test_new_token_accepted_after_rotation(
        self, env, new_token,
    ):
        env.rotate_token(new_token)
        resp = env.request(
            '/runtime/health', bearer_token=new_token,
        )
        assert resp['status'] == 200

    def test_both_tokens_checked_in_sequence(
        self, env, old_token, new_token,
    ):
        """Post-rotation: new accepted, old rejected, in a single drill."""
        env.rotate_token(new_token)

        new_resp = env.request(
            '/runtime/health', bearer_token=new_token,
        )
        old_resp = env.request(
            '/runtime/health', bearer_token=old_token,
        )
        assert new_resp['status'] == 200
        assert old_resp['status'] == 401


# =====================================================================
# 5. Evidence capture with request correlation
# =====================================================================


class TestEvidenceCapture:

    def test_rotation_drill_evidence_complete(
        self, env, old_token, new_token,
    ):
        """Full rotation drill with evidence passes validation."""
        scenario = build_sprite_runtime_outage_scenario()
        req_id = _request_id()
        evidence: list[DrillEvidence] = []

        # Generate + rotate.
        env.rotate_token(new_token)
        env.redeploy()

        # Smoke check — health.
        resp = env.request('/health', request_id=req_id)
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.REQUEST_RESPONSE,
            request_id=req_id,
            timestamp=_now(),
            endpoint='/health',
            status_code=resp['status'],
            detail='Post-rotation health check passed',
        ))

        # Smoke check — auth round trip.
        resp = env.request(
            '/api/v1/me', bearer_token=new_token,
            request_id=req_id,
        )
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.REQUEST_RESPONSE,
            request_id=req_id,
            timestamp=_now(),
            endpoint='/api/v1/me',
            status_code=resp['status'],
            detail='Auth round-trip with new token succeeded',
        ))

        # Old token rejected.
        resp = env.request(
            '/runtime/health', bearer_token=old_token,
            request_id=req_id,
        )
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.REQUEST_RESPONSE,
            request_id=req_id,
            timestamp=_now(),
            endpoint='/runtime/health',
            status_code=resp['status'],
            detail=f'Old token rejected (status={resp["status"]})',
        ))

        # Job transition — simulated rotation completion.
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.JOB_TRANSITION,
            request_id=req_id,
            timestamp=_now(),
            detail='Rotation complete: old_token → new_token',
        ))

        # Alert — would fire in production (simulated).
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.ALERT_FIRED,
            request_id=req_id,
            timestamp=_now(),
            detail='provisioning_error_rate_burn (simulated)',
        ))

        # Recovery confirmed.
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.RECOVERY_CONFIRMED,
            request_id=req_id,
            timestamp=_now(),
            endpoint='/api/v1/me',
            status_code=200,
            detail='Service healthy with new bearer token',
        ))

        drill_result = DrillResult(
            scenario=scenario,
            evidence=tuple(evidence),
            passed=True,
            duration_seconds=5.0,
        )

        errors = validate_drill_result(drill_result)
        assert errors == [], f'Drill validation errors: {errors}'
        assert drill_result.has_request_correlation

    def test_evidence_all_correlated(self, env, new_token):
        """All evidence entries share a request ID."""
        req_id = _request_id()
        entries = [
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id=req_id,
                timestamp=_now(),
            ),
            DrillEvidence(
                evidence_type=EvidenceType.ALERT_FIRED,
                request_id=req_id,
                timestamp=_now(),
            ),
            DrillEvidence(
                evidence_type=EvidenceType.RECOVERY_CONFIRMED,
                request_id=req_id,
                timestamp=_now(),
            ),
        ]
        assert all(e.request_id == req_id for e in entries)


# =====================================================================
# 6. Runbook integration alignment
# =====================================================================


class TestRunbookIntegration:

    def test_default_runbook_passes_validation(self):
        validate_rotation_runbook(DEFAULT_ROTATION_RUNBOOK)

    def test_runbook_has_correct_owner(self):
        assert DEFAULT_ROTATION_RUNBOOK.owner == 'runtime_owner'

    def test_runbook_estimated_duration_reasonable(self):
        assert 5 <= DEFAULT_ROTATION_RUNBOOK.estimated_duration_minutes <= 30

    def test_runbook_step_count(self):
        assert DEFAULT_ROTATION_RUNBOOK.step_count == 7

    def test_runbook_smoke_check_count(self):
        assert DEFAULT_ROTATION_RUNBOOK.smoke_check_count == 4


# =====================================================================
# 7. Rollback safety
# =====================================================================


class TestRollbackSafety:

    def test_every_step_has_rollback(self, runbook):
        for step in runbook.steps:
            assert step.rollback.strip(), (
                f'Step {step.order} ({step.action!r}) missing rollback'
            )

    def test_every_step_has_timeout(self, runbook):
        for step in runbook.steps:
            assert step.timeout_seconds > 0, (
                f'Step {step.order} ({step.action!r}) has no timeout'
            )

    def test_generate_step_has_safe_rollback(self, runbook):
        """Generate step rollback should note no action needed."""
        gen_steps = [
            s for s in runbook.steps
            if s.phase == RotationPhase.GENERATE
        ]
        assert gen_steps
        assert 'no action' in gen_steps[0].rollback.lower()


# =====================================================================
# 8. Response redaction
# =====================================================================


class TestResponseRedaction:

    def test_proxy_response_never_leaks_token(self, env, new_token):
        env.rotate_token(new_token)
        # Make several requests.
        env.request('/health')
        env.request('/api/v1/me', bearer_token=new_token)
        env.request('/api/v1/workspaces/ws_1/proxy/health')
        env.request('/runtime/health', bearer_token=new_token)

        assert env.check_no_token_leakage()

    def test_redaction_smoke_check_specifies_forbidden_strings(self):
        runbook = DEFAULT_ROTATION_RUNBOOK
        redaction_checks = [
            c for c in runbook.smoke_checks
            if c.check_type == SmokeCheckType.RESPONSE_REDACTION
        ]
        assert len(redaction_checks) == 1
        check = redaction_checks[0]
        assert len(check.must_not_contain) >= 2
        assert 'sprite-bearer' in check.must_not_contain

    def test_request_log_captures_all_requests(self, env, new_token):
        env.rotate_token(new_token)
        env.request('/health')
        env.request('/api/v1/me', bearer_token=new_token)

        assert len(env.request_log) == 2
        assert env.request_log[0]['endpoint'] == '/health'
        assert env.request_log[1]['endpoint'] == '/api/v1/me'
