#!/usr/bin/env python3
"""Run scenario catalog with visual proof capture.

Bead: bd-223o.16.4 (K4)

Combines the scenario runner (K3) with visual proof capture to produce
Markdown evidence reports alongside API validation results.

Usage::

    # Run all scenarios with proof capture:
    python scripts/run_visual_proof.py --base-url http://localhost:8000 \
        --app-url http://localhost:5173 --output-dir evidence/

    # Run a specific scenario:
    python scripts/run_visual_proof.py --base-url http://localhost:8000 \
        --app-url http://localhost:5173 --scenario S-001

    # API-only (no browser screenshots):
    python scripts/run_visual_proof.py --base-url http://localhost:8000 \
        --no-screenshots --output-dir evidence/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path for imports.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / 'src'))

from control_plane.app.testing.scenario_parser import (
    ScenarioSpec,
    scan_scenario_dir,
)
from control_plane.app.testing.scenario_runner import (
    RunConfig,
    ScenarioResult,
    ScenarioRunner,
)
from control_plane.app.testing.visual_proof import (
    CaptureConfig,
    ProofSession,
)
from control_plane.app.testing.proof_report import build_proof_report

SCENARIOS_DIR = _PROJECT_ROOT / 'test-scenarios'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run scenarios with visual proof capture.',
    )
    parser.add_argument(
        '--base-url',
        required=True,
        help='Base URL of the control plane API',
    )
    parser.add_argument(
        '--app-url',
        help='Base URL of the frontend app (for screenshots)',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('evidence'),
        help='Directory for evidence artifacts (default: evidence/)',
    )
    parser.add_argument(
        '--scenario',
        help='Run a single scenario by ID (e.g., S-001)',
    )
    parser.add_argument(
        '--critical-only',
        action='store_true',
        help='Run only critical-path scenarios',
    )
    parser.add_argument(
        '--no-screenshots',
        action='store_true',
        help='Skip browser screenshot capture (API-only)',
    )
    parser.add_argument(
        '--auth-token',
        help='Bearer token for authenticated requests',
    )
    parser.add_argument(
        '--session-cookie',
        help='Session cookie value',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=30.0,
        help='Request timeout in seconds (default: 30)',
    )
    parser.add_argument(
        '--var',
        action='append',
        default=[],
        help='Variable substitution (key=value)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Output results as JSON',
    )
    parser.add_argument(
        '--scenarios-dir',
        type=Path,
        default=SCENARIOS_DIR,
        help=f'Scenarios directory (default: {SCENARIOS_DIR})',
    )
    return parser.parse_args()


def build_variable_map(var_args: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for arg in var_args:
        if '=' not in arg:
            print(f'WARNING: Ignoring malformed --var: {arg}', file=sys.stderr)
            continue
        key, value = arg.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def filter_scenarios(
    specs: list[ScenarioSpec],
    *,
    scenario_id: str | None = None,
    critical_only: bool = False,
) -> list[ScenarioSpec]:
    if scenario_id:
        matched = [s for s in specs if s.scenario_id == scenario_id]
        if not matched:
            available = ', '.join(s.scenario_id for s in specs)
            print(
                f'ERROR: Scenario {scenario_id} not found. '
                f'Available: {available}',
                file=sys.stderr,
            )
            sys.exit(1)
        return matched
    if critical_only:
        return [s for s in specs if s.critical_path]
    return specs


async def run_scenario_with_proof(
    runner: ScenarioRunner,
    spec: ScenarioSpec,
    capture_config: CaptureConfig,
    *,
    app_url: str | None = None,
    capture_screenshots: bool = True,
) -> tuple[ScenarioResult, ProofSession]:
    """Run a scenario and capture evidence artifacts."""
    session = ProofSession(capture_config, spec.scenario_id)

    # Execute API steps.
    result = await runner.run(spec)

    # Record API responses as evidence.
    for step in result.step_results:
        if step.actual_status is not None:
            session.record_api_response(
                step=step.step_number,
                method=step.method,
                path=step.path,
                status=step.actual_status,
                body=step.response_body,
                request_id=step.request_id,
            )

    # Capture screenshot of app if URL provided and enabled.
    if capture_screenshots and app_url:
        try:
            await session.capture_screenshot(
                step=0,
                description='App state after scenario execution',
                url=app_url,
            )
        except RuntimeError as exc:
            session.record_log_entry(
                step=0,
                description='Screenshot capture failed',
                log_text=str(exc),
            )

    session.finalize()
    return result, session


async def main() -> int:
    args = parse_args()

    specs = scan_scenario_dir(args.scenarios_dir)
    if not specs:
        print(f'ERROR: No scenarios found in {args.scenarios_dir}',
              file=sys.stderr)
        return 1

    specs = filter_scenarios(
        specs,
        scenario_id=args.scenario,
        critical_only=args.critical_only,
    )

    variable_map = build_variable_map(args.var)

    run_config = RunConfig(
        base_url=args.base_url,
        session_cookie=args.session_cookie,
        auth_token=args.auth_token,
        timeout_seconds=args.timeout,
        fail_fast=True,
        variable_map=variable_map,
    )

    capture_config = CaptureConfig(output_dir=args.output_dir)

    runner = ScenarioRunner(run_config)
    all_results: list[dict] = []

    for spec in specs:
        result, session = await run_scenario_with_proof(
            runner,
            spec,
            capture_config,
            app_url=args.app_url,
            capture_screenshots=not args.no_screenshots,
        )

        # Write proof report.
        artifacts = session.finalize()
        report = build_proof_report(result, artifacts)
        report_path = capture_config.output_dir / spec.scenario_id / 'report.md'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding='utf-8')

        icon = '\u2714' if result.passed else '\u2718'
        print(f'{icon} {result.scenario_id}: {result.title} '
              f'({len(artifacts)} artifacts)')

        all_results.append({
            **result.summary(),
            'artifacts': len(artifacts),
            'report': str(report_path),
        })

    if args.json_output:
        output = {
            'scenarios': all_results,
            'overall_passed': all(r['passed'] for r in all_results),
            'output_dir': str(args.output_dir),
        }
        print(json.dumps(output, indent=2))

    overall = all(r['passed'] for r in all_results)
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
