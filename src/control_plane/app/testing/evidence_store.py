"""Persist and index visual proof artifacts alongside scenario outputs.

Bead: bd-223o.16.4.1 (K4a)

Provides durable storage of artifact references within scenario results
so that downstream reporting (K5) and issue tracking (beads) can
discover and link evidence without re-running scenarios.

Usage::

    store = EvidenceStore(Path('evidence'))
    store.attach_artifacts(scenario_result, artifacts)
    index = store.build_index()
    comment = format_beads_comment(scenario_result, artifacts)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenario_runner import ScenarioResult, StepOutcome
from .visual_proof import ArtifactType, EvidenceArtifact


@dataclass(frozen=True, slots=True)
class AttachedScenario:
    """A scenario result with its attached evidence artifacts."""

    scenario_id: str
    title: str
    passed: bool
    step_count: int
    pass_count: int
    fail_count: int
    error_count: int
    duration_ms: float
    started_at: str
    finished_at: str
    artifacts: tuple[dict[str, Any], ...]
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'scenario_id': self.scenario_id,
            'title': self.title,
            'passed': self.passed,
            'steps': self.step_count,
            'pass': self.pass_count,
            'fail': self.fail_count,
            'error': self.error_count,
            'duration_ms': round(self.duration_ms, 1),
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'artifact_count': len(self.artifacts),
            'artifacts': list(self.artifacts),
            'output_path': self.output_path,
        }


class EvidenceStore:
    """Manages persistence of evidence artifacts for scenario runs.

    Each scenario gets a sub-directory containing:
      - ``result.json``: Scenario outcome + attached artifact references.
      - Artifact files (screenshots, API responses, logs).
      - ``manifest.json``: Written by :class:`ProofSession.finalize`.

    The store also writes a top-level ``index.json`` for cross-scenario
    discovery.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._attached: list[AttachedScenario] = []

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def attach_artifacts(
        self,
        result: ScenarioResult,
        artifacts: tuple[EvidenceArtifact, ...] | list[EvidenceArtifact] = (),
    ) -> AttachedScenario:
        """Persist a scenario result with its artifact references.

        Writes ``result.json`` in the scenario sub-directory containing
        the full scenario outcome plus artifact metadata.
        """
        scenario_dir = self._output_dir / result.scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        artifact_dicts = tuple(a.to_dict() for a in artifacts)

        # Build per-step detail with linked artifacts.
        step_details = []
        artifact_by_step: dict[int, list[dict[str, Any]]] = {}
        for a in artifact_dicts:
            artifact_by_step.setdefault(a['step'], []).append(a)

        for step in result.step_results:
            detail: dict[str, Any] = {
                'step': step.step_number,
                'method': step.method,
                'path': step.path,
                'expected_status': step.expected_status,
                'actual_status': step.actual_status,
                'outcome': step.outcome.value,
                'duration_ms': round(step.duration_ms, 1),
                'request_id': step.request_id,
            }
            if step.error_detail:
                detail['error'] = step.error_detail
            if step.missing_fields:
                detail['missing_fields'] = list(step.missing_fields)

            step_artifacts = artifact_by_step.get(step.step_number, [])
            if step_artifacts:
                detail['artifacts'] = step_artifacts

            step_details.append(detail)

        output = {
            'scenario_id': result.scenario_id,
            'title': result.title,
            'passed': result.passed,
            'started_at': result.started_at,
            'finished_at': result.finished_at,
            'duration_ms': round(result.total_duration_ms, 1),
            'steps': step_details,
            'artifact_count': len(artifact_dicts),
            'artifacts': list(artifact_dicts),
        }

        result_path = scenario_dir / 'result.json'
        result_path.write_text(
            json.dumps(output, indent=2), encoding='utf-8',
        )

        attached = AttachedScenario(
            scenario_id=result.scenario_id,
            title=result.title,
            passed=result.passed,
            step_count=result.total_steps,
            pass_count=result.pass_count,
            fail_count=result.fail_count,
            error_count=result.error_count,
            duration_ms=result.total_duration_ms,
            started_at=result.started_at,
            finished_at=result.finished_at,
            artifacts=artifact_dicts,
            output_path=str(result_path.relative_to(self._output_dir)),
        )
        self._attached.append(attached)
        return attached

    def build_index(self) -> dict[str, Any]:
        """Build and write the top-level evidence index.

        The index lists all attached scenarios with summary stats and
        artifact counts, enabling K5 to aggregate across scenarios.

        Returns the index dict and writes it to ``index.json``.
        """
        total_pass = sum(a.pass_count for a in self._attached)
        total_fail = sum(a.fail_count for a in self._attached)
        total_error = sum(a.error_count for a in self._attached)
        total_artifacts = sum(len(a.artifacts) for a in self._attached)

        index = {
            'generated_at': _now_iso(),
            'scenario_count': len(self._attached),
            'overall_passed': all(a.passed for a in self._attached),
            'total_steps_pass': total_pass,
            'total_steps_fail': total_fail,
            'total_steps_error': total_error,
            'total_artifacts': total_artifacts,
            'scenarios': [a.to_dict() for a in self._attached],
        }

        index_path = self._output_dir / 'index.json'
        index_path.write_text(
            json.dumps(index, indent=2), encoding='utf-8',
        )

        return index


def format_beads_comment(
    result: ScenarioResult,
    artifacts: tuple[EvidenceArtifact, ...] | list[EvidenceArtifact] = (),
    *,
    evidence_base_url: str = '',
) -> str:
    """Format a scenario result as a beads issue comment.

    Produces a concise Markdown summary suitable for posting to a beads
    issue (or GitHub PR/issue) with artifact links.

    Args:
        result: Scenario execution result.
        artifacts: Evidence artifacts to reference.
        evidence_base_url: Optional base URL for artifact links.
            If empty, uses relative file paths.
    """
    icon = '\u2714' if result.passed else '\u2718'
    verdict = 'PASSED' if result.passed else 'FAILED'

    lines = [
        f'### {icon} {result.scenario_id}: {result.title} — {verdict}',
        '',
        f'| Steps | Pass | Fail | Error | Duration |',
        f'|-------|------|------|-------|----------|',
        f'| {result.total_steps} '
        f'| {result.pass_count} '
        f'| {result.fail_count} '
        f'| {result.error_count} '
        f'| {result.total_duration_ms:.0f}ms |',
        '',
    ]

    # List failed steps.
    failed_steps = [
        s for s in result.step_results
        if s.outcome in (StepOutcome.FAIL, StepOutcome.ERROR)
    ]
    if failed_steps:
        lines.append('**Failed steps:**')
        for step in failed_steps:
            lines.append(
                f'- Step {step.step_number}: {step.method} {step.path} '
                f'\u2192 {step.actual_status or "N/A"} '
                f'(expected {step.expected_status})'
            )
            if step.error_detail:
                lines.append(f'  - {step.error_detail}')
        lines.append('')

    # List evidence artifacts.
    if artifacts:
        lines.append(f'**Evidence ({len(artifacts)} artifacts):**')
        for artifact in artifacts:
            base = evidence_base_url.rstrip('/') + '/' if evidence_base_url else ''
            path = f'{base}{artifact.file_path}'
            if artifact.artifact_type == ArtifactType.SCREENSHOT:
                lines.append(f'- \U0001F4F8 [{artifact.description}]({path})')
            elif artifact.artifact_type == ArtifactType.API_RESPONSE:
                lines.append(f'- \U0001F4CB [{artifact.description}]({path})')
            elif artifact.artifact_type == ArtifactType.LOG_ENTRY:
                lines.append(f'- \U0001F4DD [{artifact.description}]({path})')
            else:
                lines.append(f'- [{artifact.description}]({path})')
        lines.append('')

    lines.append(
        f'*Run: {result.started_at} \u2192 {result.finished_at}*'
    )

    return '\n'.join(lines)


# ── Helpers ────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
