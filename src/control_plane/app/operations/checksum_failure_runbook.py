"""Checksum-failure operator runbook and communication template.

Bead: bd-223o.15.4 (J4)

Codifies the operator response for artifact checksum mismatches during
provisioning. When ``bundle_sha256`` verification fails, the workspace
cannot be safely started — the operator must triage, rollback or
rebuild, and communicate status to stakeholders.

Error codes that trigger this runbook:
  - ``CHECKSUM_MISMATCH``: bundle SHA256 does not match expected value
  - ``ARTIFACT_CORRUPT``: bundle cannot be unpacked or validated

The runbook integrates with:
  - Stale job detector (J2) for timeout-related failures during upload
  - SLO alert catalog (J1) for ``provisioning_error_rate_burn`` grouped
    by ``last_error_code``
  - Release contract (D1) for ``bundle_sha256`` resolution

Communication templates follow a structured format for:
  - Immediate operator triage notes
  - Stakeholder status updates (affected workspace count, ETA)
  - Post-incident summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class ChecksumFailureCode(Enum):
    """Error codes that trigger the checksum-failure runbook."""

    CHECKSUM_MISMATCH = 'CHECKSUM_MISMATCH'
    ARTIFACT_CORRUPT = 'ARTIFACT_CORRUPT'


class TriageOutcome(Enum):
    """Possible triage outcomes after checksum failure investigation."""

    REBUILD_ARTIFACT = 'rebuild_artifact'
    ROLLBACK_RELEASE = 'rollback_release'
    RETRY_UPLOAD = 'retry_upload'
    ESCALATE = 'escalate'


class CommsTemplateType(Enum):
    """Communication template types for stakeholder updates."""

    TRIAGE_NOTE = 'triage_note'
    STATUS_UPDATE = 'status_update'
    RESOLUTION_SUMMARY = 'resolution_summary'


@dataclass(frozen=True, slots=True)
class TriageStep:
    """Single step in the checksum-failure triage procedure.

    Attributes:
        order: Execution order (1-indexed).
        action: Human-readable action description.
        command: Shell command or API call template.
        expected_outcome: What the operator should observe.
        if_fail: Next action if this step does not succeed.
    """

    order: int
    action: str
    command: str
    expected_outcome: str
    if_fail: str


@dataclass(frozen=True, slots=True)
class CommsTemplate:
    """Communication template for stakeholder updates.

    Attributes:
        template_type: Category of the communication.
        audience: Who receives this communication.
        subject_template: Subject line with placeholders.
        body_template: Markdown body with placeholders.
        placeholders: Required placeholder names.
    """

    template_type: CommsTemplateType
    audience: str
    subject_template: str
    body_template: str
    placeholders: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChecksumFailureRunbook:
    """Complete operator runbook for checksum-failure incidents.

    Attributes:
        trigger_codes: Error codes that activate this runbook.
        triage_steps: Ordered investigation and repair steps.
        comms_templates: Communication templates by type.
        owner: Escalation owner from the SLO catalog.
        max_triage_minutes: Time before automatic escalation.
    """

    trigger_codes: frozenset[str]
    triage_steps: tuple[TriageStep, ...]
    comms_templates: tuple[CommsTemplate, ...]
    owner: str
    max_triage_minutes: int

    @property
    def step_count(self) -> int:
        return len(self.triage_steps)

    @property
    def template_count(self) -> int:
        return len(self.comms_templates)

    @property
    def comms_by_type(self) -> dict[CommsTemplateType, CommsTemplate]:
        return {t.template_type: t for t in self.comms_templates}


# ── Required contracts ──────────────────────────────────────────────

REQUIRED_TRIGGER_CODES = frozenset({
    ChecksumFailureCode.CHECKSUM_MISMATCH.value,
    ChecksumFailureCode.ARTIFACT_CORRUPT.value,
})

REQUIRED_COMMS_TYPES = frozenset({
    CommsTemplateType.TRIAGE_NOTE,
    CommsTemplateType.STATUS_UPDATE,
    CommsTemplateType.RESOLUTION_SUMMARY,
})


# ── Factory ─────────────────────────────────────────────────────────


def build_checksum_failure_runbook() -> ChecksumFailureRunbook:
    """Build the canonical checksum-failure operator runbook."""

    triage_steps = (
        TriageStep(
            order=1,
            action='Identify the affected workspace and release',
            command='curl -s https://<control-plane>/api/v1/admin/jobs?error_code=CHECKSUM_MISMATCH | jq .',
            expected_outcome='JSON list of failed provisioning jobs with workspace_id and release_id.',
            if_fail='Check control plane logs for recent provisioning errors.',
        ),
        TriageStep(
            order=2,
            action='Verify the expected checksum from the release catalog',
            command='curl -s https://<control-plane>/api/v1/releases/{release_id} | jq .bundle_sha256',
            expected_outcome='SHA256 hex string matching the published artifact.',
            if_fail='If release not found, escalate to release engineering.',
        ),
        TriageStep(
            order=3,
            action='Re-download and verify the artifact independently',
            command='sha256sum /tmp/bundle-{release_id}.tar.gz',
            expected_outcome='Checksum matches the release catalog value.',
            if_fail='If mismatch persists, artifact is corrupt — proceed to step 5.',
        ),
        TriageStep(
            order=4,
            action='Retry the upload for affected workspaces',
            command='curl -X POST https://<control-plane>/api/v1/workspaces/{workspace_id}/retry',
            expected_outcome='Workspace transitions from error to queued and eventually reaches ready.',
            if_fail='If retry also fails with checksum error, proceed to step 5.',
        ),
        TriageStep(
            order=5,
            action='Rebuild the release artifact from source',
            command='cd /repo && make release RELEASE_ID={release_id}',
            expected_outcome='New artifact produced with correct checksum.',
            if_fail='Escalate to release engineering with build logs.',
        ),
        TriageStep(
            order=6,
            action='Update the release catalog with new checksum',
            command='curl -X PATCH https://<control-plane>/api/v1/releases/{release_id} -d \'{"bundle_sha256": "<new_sha256>"}\'',
            expected_outcome='Release catalog updated, retry succeeds.',
            if_fail='If update rejected, rollback to previous known-good release.',
        ),
        TriageStep(
            order=7,
            action='Rollback to previous release if rebuild fails',
            command='curl -X POST https://<control-plane>/api/v1/releases/{release_id}/rollback',
            expected_outcome='Affected workspaces provisioned with previous stable release.',
            if_fail='Escalate: multiple releases corrupt, possible supply-chain incident.',
        ),
    )

    comms_templates = (
        CommsTemplate(
            template_type=CommsTemplateType.TRIAGE_NOTE,
            audience='on-call operator',
            subject_template='[TRIAGE] Checksum failure: {affected_count} workspaces on release {release_id}',
            body_template=(
                '## Triage Note\n\n'
                '**Error code:** {error_code}\n'
                '**Affected workspaces:** {affected_count}\n'
                '**Release:** {release_id}\n'
                '**Expected SHA256:** {expected_sha256}\n'
                '**Actual SHA256:** {actual_sha256}\n\n'
                '### Next steps\n'
                '1. Verify artifact integrity (step 3)\n'
                '2. Retry upload or rebuild (steps 4-5)\n'
                '3. Update status within {max_triage_minutes} minutes\n'
            ),
            placeholders=(
                'error_code', 'affected_count', 'release_id',
                'expected_sha256', 'actual_sha256', 'max_triage_minutes',
            ),
        ),
        CommsTemplate(
            template_type=CommsTemplateType.STATUS_UPDATE,
            audience='workspace owners',
            subject_template='[STATUS] Provisioning delayed for {affected_count} workspace(s)',
            body_template=(
                '## Status Update\n\n'
                'We are aware of a provisioning issue affecting '
                '{affected_count} workspace(s).\n\n'
                '**Cause:** Artifact verification failure during deployment.\n'
                '**Impact:** New workspace provisioning is temporarily paused.\n'
                '**ETA:** Resolution expected within {eta_minutes} minutes.\n\n'
                'Existing running workspaces are not affected.\n'
            ),
            placeholders=(
                'affected_count', 'eta_minutes',
            ),
        ),
        CommsTemplate(
            template_type=CommsTemplateType.RESOLUTION_SUMMARY,
            audience='engineering team',
            subject_template='[RESOLVED] Checksum failure incident for release {release_id}',
            body_template=(
                '## Resolution Summary\n\n'
                '**Incident duration:** {duration_minutes} minutes\n'
                '**Root cause:** {root_cause}\n'
                '**Resolution:** {resolution}\n'
                '**Affected workspaces:** {affected_count}\n'
                '**Workspaces recovered:** {recovered_count}\n\n'
                '### Timeline\n'
                '- {detected_at}: Checksum failure detected\n'
                '- {triaged_at}: Triage started\n'
                '- {resolved_at}: Resolution applied\n\n'
                '### Follow-up actions\n'
                '- [ ] Add checksum pre-check to CI pipeline\n'
                '- [ ] Review artifact build reproducibility\n'
            ),
            placeholders=(
                'duration_minutes', 'root_cause', 'resolution',
                'affected_count', 'recovered_count',
                'detected_at', 'triaged_at', 'resolved_at',
            ),
        ),
    )

    return ChecksumFailureRunbook(
        trigger_codes=REQUIRED_TRIGGER_CODES,
        triage_steps=triage_steps,
        comms_templates=comms_templates,
        owner='runtime_owner',
        max_triage_minutes=15,
    )


DEFAULT_CHECKSUM_FAILURE_RUNBOOK = build_checksum_failure_runbook()


# ── Validation ──────────────────────────────────────────────────────


def validate_checksum_failure_runbook(
    runbook: ChecksumFailureRunbook,
) -> None:
    """Validate that the runbook meets operational requirements.

    Raises:
        ValueError: If required contracts are not met.
    """
    # All trigger codes covered.
    if not REQUIRED_TRIGGER_CODES.issubset(runbook.trigger_codes):
        missing = sorted(REQUIRED_TRIGGER_CODES - runbook.trigger_codes)
        raise ValueError(f'Missing trigger codes: {missing}')

    # All comms types covered.
    covered_types = {t.template_type for t in runbook.comms_templates}
    missing_types = REQUIRED_COMMS_TYPES - covered_types
    if missing_types:
        raise ValueError(
            f'Missing comms templates: '
            f'{sorted(t.value for t in missing_types)}'
        )

    # Steps in order.
    orders = [step.order for step in runbook.triage_steps]
    if orders != sorted(orders):
        raise ValueError('Triage steps not in ascending order')

    # All steps have if_fail guidance.
    for step in runbook.triage_steps:
        if not step.if_fail.strip():
            raise ValueError(
                f'Step {step.order} ({step.action!r}) has no failure guidance'
            )

    # All comms templates have placeholders.
    for tmpl in runbook.comms_templates:
        if not tmpl.placeholders:
            raise ValueError(
                f'Comms template {tmpl.template_type.value!r} has no placeholders'
            )

    # Owner required.
    if not runbook.owner:
        raise ValueError('Runbook has no owner')

    # Max triage time reasonable.
    if runbook.max_triage_minutes < 5:
        raise ValueError('Max triage minutes must be >= 5')
