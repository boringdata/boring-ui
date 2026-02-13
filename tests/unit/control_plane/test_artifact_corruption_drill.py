"""Artifact-corruption recovery drill: simulate and validate end-to-end.

Bead: bd-223o.15.4.1 (J4a)

Executes the artifact corruption drill scenario defined in J5's outage_drill
module, validating:
  1. Corruption detection: provisioning fails with CHECKSUM_MISMATCH when
     artifact integrity check fails.
  2. Error state capture: job reaches error state with actionable error
     code and detail referencing the checksum mismatch.
  3. Retry remediation: after fixing the artifact, retry succeeds and
     the workspace reaches ready state.
  4. Evidence capture: request-correlated evidence proves detection,
     transition, and recovery.
  5. Drill validation: DrillResult passes validate_drill_result with
     all required evidence types present.
  6. Runbook integration: checksum failure runbook triage steps
     align with the drill's recovery actions.

Uses the in-memory providers from D4 (ProvisioningJobExecutor) to drive
the state machine through a realistic corruption→error→fix→retry→ready
flow without external dependencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from control_plane.app.operations.checksum_failure_runbook import (
    DEFAULT_CHECKSUM_FAILURE_RUNBOOK,
    ChecksumFailureCode,
    CommsTemplateType,
    validate_checksum_failure_runbook,
)
from control_plane.app.operations.outage_drill import (
    DrillEvidence,
    DrillResult,
    DrillType,
    EvidenceType,
    build_artifact_corruption_scenario,
    validate_drill_result,
)
from control_plane.app.provisioning.job_executor import (
    ExecutionResult,
    InMemoryArtifactVerifier,
    InMemoryRuntimeMetadataStore,
    InMemorySandboxProvider,
    ProvisioningJobExecutor,
)
from control_plane.app.provisioning.release_contract import (
    ProvisioningTarget,
)
from control_plane.app.provisioning.state_machine import (
    ARTIFACT_CHECKSUM_MISMATCH_CODE,
    ProvisioningJobState,
    create_queued_job,
    retry_from_error,
    transition_to_checksum_mismatch,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _request_id() -> str:
    return f'drill-{uuid.uuid4().hex[:12]}'


def _make_target(
    *,
    workspace_id: str = 'ws_drill_001',
    app_id: str = 'boring-ui',
    release_id: str = 'rel_drill_1',
    bundle_sha256: str = 'a' * 64,
) -> ProvisioningTarget:
    return ProvisioningTarget(
        workspace_id=workspace_id,
        app_id=app_id,
        release_id=release_id,
        bundle_sha256=bundle_sha256,
        sandbox_name=f'sbx-{app_id}-{workspace_id}-staging',
    )


# =====================================================================
# 1. Corruption detection: executor detects checksum mismatch
# =====================================================================


class TestCorruptionDetection:
    """Provisioning fails with CHECKSUM_MISMATCH on corrupted artifact."""

    @pytest.mark.asyncio
    async def test_executor_detects_checksum_mismatch(self):
        """Executor returns error with ARTIFACT_CHECKSUM_MISMATCH code."""
        target = _make_target()
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=InMemoryRuntimeMetadataStore(),
        )

        result = await executor.execute(target=target)

        assert not result.success
        assert result.error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE
        assert result.job.state == 'error'

    @pytest.mark.asyncio
    async def test_error_detail_is_actionable(self):
        """Error detail mentions mismatch for operator triage."""
        target = _make_target()
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=InMemoryRuntimeMetadataStore(),
        )

        result = await executor.execute(target=target)

        assert result.error_detail is not None
        assert 'mismatch' in result.error_detail.lower()

    @pytest.mark.asyncio
    async def test_runtime_metadata_records_error(self):
        """Runtime metadata store captures the error state."""
        runtime_store = InMemoryRuntimeMetadataStore()
        target = _make_target()
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=runtime_store,
        )

        await executor.execute(target=target)

        rt = runtime_store.runtimes.get(target.workspace_id)
        assert rt is not None
        assert rt['state'] == 'error'
        assert rt['last_error_code'] == ARTIFACT_CHECKSUM_MISMATCH_CODE

    @pytest.mark.asyncio
    async def test_sandbox_not_created_on_checksum_fail(self):
        """Sandbox provider is never called if checksum fails early."""
        sandbox = InMemorySandboxProvider()
        target = _make_target()
        executor = ProvisioningJobExecutor(
            sandbox_provider=sandbox,
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=InMemoryRuntimeMetadataStore(),
        )

        await executor.execute(target=target)

        assert len(sandbox.calls) == 0


# =====================================================================
# 2. State machine error transition
# =====================================================================


class TestStateMachineChecksumTransition:
    """State machine transitions correctly on checksum mismatch."""

    def test_active_state_transitions_to_error(self):
        job = create_queued_job(workspace_id='ws_drill', now=_now())
        from control_plane.app.provisioning.state_machine import advance_state
        job = advance_state(job, now=_now())  # release_resolve

        error_job = transition_to_checksum_mismatch(
            job,
            now=_now(),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )

        assert error_job.state == 'error'
        assert error_job.last_error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

    def test_error_detail_contains_hash_prefixes(self):
        job = create_queued_job(workspace_id='ws_drill', now=_now())
        from control_plane.app.provisioning.state_machine import advance_state
        job = advance_state(job, now=_now())

        error_job = transition_to_checksum_mismatch(
            job,
            now=_now(),
            expected_sha256='abc123' + '0' * 58,
            actual_sha256='def456' + '0' * 58,
        )

        assert 'abc123' in error_job.last_error_detail
        assert 'def456' in error_job.last_error_detail


# =====================================================================
# 3. Retry recovery: fix artifact → retry → ready
# =====================================================================


class TestRetryRecovery:
    """After fixing the artifact, retry reaches ready state."""

    @pytest.mark.asyncio
    async def test_retry_after_fix_reaches_ready(self):
        """Fix artifact (valid=True) and re-execute → success."""
        target = _make_target()
        runtime_store = InMemoryRuntimeMetadataStore()

        # Phase 1: corrupt artifact → error
        executor_corrupt = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=runtime_store,
        )
        error_result = await executor_corrupt.execute(target=target)
        assert not error_result.success
        assert error_result.error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

        # Phase 2: fix artifact (valid=True) and re-execute
        executor_fixed = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(
                valid=True,
                bundle_file=Path('/tmp/bundle.tar.gz'),
            ),
            runtime_store=runtime_store,
        )
        success_result = await executor_fixed.execute(target=target)
        assert success_result.success
        assert success_result.job.state == 'ready'

    @pytest.mark.asyncio
    async def test_runtime_metadata_updated_on_recovery(self):
        """Runtime store reflects ready state after successful retry."""
        target = _make_target()
        runtime_store = InMemoryRuntimeMetadataStore()

        # Phase 1: corrupt → error
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=runtime_store,
        )
        await executor.execute(target=target)
        assert runtime_store.runtimes[target.workspace_id]['state'] == 'error'

        # Phase 2: fix → ready
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(
                valid=True,
                bundle_file=Path('/tmp/bundle.tar.gz'),
            ),
            runtime_store=runtime_store,
        )
        await executor.execute(target=target)
        assert runtime_store.runtimes[target.workspace_id]['state'] == 'ready'

    def test_state_machine_retry_clears_error(self):
        """retry_from_error resets state to queued with cleared errors."""
        job = create_queued_job(workspace_id='ws_drill', now=_now())
        from control_plane.app.provisioning.state_machine import advance_state
        job = advance_state(job, now=_now())

        error_job = transition_to_checksum_mismatch(
            job,
            now=_now(),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )
        retried = retry_from_error(error_job, now=_now())

        assert retried.state == 'queued'
        assert retried.attempt == 2
        assert retried.last_error_code is None
        assert retried.last_error_detail is None


# =====================================================================
# 4. Evidence capture with request correlation
# =====================================================================


class TestEvidenceCapture:
    """Build drill evidence from the corruption→recovery flow."""

    @pytest.mark.asyncio
    async def test_collect_detection_evidence(self):
        """Evidence captured when checksum mismatch is first detected."""
        req_id = _request_id()
        target = _make_target()

        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=InMemoryRuntimeMetadataStore(),
        )
        result = await executor.execute(target=target)

        evidence = DrillEvidence(
            evidence_type=EvidenceType.REQUEST_RESPONSE,
            request_id=req_id,
            timestamp=_now(),
            endpoint=f'/api/v1/workspaces/{target.workspace_id}/runtime',
            status_code=200,
            detail=f'state=error, error_code={result.error_code}',
        )

        assert evidence.request_id.startswith('drill-')
        assert evidence.evidence_type == EvidenceType.REQUEST_RESPONSE
        assert 'ARTIFACT_CHECKSUM_MISMATCH' in evidence.detail

    @pytest.mark.asyncio
    async def test_collect_transition_evidence(self):
        """Evidence for the error → queued → ready state transitions."""
        req_id = _request_id()

        evidence = DrillEvidence(
            evidence_type=EvidenceType.JOB_TRANSITION,
            request_id=req_id,
            timestamp=_now(),
            detail='error → queued (retry_from_error)',
        )

        assert evidence.evidence_type == EvidenceType.JOB_TRANSITION
        assert evidence.request_id

    @pytest.mark.asyncio
    async def test_collect_recovery_evidence(self):
        """Evidence confirming successful recovery to ready state."""
        req_id = _request_id()

        evidence = DrillEvidence(
            evidence_type=EvidenceType.RECOVERY_CONFIRMED,
            request_id=req_id,
            timestamp=_now(),
            endpoint='/api/v1/workspaces/ws_drill_001/runtime',
            status_code=200,
            detail='state=ready after retry',
        )

        assert evidence.evidence_type == EvidenceType.RECOVERY_CONFIRMED

    @pytest.mark.asyncio
    async def test_all_evidence_has_request_correlation(self):
        """Every evidence entry must have a non-empty request_id."""
        req_id = _request_id()
        entries = [
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id=req_id,
                timestamp=_now(),
                detail='detection',
            ),
            DrillEvidence(
                evidence_type=EvidenceType.JOB_TRANSITION,
                request_id=req_id,
                timestamp=_now(),
                detail='error → queued',
            ),
            DrillEvidence(
                evidence_type=EvidenceType.RECOVERY_CONFIRMED,
                request_id=req_id,
                timestamp=_now(),
                detail='state=ready',
            ),
        ]

        assert all(e.request_id for e in entries)


# =====================================================================
# 5. Full drill execution and validation
# =====================================================================


class TestFullDrillExecution:
    """End-to-end drill: corrupt → detect → fix → retry → recover → validate."""

    @pytest.mark.asyncio
    async def test_full_drill_passes_validation(self):
        """Complete drill with all evidence passes validate_drill_result."""
        scenario = build_artifact_corruption_scenario()
        target = _make_target()
        runtime_store = InMemoryRuntimeMetadataStore()
        req_id = _request_id()
        evidence: list[DrillEvidence] = []

        # Step 1: Inject corruption → execute → detect error
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=runtime_store,
        )
        error_result = await executor.execute(target=target)
        assert not error_result.success

        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.REQUEST_RESPONSE,
            request_id=req_id,
            timestamp=_now(),
            endpoint=f'/api/v1/workspaces/{target.workspace_id}/runtime',
            status_code=200,
            detail=f'state=error, error_code={error_result.error_code}',
        ))

        # Step 2: Record transition evidence
        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.JOB_TRANSITION,
            request_id=req_id,
            timestamp=_now(),
            detail=f'Job transitioned: release_resolve → error '
                   f'(code={ARTIFACT_CHECKSUM_MISMATCH_CODE})',
        ))

        # Step 3: Fix artifact and re-execute (retry)
        executor_fixed = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(
                valid=True, bundle_file=Path('/tmp/bundle.tar.gz'),
            ),
            runtime_store=runtime_store,
        )
        success_result = await executor_fixed.execute(target=target)
        assert success_result.success

        evidence.append(DrillEvidence(
            evidence_type=EvidenceType.RECOVERY_CONFIRMED,
            request_id=req_id,
            timestamp=_now(),
            endpoint=f'/api/v1/workspaces/{target.workspace_id}/runtime',
            status_code=200,
            detail='state=ready after artifact rebuild and retry',
        ))

        # Build and validate drill result
        drill_result = DrillResult(
            scenario=scenario,
            evidence=tuple(evidence),
            passed=True,
            duration_seconds=2.5,
        )

        errors = validate_drill_result(drill_result)
        assert errors == [], f'Drill validation errors: {errors}'

    @pytest.mark.asyncio
    async def test_drill_fails_without_recovery_evidence(self):
        """Drill result without RECOVERY_CONFIRMED fails validation."""
        scenario = build_artifact_corruption_scenario()
        req_id = _request_id()

        partial_evidence = (
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id=req_id,
                timestamp=_now(),
                detail='detection only',
            ),
            DrillEvidence(
                evidence_type=EvidenceType.JOB_TRANSITION,
                request_id=req_id,
                timestamp=_now(),
                detail='error transition',
            ),
        )

        drill_result = DrillResult(
            scenario=scenario,
            evidence=partial_evidence,
            passed=False,
            failure_reason='Recovery not attempted',
        )

        errors = validate_drill_result(drill_result)
        assert any('recovery_confirmed' in e for e in errors)

    @pytest.mark.asyncio
    async def test_drill_fails_without_request_correlation(self):
        """Evidence without request IDs fails correlation check."""
        scenario = build_artifact_corruption_scenario()

        uncorrelated_evidence = (
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id='',  # Missing!
                timestamp=_now(),
                detail='no correlation',
            ),
            DrillEvidence(
                evidence_type=EvidenceType.JOB_TRANSITION,
                request_id=_request_id(),
                timestamp=_now(),
                detail='transition',
            ),
            DrillEvidence(
                evidence_type=EvidenceType.RECOVERY_CONFIRMED,
                request_id=_request_id(),
                timestamp=_now(),
                detail='recovery',
            ),
        )

        drill_result = DrillResult(
            scenario=scenario,
            evidence=uncorrelated_evidence,
            passed=False,
        )

        errors = validate_drill_result(drill_result)
        assert any('request ID' in e for e in errors)


# =====================================================================
# 6. Drill scenario matches runbook integration
# =====================================================================


class TestDrillRunbookIntegration:
    """Verify drill scenario aligns with the J4 checksum failure runbook."""

    def test_scenario_drill_type(self):
        scenario = build_artifact_corruption_scenario()
        assert scenario.drill_type == DrillType.ARTIFACT_CORRUPTION

    def test_scenario_references_j4_runbook(self):
        scenario = build_artifact_corruption_scenario()
        assert 'J4' in scenario.recovery.runbook_reference

    def test_scenario_expects_checksum_mismatch_error(self):
        scenario = build_artifact_corruption_scenario()
        assert 'CHECKSUM_MISMATCH' in scenario.failure.expected_error_codes

    def test_scenario_requires_recovery_confirmed(self):
        scenario = build_artifact_corruption_scenario()
        assert (
            EvidenceType.RECOVERY_CONFIRMED
            in scenario.evidence_requirements
        )

    def test_runbook_triggers_match_scenario_errors(self):
        """Runbook trigger codes include the scenario's expected errors."""
        runbook = DEFAULT_CHECKSUM_FAILURE_RUNBOOK
        scenario = build_artifact_corruption_scenario()

        for code in scenario.failure.expected_error_codes:
            assert code in runbook.trigger_codes, (
                f'Expected error code {code!r} not in runbook triggers'
            )

    def test_runbook_passes_validation(self):
        """The default checksum failure runbook passes validation."""
        validate_checksum_failure_runbook(DEFAULT_CHECKSUM_FAILURE_RUNBOOK)

    def test_runbook_has_retry_step(self):
        """Runbook includes a retry step (step 4 in triage)."""
        runbook = DEFAULT_CHECKSUM_FAILURE_RUNBOOK
        retry_steps = [
            s for s in runbook.triage_steps
            if 'retry' in s.action.lower()
        ]
        assert len(retry_steps) >= 1

    def test_runbook_has_rebuild_step(self):
        """Runbook includes a rebuild step (step 5 in triage)."""
        runbook = DEFAULT_CHECKSUM_FAILURE_RUNBOOK
        rebuild_steps = [
            s for s in runbook.triage_steps
            if 'rebuild' in s.action.lower()
        ]
        assert len(rebuild_steps) >= 1

    def test_runbook_comms_cover_all_types(self):
        """Runbook has triage note, status update, and resolution summary."""
        runbook = DEFAULT_CHECKSUM_FAILURE_RUNBOOK
        comms_types = {t.template_type for t in runbook.comms_templates}
        assert CommsTemplateType.TRIAGE_NOTE in comms_types
        assert CommsTemplateType.STATUS_UPDATE in comms_types
        assert CommsTemplateType.RESOLUTION_SUMMARY in comms_types

    def test_scenario_recovery_steps_cover_drill_flow(self):
        """Scenario recovery steps mention key drill actions."""
        scenario = build_artifact_corruption_scenario()
        steps_text = ' '.join(scenario.recovery.steps).lower()
        assert 'verify' in steps_text or 'identify' in steps_text
        assert 'retry' in steps_text
        assert 'rebuild' in steps_text


# =====================================================================
# 7. DrillResult properties
# =====================================================================


class TestDrillResultProperties:

    def test_evidence_by_type_groups_correctly(self):
        scenario = build_artifact_corruption_scenario()
        req_id = _request_id()
        evidence = (
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id=req_id,
                timestamp=_now(),
            ),
            DrillEvidence(
                evidence_type=EvidenceType.JOB_TRANSITION,
                request_id=req_id,
                timestamp=_now(),
            ),
            DrillEvidence(
                evidence_type=EvidenceType.RECOVERY_CONFIRMED,
                request_id=req_id,
                timestamp=_now(),
            ),
        )

        result = DrillResult(
            scenario=scenario,
            evidence=evidence,
            passed=True,
        )

        by_type = result.evidence_by_type
        assert len(by_type[EvidenceType.REQUEST_RESPONSE]) == 1
        assert len(by_type[EvidenceType.JOB_TRANSITION]) == 1
        assert len(by_type[EvidenceType.RECOVERY_CONFIRMED]) == 1

    def test_has_request_correlation_true(self):
        scenario = build_artifact_corruption_scenario()
        evidence = (
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id=_request_id(),
                timestamp=_now(),
            ),
        )
        result = DrillResult(
            scenario=scenario, evidence=evidence, passed=True,
        )
        assert result.has_request_correlation is True

    def test_has_request_correlation_false(self):
        scenario = build_artifact_corruption_scenario()
        evidence = (
            DrillEvidence(
                evidence_type=EvidenceType.REQUEST_RESPONSE,
                request_id='',
                timestamp=_now(),
            ),
        )
        result = DrillResult(
            scenario=scenario, evidence=evidence, passed=False,
        )
        assert result.has_request_correlation is False
