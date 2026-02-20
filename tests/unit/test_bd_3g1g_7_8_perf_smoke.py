"""Hermetic contract tests for bd-3g1g.7.8 perf_smoke suite."""

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


def test_perf_smoke_dry_run_emits_thresholds_json() -> None:
    root = _repo_root()
    script = root / "scripts" / "perf_smoke.py"
    assert script.exists()

    proc = subprocess.run(  # noqa: S603 - local repo script under test
        ["python3", str(script), "--dry-run"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert "thresholds" in payload
    thresholds = payload["thresholds"]
    assert isinstance(thresholds, dict) and thresholds, "Expected non-empty thresholds dict"

