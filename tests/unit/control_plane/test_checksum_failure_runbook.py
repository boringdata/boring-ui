"""Checksum-failure operator runbook tests.

Bead: bd-223o.15.4 (J4)

Validates:
  - Runbook covers required trigger codes (CHECKSUM_MISMATCH, ARTIFACT_CORRUPT)
  - Triage steps are ordered with failure guidance
  - Communication templates cover triage note, status update, resolution summary
  - Templates have required placeholders
  - Validation rejects incomplete runbooks
  - Runbook owner matches escalation model
  - Default runbook passes validation
  - Frozen dataclass invariants hold
  - Idempotent construction
"""

from __future__ import annotations

import pytest

from control_plane.app.operations.checksum_failure_runbook import (
    ChecksumFailureCode,
    ChecksumFailureRunbook,
    CommsTemplate,
    CommsTemplateType,
    DEFAULT_CHECKSUM_FAILURE_RUNBOOK,
    REQUIRED_COMMS_TYPES,
    REQUIRED_TRIGGER_CODES,
    TriageOutcome,
    TriageStep,
    build_checksum_failure_runbook,
    validate_checksum_failure_runbook,
)


@pytest.fixture
def runbook():
    return DEFAULT_CHECKSUM_FAILURE_RUNBOOK


# =====================================================================
# 1. Trigger code coverage
# =====================================================================


class TestTriggerCodes:
    """Runbook must cover all required checksum error codes."""

    def test_checksum_mismatch_covered(self, runbook):
        assert ChecksumFailureCode.CHECKSUM_MISMATCH.value in runbook.trigger_codes

    def test_artifact_corrupt_covered(self, runbook):
        assert ChecksumFailureCode.ARTIFACT_CORRUPT.value in runbook.trigger_codes

    def test_all_required_codes_covered(self, runbook):
        assert REQUIRED_TRIGGER_CODES.issubset(runbook.trigger_codes)


# =====================================================================
# 2. Triage step ordering and completeness
# =====================================================================


class TestTriageSteps:
    """Triage steps are ordered with complete guidance."""

    def test_steps_in_ascending_order(self, runbook):
        orders = [step.order for step in runbook.triage_steps]
        assert orders == sorted(orders)

    def test_no_duplicate_order_numbers(self, runbook):
        orders = [step.order for step in runbook.triage_steps]
        assert len(orders) == len(set(orders))

    def test_all_steps_have_failure_guidance(self, runbook):
        for step in runbook.triage_steps:
            assert step.if_fail.strip(), (
                f'Step {step.order} has no failure guidance'
            )

    def test_all_steps_have_command(self, runbook):
        for step in runbook.triage_steps:
            assert step.command.strip()

    def test_all_steps_have_expected_outcome(self, runbook):
        for step in runbook.triage_steps:
            assert step.expected_outcome.strip()

    def test_first_step_identifies_affected(self, runbook):
        first = runbook.triage_steps[0]
        assert 'identify' in first.action.lower() or 'affected' in first.action.lower()

    def test_includes_retry_step(self, runbook):
        actions = [step.action.lower() for step in runbook.triage_steps]
        assert any('retry' in a for a in actions)

    def test_includes_rollback_step(self, runbook):
        actions = [step.action.lower() for step in runbook.triage_steps]
        assert any('rollback' in a for a in actions)

    def test_minimum_step_count(self, runbook):
        assert runbook.step_count >= 5


# =====================================================================
# 3. Communication template coverage
# =====================================================================


class TestCommsTemplates:
    """Templates cover triage, status, and resolution communications."""

    def test_all_required_types_covered(self, runbook):
        covered = {t.template_type for t in runbook.comms_templates}
        assert REQUIRED_COMMS_TYPES.issubset(covered)

    def test_triage_note_present(self, runbook):
        assert CommsTemplateType.TRIAGE_NOTE in runbook.comms_by_type

    def test_status_update_present(self, runbook):
        assert CommsTemplateType.STATUS_UPDATE in runbook.comms_by_type

    def test_resolution_summary_present(self, runbook):
        assert CommsTemplateType.RESOLUTION_SUMMARY in runbook.comms_by_type

    def test_all_templates_have_placeholders(self, runbook):
        for tmpl in runbook.comms_templates:
            assert len(tmpl.placeholders) > 0, (
                f'{tmpl.template_type.value} has no placeholders'
            )

    def test_all_templates_have_audience(self, runbook):
        for tmpl in runbook.comms_templates:
            assert tmpl.audience.strip()

    def test_all_templates_have_subject(self, runbook):
        for tmpl in runbook.comms_templates:
            assert tmpl.subject_template.strip()

    def test_all_templates_have_body(self, runbook):
        for tmpl in runbook.comms_templates:
            assert tmpl.body_template.strip()

    def test_triage_note_includes_error_code_placeholder(self, runbook):
        triage = runbook.comms_by_type[CommsTemplateType.TRIAGE_NOTE]
        assert 'error_code' in triage.placeholders

    def test_status_update_includes_affected_count(self, runbook):
        status = runbook.comms_by_type[CommsTemplateType.STATUS_UPDATE]
        assert 'affected_count' in status.placeholders

    def test_resolution_includes_root_cause(self, runbook):
        resolution = runbook.comms_by_type[CommsTemplateType.RESOLUTION_SUMMARY]
        assert 'root_cause' in resolution.placeholders


# =====================================================================
# 4. Validation
# =====================================================================


class TestValidation:
    """validate_checksum_failure_runbook catches incomplete runbooks."""

    def test_default_passes_validation(self, runbook):
        validate_checksum_failure_runbook(runbook)

    def test_built_passes_validation(self):
        validate_checksum_failure_runbook(build_checksum_failure_runbook())

    def test_missing_trigger_code_raises(self):
        runbook = ChecksumFailureRunbook(
            trigger_codes=frozenset({'CHECKSUM_MISMATCH'}),
            triage_steps=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps,
            comms_templates=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates,
            owner='runtime_owner',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='Missing trigger codes'):
            validate_checksum_failure_runbook(runbook)

    def test_missing_comms_type_raises(self):
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps,
            comms_templates=(
                CommsTemplate(
                    template_type=CommsTemplateType.TRIAGE_NOTE,
                    audience='ops',
                    subject_template='Test',
                    body_template='Body',
                    placeholders=('a',),
                ),
            ),
            owner='runtime_owner',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='Missing comms templates'):
            validate_checksum_failure_runbook(runbook)

    def test_unordered_steps_raises(self):
        steps = list(DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps)
        steps.reverse()
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=tuple(steps),
            comms_templates=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates,
            owner='runtime_owner',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='not in ascending order'):
            validate_checksum_failure_runbook(runbook)

    def test_empty_if_fail_raises(self):
        steps = list(DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps)
        steps[0] = TriageStep(
            order=1, action='Test', command='cmd',
            expected_outcome='ok', if_fail='',
        )
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=tuple(steps),
            comms_templates=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates,
            owner='runtime_owner',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='no failure guidance'):
            validate_checksum_failure_runbook(runbook)

    def test_empty_owner_raises(self):
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps,
            comms_templates=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates,
            owner='',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='no owner'):
            validate_checksum_failure_runbook(runbook)

    def test_too_short_triage_time_raises(self):
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps,
            comms_templates=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates,
            owner='runtime_owner',
            max_triage_minutes=2,
        )
        with pytest.raises(ValueError, match='triage minutes'):
            validate_checksum_failure_runbook(runbook)

    def test_empty_placeholder_raises(self):
        runbook = ChecksumFailureRunbook(
            trigger_codes=REQUIRED_TRIGGER_CODES,
            triage_steps=DEFAULT_CHECKSUM_FAILURE_RUNBOOK.triage_steps,
            comms_templates=(
                CommsTemplate(
                    template_type=CommsTemplateType.TRIAGE_NOTE,
                    audience='ops',
                    subject_template='s',
                    body_template='b',
                    placeholders=(),
                ),
                *[t for t in DEFAULT_CHECKSUM_FAILURE_RUNBOOK.comms_templates
                  if t.template_type != CommsTemplateType.TRIAGE_NOTE],
            ),
            owner='runtime_owner',
            max_triage_minutes=15,
        )
        with pytest.raises(ValueError, match='no placeholders'):
            validate_checksum_failure_runbook(runbook)


# =====================================================================
# 5. Runbook properties
# =====================================================================


class TestRunbookProperties:
    """Aggregate properties are correct."""

    def test_step_count(self, runbook):
        assert runbook.step_count == len(runbook.triage_steps)

    def test_template_count(self, runbook):
        assert runbook.template_count == len(runbook.comms_templates)

    def test_comms_by_type_has_all_types(self, runbook):
        by_type = runbook.comms_by_type
        assert len(by_type) == 3

    def test_owner_is_runtime_owner(self, runbook):
        assert runbook.owner == 'runtime_owner'

    def test_max_triage_minutes_reasonable(self, runbook):
        assert 5 <= runbook.max_triage_minutes <= 60


# =====================================================================
# 6. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:

    def test_runbook_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.owner = 'changed'

    def test_triage_step_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.triage_steps[0].action = 'changed'

    def test_comms_template_frozen(self, runbook):
        with pytest.raises(AttributeError):
            runbook.comms_templates[0].audience = 'changed'


# =====================================================================
# 7. Idempotency
# =====================================================================


class TestIdempotency:

    def test_two_builds_have_same_steps(self):
        r1 = build_checksum_failure_runbook()
        r2 = build_checksum_failure_runbook()
        assert r1.step_count == r2.step_count
        for s1, s2 in zip(r1.triage_steps, r2.triage_steps):
            assert s1.order == s2.order
            assert s1.action == s2.action

    def test_default_matches_build(self):
        fresh = build_checksum_failure_runbook()
        assert DEFAULT_CHECKSUM_FAILURE_RUNBOOK.step_count == fresh.step_count
        assert DEFAULT_CHECKSUM_FAILURE_RUNBOOK.owner == fresh.owner


# =====================================================================
# 8. Enum values
# =====================================================================


class TestEnumValues:

    def test_failure_codes(self):
        assert ChecksumFailureCode.CHECKSUM_MISMATCH.value == 'CHECKSUM_MISMATCH'
        assert ChecksumFailureCode.ARTIFACT_CORRUPT.value == 'ARTIFACT_CORRUPT'

    def test_triage_outcomes(self):
        assert TriageOutcome.REBUILD_ARTIFACT.value == 'rebuild_artifact'
        assert TriageOutcome.ROLLBACK_RELEASE.value == 'rollback_release'
        assert TriageOutcome.RETRY_UPLOAD.value == 'retry_upload'
        assert TriageOutcome.ESCALATE.value == 'escalate'

    def test_comms_types(self):
        assert CommsTemplateType.TRIAGE_NOTE.value == 'triage_note'
        assert CommsTemplateType.STATUS_UPDATE.value == 'status_update'
        assert CommsTemplateType.RESOLUTION_SUMMARY.value == 'resolution_summary'
