#!/usr/bin/env python3
"""Run E2E scenario catalog against a deployed control plane.

Bead: bd-223o.16.3 (K3)

Usage::

    # Run all scenarios against a local control plane:
    python scripts/run_scenarios.py --base-url http://localhost:8000

    # Run a specific scenario:
    python scripts/run_scenarios.py --base-url http://localhost:8000 --scenario S-001

    # Run with auth:
    python scripts/run_scenarios.py --base-url https://boring-ui.modal.run \\
        --auth-token <jwt> --session-cookie <cookie>

    # Run critical-path scenarios only:
    python scripts/run_scenarios.py --base-url http://localhost:8000 --critical-only

    # Output JSON results:
    python scripts/run_scenarios.py --base-url http://localhost:8000 --json
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
    StepOutcome,
)


SCENARIOS_DIR = _PROJECT_ROOT / 'test-scenarios'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run E2E scenario catalog against a control plane.',
    )
    parser.add_argument(
        '--base-url',
        required=True,
        help='Base URL of the control plane (e.g., http://localhost:8000)',
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
        '--auth-token',
        help='Bearer token for authenticated requests',
    )
    parser.add_argument(
        '--session-cookie',
        help='Session cookie value (boring_session)',
    )
    parser.add_argument(
        '--no-fail-fast',
        action='store_true',
        help='Continue executing steps after a failure',
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
        help='Variable substitution (key=value), repeatable',
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
    """Parse --var key=value arguments into a dict."""
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
    """Filter scenarios by ID or critical path."""
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


def print_text_results(results: list[ScenarioResult]) -> None:
    """Print human-readable results."""
    total_pass = 0
    total_fail = 0
    total_error = 0

    for result in results:
        icon = '\u2714' if result.passed else '\u2718'
        print(f'\n{icon} {result.scenario_id}: {result.title}')
        print(f'  Steps: {result.total_steps} | '
              f'Pass: {result.pass_count} | '
              f'Fail: {result.fail_count} | '
              f'Error: {result.error_count} | '
              f'Duration: {result.total_duration_ms:.0f}ms')

        for step in result.step_results:
            if step.outcome == StepOutcome.PASS:
                marker = '  \u2714'
            elif step.outcome == StepOutcome.SKIP:
                marker = '  \u23E9'
            else:
                marker = '  \u2718'

            print(f'{marker} Step {step.step_number}: '
                  f'{step.method} {step.path} '
                  f'→ {step.actual_status or "N/A"} '
                  f'(expected {step.expected_status}) '
                  f'[{step.outcome.value}]')

            if step.error_detail:
                print(f'      {step.error_detail}')
            if step.request_id:
                print(f'      request_id: {step.request_id}')

        total_pass += result.pass_count
        total_fail += result.fail_count
        total_error += result.error_count

    print(f'\n{"=" * 60}')
    all_passed = total_fail == 0 and total_error == 0
    summary_icon = '\u2714' if all_passed else '\u2718'
    print(f'{summary_icon} Total: {total_pass} pass, '
          f'{total_fail} fail, {total_error} error '
          f'across {len(results)} scenarios')

    if not all_passed:
        failed = [r for r in results if not r.passed]
        print(f'\nFailed scenarios:')
        for r in failed:
            print(f'  - {r.scenario_id}: {r.title}')


def print_json_results(results: list[ScenarioResult]) -> None:
    """Print JSON results."""
    output = {
        'scenarios': [r.summary() for r in results],
        'overall_passed': all(r.passed for r in results),
        'total_scenarios': len(results),
        'total_pass': sum(r.pass_count for r in results),
        'total_fail': sum(r.fail_count for r in results),
        'total_error': sum(r.error_count for r in results),
    }
    print(json.dumps(output, indent=2))


async def main() -> int:
    args = parse_args()

    # Load and filter scenarios.
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

    config = RunConfig(
        base_url=args.base_url,
        session_cookie=args.session_cookie,
        auth_token=args.auth_token,
        timeout_seconds=args.timeout,
        fail_fast=not args.no_fail_fast,
        variable_map=variable_map,
    )

    runner = ScenarioRunner(config)
    results: list[ScenarioResult] = []

    for spec in specs:
        result = await runner.run(spec)
        results.append(result)

    if args.json_output:
        print_json_results(results)
    else:
        print_text_results(results)

    return 0 if all(r.passed for r in results) else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
