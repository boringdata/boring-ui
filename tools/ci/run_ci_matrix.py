#!/usr/bin/env python3
"""Run CI matrix suites with failure-centric reporting artifacts."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _ensure_import_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_back = repo_root / 'src' / 'back'
    if str(src_back) not in sys.path:
        sys.path.insert(0, str(src_back))


_ensure_import_path()

from boring_ui.api.ci_matrix import (  # noqa: E402
    CIMatrixRunner,
    FlakyTestTracker,
    MatrixEnv,
    RunStatus,
    get_matrix_suites,
)


REQUEST_ID_PATTERNS = [
    re.compile(r'request[_-]?id["\']?\s*[:=]\s*["\']?([0-9a-fA-F-]{8,})'),
    re.compile(r'\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b'),
]


def extract_request_id(text: str) -> str:
    """Extract a correlated request_id from test output text."""
    for pattern in REQUEST_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ''


def parse_junit_counts(path: Path) -> dict[str, int]:
    """Parse pytest junit xml and return aggregate counts."""
    if not path.exists():
        return {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0, 'passed': 0}

    root = ET.fromstring(path.read_text())
    tests = failures = errors = skipped = 0

    if root.tag == 'testsuite':
        suites = [root]
    else:
        suites = list(root.findall('testsuite'))

    for suite in suites:
        tests += int(suite.attrib.get('tests', 0))
        failures += int(suite.attrib.get('failures', 0))
        errors += int(suite.attrib.get('errors', 0))
        skipped += int(suite.attrib.get('skipped', 0))

    passed = max(tests - failures - errors - skipped, 0)
    return {
        'tests': tests,
        'failures': failures,
        'errors': errors,
        'skipped': skipped,
        'passed': passed,
    }


def first_failure_from_junit(path: Path) -> dict[str, Any] | None:
    """Return first failure details from junit xml."""
    if not path.exists():
        return None

    root = ET.fromstring(path.read_text())
    cases = root.findall('.//testcase')
    for case in cases:
        failure = case.find('failure') or case.find('error')
        if failure is None:
            continue
        return {
            'test_name': case.attrib.get('name', 'unknown'),
            'message': (failure.attrib.get('message') or (failure.text or '')).strip()[:2000],
            'file_path': case.attrib.get('classname', ''),
        }
    return None


def run_suite_pytest(
    test_path: str,
    *,
    artifacts_dir: Path,
    suite_label: str,
) -> dict[str, Any]:
    """Run a pytest suite and return ci_matrix-compatible simulated results."""
    suite_dir = artifacts_dir / 'suite-results' / suite_label
    suite_dir.mkdir(parents=True, exist_ok=True)

    junit_path = suite_dir / 'junit.xml'
    output_path = suite_dir / 'pytest-output.log'

    cmd = [
        sys.executable,
        '-m',
        'pytest',
        test_path,
        '-q',
        '--maxfail=1',
        f'--junitxml={junit_path}',
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    output = f'{proc.stdout}\n{proc.stderr}'.strip()
    output_path.write_text(output)
    counts = parse_junit_counts(junit_path)
    request_id = extract_request_id(output)
    first_failure = first_failure_from_junit(junit_path)

    failures = []
    if first_failure:
        failures.append(
            {
                'test_name': first_failure['test_name'],
                'message': first_failure['message'],
                'request_id': request_id,
                'file_path': first_failure['file_path'],
                'artifact_path': str(output_path),
            }
        )

    return {
        'passed': counts['passed'],
        'failed': counts['failures'],
        'errors': counts['errors'],
        'skipped': counts['skipped'],
        'failures': failures,
    }


def credentials_available() -> bool:
    required = ['SPRITES_API_TOKEN', 'SPRITES_BASE_URL', 'SPRITES_SPRITE_NAME']
    return all(os.getenv(name, '').strip() for name in required)


def main() -> int:
    parser = argparse.ArgumentParser(description='Run CI matrix suites.')
    parser.add_argument(
        '--env',
        choices=['all', 'local', 'sandbox-stubbed', 'live-smoke'],
        default='all',
        help='Matrix environment to run',
    )
    parser.add_argument(
        '--artifacts-dir',
        default='artifacts',
        help='Output directory for report artifacts',
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if args.env == 'all':
        suites = get_matrix_suites()
    else:
        suites = get_matrix_suites(envs=[MatrixEnv(args.env)])

    flaky_path = artifacts_dir / 'ci-matrix' / 'flaky-tracker.json'
    flaky_tracker = FlakyTestTracker.load(flaky_path)
    runner = CIMatrixRunner(suites=suites, flaky_tracker=flaky_tracker)

    creds = credentials_available()
    for suite in suites:
        if suite.requires_credentials and not creds:
            runner.run_suite(
                suite,
                simulate_results={
                    'credentials_available': False,
                    'expected_tests': 1,
                },
            )
            continue

        sim = run_suite_pytest(
            suite.test_path,
            artifacts_dir=artifacts_dir,
            suite_label=suite.label,
        )
        runner.run_suite(suite, simulate_results=sim)

    report = runner.generate_report()
    report_path = runner.save_report(report, artifacts_dir)
    runner.flaky_tracker.save(flaky_path)

    summary_text = report.to_summary_line()
    print(summary_text)
    if report.first_failure:
        ff = report.first_failure
        print(
            f'First failure: {ff.test_name} | request_id={ff.request_id or "n/a"} | '
            f'artifact={ff.artifact_path or "n/a"}'
        )
    print(f'Report artifact: {report_path}')

    if report.overall_status in (RunStatus.FAILED, RunStatus.ERROR):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

