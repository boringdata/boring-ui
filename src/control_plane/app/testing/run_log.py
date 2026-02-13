"""Structured run log for machine-readable scenario execution output.

Bead: bd-223o.16.3.1 (K3a)

Aggregates per-scenario run logs into a single machine-readable report
with metadata, per-step expected/observed evidence, and summary verdict.

Usage::

    log = RunLog.from_results(results, run_id='run-abc')
    output = log.to_dict()          # dict suitable for json.dumps
    json_str = log.to_json()        # formatted JSON string
    log.write(Path('evidence/run-abc.json'))

The output format ties each scenario step to expected and observed
behavior for downstream evidence collection (K3a) and report
generation (K4).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenario_runner import ScenarioResult, StepOutcome


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_run_id() -> str:
    return f'run-{uuid.uuid4().hex[:12]}'


@dataclass(frozen=True, slots=True)
class RunLog:
    """Machine-readable log of one or more scenario executions.

    Attributes:
        run_id: Unique identifier for this run.
        created_at: ISO-8601 timestamp of log creation.
        scenarios: Per-scenario run log dicts.
        metadata: Optional key-value metadata (base_url, auth mode, etc.).
    """

    run_id: str
    created_at: str
    scenarios: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_results(
        results: list[ScenarioResult] | tuple[ScenarioResult, ...],
        *,
        run_id: str = '',
        include_bodies: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> RunLog:
        """Build a RunLog from scenario results.

        Args:
            results: Completed scenario results.
            run_id: Optional run identifier (auto-generated if empty).
            include_bodies: If True, include full response bodies.
            metadata: Optional metadata to attach to the log.

        Returns:
            RunLog with per-scenario and per-step evidence.
        """
        return RunLog(
            run_id=run_id or _generate_run_id(),
            created_at=_now_iso(),
            scenarios=tuple(
                r.to_run_log(include_bodies=include_bodies)
                for r in results
            ),
            metadata=metadata or {},
        )

    @property
    def overall_passed(self) -> bool:
        """True if all scenarios passed."""
        return all(s['verdict'] == 'pass' for s in self.scenarios)

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)

    @property
    def total_steps(self) -> int:
        return sum(s['counts']['total'] for s in self.scenarios)

    @property
    def total_pass(self) -> int:
        return sum(s['counts']['pass'] for s in self.scenarios)

    @property
    def total_fail(self) -> int:
        return sum(s['counts']['fail'] for s in self.scenarios)

    @property
    def total_error(self) -> int:
        return sum(s['counts']['error'] for s in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            'run_id': self.run_id,
            'created_at': self.created_at,
            'overall_passed': self.overall_passed,
            'summary': {
                'scenarios': self.scenario_count,
                'steps': self.total_steps,
                'pass': self.total_pass,
                'fail': self.total_fail,
                'error': self.total_error,
            },
            'metadata': self.metadata,
            'scenarios': list(self.scenarios),
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, path: Path) -> None:
        """Write the run log to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding='utf-8')

    def failed_steps(self) -> list[dict[str, Any]]:
        """Return all failed or errored steps across scenarios.

        Each entry includes the parent scenario_id for traceability.
        """
        failures: list[dict[str, Any]] = []
        for scenario in self.scenarios:
            for step in scenario['steps']:
                if step['outcome'] in ('fail', 'error'):
                    entry = dict(step)
                    entry['scenario_id'] = scenario['scenario_id']
                    failures.append(entry)
        return failures
