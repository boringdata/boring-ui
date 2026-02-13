"""Cross-epic outage drill catalog and evidence validation tests.

Bead: bd-223o.15.5 (J5)

Validates:
  - Drill catalog covers all required drill types
  - Each scenario has failure injection, degradation, recovery, and evidence requirements
  - All scenarios require RECOVERY_CONFIRMED evidence
  - Scenario factory functions produce valid scenarios
  - validate_drill_catalog rejects incomplete catalogs
  - validate_drill_result checks evidence requirements and request correlation
  - DrillResult properties work correctly
  - Frozen dataclass invariants hold
  - Idempotent construction
  - Cross-epic integration references (J1 alerts, J2 stale jobs, J3 rotation, J4 checksum)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from control_plane.app.operations.outage_drill import (
    DEFAULT_DRILL_CATALOG,
    REQUIRED_DRILL_TYPES,
    DrillEvidence,
    DrillResult,
    DrillScenario,
    DrillType,
    EvidenceType,
    ExpectedDegradation,
    FailureInjection,
    RecoveryAction,
    build_artifact_corruption_scenario,
    build_drill_catalog,
    build_sprite_runtime_outage_scenario,
    build_supabase_auth_outage_scenario,
    validate_drill_catalog,
    validate_drill_result,
)


@pytest.fixture
def catalog():
    return DEFAULT_DRILL_CATALOG


@pytest.fixture
def supabase_scenario():
    return build_supabase_auth_outage_scenario()


@pytest.fixture
def sprite_scenario():
    return build_sprite_runtime_outage_scenario()


@pytest.fixture
def artifact_scenario():
    return build_artifact_corruption_scenario()


def _make_evidence(
    evidence_type: EvidenceType,
    request_id: str = 'req-001',
) -> DrillEvidence:
    return DrillEvidence(
        evidence_type=evidence_type,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        endpoint='/test',
        status_code=200,
        detail='test evidence',
    )


# =====================================================================
# 1. Drill type coverage
# =====================================================================


class TestDrillTypeCoverage:
    """Catalog must cover all required drill types."""

    def test_all_required_types_covered(self, catalog):
        covered = {s.drill_type for s in catalog}
        assert REQUIRED_DRILL_TYPES.issubset(covered)

    def test_supabase_auth_outage_present(self, catalog):
        types = {s.drill_type for s in catalog}
        assert DrillType.SUPABASE_AUTH_OUTAGE in types

    def test_sprite_runtime_outage_present(self, catalog):
        types = {s.drill_type for s in catalog}
        assert DrillType.SPRITE_RUNTIME_OUTAGE in types

    def test_artifact_corruption_present(self, catalog):
        types = {s.drill_type for s in catalog}
        assert DrillType.ARTIFACT_CORRUPTION in types

    def test_catalog_has_three_scenarios(self, catalog):
        assert len(catalog) == 3


# =====================================================================
# 2. Failure injection completeness
# =====================================================================


class TestFailureInjection:
    """Each scenario specifies a complete failure injection."""

    def test_supabase_targets_supabase_auth(self, supabase_scenario):
        assert supabase_scenario.failure.target_service == 'supabase_auth'

    def test_sprite_targets_sprite_runtime(self, sprite_scenario):
        assert sprite_scenario.failure.target_service == 'sprite_runtime'

    def test_artifact_targets_artifact_store(self, artifact_scenario):
        assert artifact_scenario.failure.target_service == 'artifact_store'

    def test_all_have_injection_method(self, catalog):
        for scenario in catalog:
            assert scenario.failure.method.strip()

    def test_all_have_positive_duration(self, catalog):
        for scenario in catalog:
            assert scenario.failure.duration_seconds > 0

    def test_all_have_expected_error_codes(self, catalog):
        for scenario in catalog:
            assert len(scenario.failure.expected_error_codes) > 0


# =====================================================================
# 3. Expected degradation
# =====================================================================


class TestExpectedDegradation:
    """Each scenario describes expected system behavior during failure."""

    def test_all_have_affected_endpoints(self, catalog):
        for scenario in catalog:
            assert len(scenario.degradation.affected_endpoints) > 0

    def test_all_have_expected_status_codes(self, catalog):
        for scenario in catalog:
            assert len(scenario.degradation.expected_status_codes) > 0

    def test_all_have_expected_alerts(self, catalog):
        for scenario in catalog:
            assert len(scenario.degradation.alerts_expected) > 0

    def test_all_have_user_visible_impact(self, catalog):
        for scenario in catalog:
            assert scenario.degradation.user_visible_impact.strip()

    def test_supabase_expects_401_or_502(self, supabase_scenario):
        codes = supabase_scenario.degradation.expected_status_codes
        assert 401 in codes or 502 in codes

    def test_sprite_expects_502_or_504(self, sprite_scenario):
        codes = sprite_scenario.degradation.expected_status_codes
        assert 502 in codes or 504 in codes

    def test_artifact_expects_500(self, artifact_scenario):
        assert 500 in artifact_scenario.degradation.expected_status_codes


# =====================================================================
# 4. Recovery actions
# =====================================================================


class TestRecoveryActions:
    """Each scenario has a recovery plan with runbook reference."""

    def test_all_have_runbook_reference(self, catalog):
        for scenario in catalog:
            assert scenario.recovery.runbook_reference.strip()

    def test_all_have_recovery_steps(self, catalog):
        for scenario in catalog:
            assert len(scenario.recovery.steps) > 0

    def test_all_have_positive_max_recovery(self, catalog):
        for scenario in catalog:
            assert scenario.recovery.max_recovery_minutes > 0

    def test_supabase_references_j1(self, supabase_scenario):
        assert 'J1' in supabase_scenario.recovery.runbook_reference

    def test_sprite_references_j3(self, sprite_scenario):
        assert 'J3' in sprite_scenario.recovery.runbook_reference

    def test_artifact_references_j4(self, artifact_scenario):
        assert 'J4' in artifact_scenario.recovery.runbook_reference


# =====================================================================
# 5. Evidence requirements
# =====================================================================


class TestEvidenceRequirements:
    """All scenarios require RECOVERY_CONFIRMED and REQUEST_RESPONSE."""

    def test_all_require_recovery_confirmed(self, catalog):
        for scenario in catalog:
            assert EvidenceType.RECOVERY_CONFIRMED in scenario.evidence_requirements

    def test_all_require_request_response(self, catalog):
        for scenario in catalog:
            assert EvidenceType.REQUEST_RESPONSE in scenario.evidence_requirements

    def test_sprite_requires_job_transition(self, sprite_scenario):
        assert EvidenceType.JOB_TRANSITION in sprite_scenario.evidence_requirements

    def test_artifact_requires_job_transition(self, artifact_scenario):
        assert EvidenceType.JOB_TRANSITION in artifact_scenario.evidence_requirements

    def test_supabase_requires_alert_fired(self, supabase_scenario):
        assert EvidenceType.ALERT_FIRED in supabase_scenario.evidence_requirements


# =====================================================================
# 6. Owners
# =====================================================================


class TestOwners:
    """All scenarios have an escalation owner."""

    def test_all_have_owner(self, catalog):
        for scenario in catalog:
            assert scenario.owner.strip()

    def test_supabase_owner(self, supabase_scenario):
        assert supabase_scenario.owner == 'backend_oncall_owner'

    def test_sprite_owner(self, sprite_scenario):
        assert sprite_scenario.owner == 'runtime_owner'

    def test_artifact_owner(self, artifact_scenario):
        assert artifact_scenario.owner == 'runtime_owner'


# =====================================================================
# 7. Catalog validation
# =====================================================================


class TestCatalogValidation:
    """validate_drill_catalog catches incomplete catalogs."""

    def test_default_passes_validation(self, catalog):
        validate_drill_catalog(catalog)

    def test_built_passes_validation(self):
        validate_drill_catalog(build_drill_catalog())

    def test_missing_drill_type_raises(self):
        # Only include supabase scenario.
        scenarios = [build_supabase_auth_outage_scenario()]
        with pytest.raises(ValueError, match='Missing drill types'):
            validate_drill_catalog(scenarios)

    def test_empty_error_codes_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='Bad scenario',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=(),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=('alert',),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=('step1',),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(
                EvidenceType.REQUEST_RESPONSE,
                EvidenceType.RECOVERY_CONFIRMED,
            ),
            owner='owner',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='no expected error codes'):
            validate_drill_catalog(scenarios)

    def test_empty_alerts_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='Bad alerts',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=('ERR',),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=(),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=('step1',),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(
                EvidenceType.REQUEST_RESPONSE,
                EvidenceType.RECOVERY_CONFIRMED,
            ),
            owner='owner',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='no expected alerts'):
            validate_drill_catalog(scenarios)

    def test_empty_recovery_steps_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='No steps',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=('ERR',),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=('alert',),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=(),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(
                EvidenceType.REQUEST_RESPONSE,
                EvidenceType.RECOVERY_CONFIRMED,
            ),
            owner='owner',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='no recovery steps'):
            validate_drill_catalog(scenarios)

    def test_missing_recovery_confirmed_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='No recovery evidence',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=('ERR',),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=('alert',),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=('step1',),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(EvidenceType.REQUEST_RESPONSE,),
            owner='owner',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='must require RECOVERY_CONFIRMED'):
            validate_drill_catalog(scenarios)

    def test_empty_owner_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='No owner',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=('ERR',),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=('alert',),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=('step1',),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(
                EvidenceType.REQUEST_RESPONSE,
                EvidenceType.RECOVERY_CONFIRMED,
            ),
            owner='',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='no owner'):
            validate_drill_catalog(scenarios)

    def test_no_evidence_requirements_raises(self):
        scenario = DrillScenario(
            drill_type=DrillType.SUPABASE_AUTH_OUTAGE,
            name='No evidence',
            description='Test',
            failure=FailureInjection(
                target_service='test',
                method='test',
                duration_seconds=60,
                expected_error_codes=('ERR',),
            ),
            degradation=ExpectedDegradation(
                affected_endpoints=('/test',),
                expected_status_codes=(500,),
                alerts_expected=('alert',),
                user_visible_impact='Impact',
            ),
            recovery=RecoveryAction(
                runbook_reference='J1',
                steps=('step1',),
                max_recovery_minutes=10,
            ),
            evidence_requirements=(),
            owner='owner',
        )
        scenarios = list(DEFAULT_DRILL_CATALOG)
        scenarios[0] = scenario
        with pytest.raises(ValueError, match='no evidence requirements'):
            validate_drill_catalog(scenarios)


# =====================================================================
# 8. Drill result validation
# =====================================================================


class TestDrillResultValidation:
    """validate_drill_result checks evidence completeness and correlation."""

    def test_complete_result_has_no_errors(self, supabase_scenario):
        evidence = tuple(
            _make_evidence(et) for et in supabase_scenario.evidence_requirements
        )
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=True,
            duration_seconds=120.0,
        )
        errors = validate_drill_result(result)
        assert errors == []

    def test_missing_evidence_type_reported(self, supabase_scenario):
        # Only provide REQUEST_RESPONSE, missing ALERT_FIRED and RECOVERY_CONFIRMED.
        evidence = (_make_evidence(EvidenceType.REQUEST_RESPONSE),)
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=False,
        )
        errors = validate_drill_result(result)
        assert any('alert_fired' in e for e in errors)
        assert any('recovery_confirmed' in e for e in errors)

    def test_empty_request_id_reported(self, supabase_scenario):
        evidence = tuple(
            DrillEvidence(
                evidence_type=et,
                request_id='',
                timestamp=datetime.now(timezone.utc),
            )
            for et in supabase_scenario.evidence_requirements
        )
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=False,
        )
        errors = validate_drill_result(result)
        assert any('request ID' in e for e in errors)

    def test_no_evidence_reports_all_missing(self, supabase_scenario):
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=(),
            passed=False,
        )
        errors = validate_drill_result(result)
        assert len(errors) >= len(supabase_scenario.evidence_requirements)


# =====================================================================
# 9. DrillResult properties
# =====================================================================


class TestDrillResultProperties:
    """DrillResult computed properties work correctly."""

    def test_evidence_by_type(self, supabase_scenario):
        evidence = (
            _make_evidence(EvidenceType.REQUEST_RESPONSE, 'req-1'),
            _make_evidence(EvidenceType.REQUEST_RESPONSE, 'req-2'),
            _make_evidence(EvidenceType.ALERT_FIRED, 'req-3'),
        )
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=True,
        )
        by_type = result.evidence_by_type
        assert len(by_type[EvidenceType.REQUEST_RESPONSE]) == 2
        assert len(by_type[EvidenceType.ALERT_FIRED]) == 1

    def test_has_request_correlation_all_present(self, supabase_scenario):
        evidence = tuple(
            _make_evidence(et, f'req-{i}')
            for i, et in enumerate(supabase_scenario.evidence_requirements)
        )
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=True,
        )
        assert result.has_request_correlation is True

    def test_has_request_correlation_missing(self, supabase_scenario):
        evidence = (
            _make_evidence(EvidenceType.REQUEST_RESPONSE, 'req-1'),
            DrillEvidence(
                evidence_type=EvidenceType.ALERT_FIRED,
                request_id='',
                timestamp=datetime.now(timezone.utc),
            ),
        )
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=evidence,
            passed=False,
        )
        assert result.has_request_correlation is False

    def test_empty_evidence_has_correlation(self, supabase_scenario):
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=(),
            passed=False,
        )
        # all() on empty iterable is True.
        assert result.has_request_correlation is True


# =====================================================================
# 10. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:
    """All drill types are frozen."""

    def test_drill_scenario_frozen(self, supabase_scenario):
        with pytest.raises(AttributeError):
            supabase_scenario.name = 'mutated'

    def test_failure_injection_frozen(self, supabase_scenario):
        with pytest.raises(AttributeError):
            supabase_scenario.failure.target_service = 'mutated'

    def test_expected_degradation_frozen(self, supabase_scenario):
        with pytest.raises(AttributeError):
            supabase_scenario.degradation.user_visible_impact = 'mutated'

    def test_recovery_action_frozen(self, supabase_scenario):
        with pytest.raises(AttributeError):
            supabase_scenario.recovery.runbook_reference = 'mutated'

    def test_drill_evidence_frozen(self):
        evidence = _make_evidence(EvidenceType.REQUEST_RESPONSE)
        with pytest.raises(AttributeError):
            evidence.request_id = 'mutated'

    def test_drill_result_frozen(self, supabase_scenario):
        result = DrillResult(
            scenario=supabase_scenario,
            evidence=(),
            passed=False,
        )
        with pytest.raises(AttributeError):
            result.passed = True


# =====================================================================
# 11. Idempotency
# =====================================================================


class TestIdempotency:
    """Factory functions produce equivalent results."""

    def test_two_catalogs_same_length(self):
        c1 = build_drill_catalog()
        c2 = build_drill_catalog()
        assert len(c1) == len(c2)

    def test_two_catalogs_same_types(self):
        c1 = build_drill_catalog()
        c2 = build_drill_catalog()
        types1 = {s.drill_type for s in c1}
        types2 = {s.drill_type for s in c2}
        assert types1 == types2

    def test_default_matches_build(self):
        fresh = build_drill_catalog()
        assert len(DEFAULT_DRILL_CATALOG) == len(fresh)
        for s1, s2 in zip(DEFAULT_DRILL_CATALOG, fresh):
            assert s1.drill_type == s2.drill_type
            assert s1.name == s2.name
            assert s1.owner == s2.owner

    def test_individual_factories_stable(self):
        s1 = build_supabase_auth_outage_scenario()
        s2 = build_supabase_auth_outage_scenario()
        assert s1.name == s2.name
        assert s1.failure.target_service == s2.failure.target_service


# =====================================================================
# 12. Enum values
# =====================================================================


class TestEnumValues:

    def test_drill_types(self):
        assert DrillType.SUPABASE_AUTH_OUTAGE.value == 'supabase_auth_outage'
        assert DrillType.SPRITE_RUNTIME_OUTAGE.value == 'sprite_runtime_outage'
        assert DrillType.ARTIFACT_CORRUPTION.value == 'artifact_corruption'
        assert DrillType.COMBINED_DEGRADATION.value == 'combined_degradation'

    def test_evidence_types(self):
        assert EvidenceType.REQUEST_RESPONSE.value == 'request_response'
        assert EvidenceType.ALERT_FIRED.value == 'alert_fired'
        assert EvidenceType.JOB_TRANSITION.value == 'job_transition'
        assert EvidenceType.RECOVERY_CONFIRMED.value == 'recovery_confirmed'
        assert EvidenceType.LOG_ENTRY.value == 'log_entry'


# =====================================================================
# 13. Cross-epic integration references
# =====================================================================


class TestCrossEpicIntegration:
    """Drill scenarios reference the correct cross-epic components."""

    def test_supabase_references_slo_alert(self, supabase_scenario):
        assert 'api_5xx_error_rate_burn' in supabase_scenario.degradation.alerts_expected

    def test_sprite_references_provisioning_alert(self, sprite_scenario):
        assert 'provisioning_error_rate_burn' in sprite_scenario.degradation.alerts_expected

    def test_artifact_references_provisioning_alert(self, artifact_scenario):
        assert 'provisioning_error_rate_burn' in artifact_scenario.degradation.alerts_expected

    def test_sprite_expects_step_timeout_code(self, sprite_scenario):
        assert 'STEP_TIMEOUT' in sprite_scenario.failure.expected_error_codes

    def test_artifact_expects_checksum_mismatch_code(self, artifact_scenario):
        assert 'CHECKSUM_MISMATCH' in artifact_scenario.failure.expected_error_codes
