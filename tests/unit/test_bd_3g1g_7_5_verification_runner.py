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


def test_verification_runner_only_filters_and_unknown_step_errors() -> None:
    root = _repo_root()
    script = root / "scripts" / "bd_3g1g_verify.py"

    proc = subprocess.run(  # noqa: S603 - local repo script under test
        ["python3", str(script), "--dry-run", "--skip-ubs", "--only=pytest_unit"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    names = [step.get("name") for step in payload.get("steps", []) if isinstance(step, dict)]
    assert names == ["pytest_unit"]

    bad = subprocess.run(  # noqa: S603 - local repo script under test
        ["python3", str(script), "--dry-run", "--skip-ubs", "--only=does_not_exist"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 2
    assert "unknown step" in (bad.stderr or "").lower()


def test_verification_runner_playwright_env_overrides_are_present_and_usable() -> None:
    root = _repo_root()
    script = root / "scripts" / "bd_3g1g_verify.py"

    proc = subprocess.run(  # noqa: S603 - local repo script under test
        ["python3", str(script), "--dry-run", "--skip-ubs", "--only=playwright_e2e"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    steps = payload.get("steps")
    assert isinstance(steps, list) and steps, "Expected non-empty steps list"
    assert steps[0].get("name") == "playwright_e2e"

    env_overrides = steps[0].get("env_overrides")
    assert isinstance(env_overrides, dict)
    assert env_overrides.get("PW_E2E_REUSE_SERVER") == "0"
    assert env_overrides.get("PW_E2E_WORKERS") == "1"

    e2e_port = env_overrides.get("PW_E2E_PORT")
    api_port = env_overrides.get("PW_E2E_API_PORT")
    assert isinstance(e2e_port, str) and e2e_port.isdigit()
    assert isinstance(api_port, str) and api_port.isdigit()
    assert e2e_port != api_port
