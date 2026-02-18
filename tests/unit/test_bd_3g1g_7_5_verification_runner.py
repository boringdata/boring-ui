"""Unit coverage for bd-3g1g.7.5 verification runner.

We only validate the runner's plan/manifest contract in dry-run mode to keep
tests fast and hermetic.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "package.json").exists():
            return parent
    raise AssertionError("Could not locate repository root from test path")


def test_verification_runner_dry_run_emits_step_plan_json() -> None:
    root = _repo_root()
    script = root / "scripts" / "bd_3g1g_verify.py"
    assert script.exists()

    proc = subprocess.run(  # noqa: S603 - local repo script under test
        ["python3", str(script), "--dry-run", "--skip-ubs"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    steps = payload.get("steps")
    assert isinstance(steps, list) and steps, "Expected non-empty steps list"

    names = [step.get("name") for step in steps if isinstance(step, dict)]
    assert "static_forbidden_routes" in names
    assert "pytest_unit" in names
    assert "pytest_integration" in names
    assert "vitest" in names
    assert "playwright_e2e" in names
    assert "ubs_js_only" not in names, "Expected --skip-ubs to remove UBS step"

