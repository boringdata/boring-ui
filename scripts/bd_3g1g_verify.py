#!/usr/bin/env python3
"""Verification runner for bd-3g1g (Phase 5 gate).

Goal (bd-3g1g.7.5): provide a single repeatable command that runs the core
verification matrix and emits structured logs + a machine-readable manifest.

This runner intentionally favors determinism:
- Captures stdout/stderr per step into timestamped log files.
- Records the exact command + environment overrides used.
- Supports --dry-run for quick inspection and unit testing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class Step:
    name: str
    cmd: list[str]
    env_overrides: dict[str, str]


@dataclass
class StepResult:
    name: str
    cmd: list[str]
    env_overrides: dict[str, str]
    log_path: str
    exit_code: int
    duration_seconds: float


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "package.json").exists():
            return parent
    raise RuntimeError("Could not locate repository root (pyproject.toml + package.json)")


def _build_steps(repo_root: Path) -> list[Step]:
    # Ensure node-based steps use real Node even when `node` resolves to Bun.
    # Playwright e2e already has a wrapper for this, but vitest is commonly run
    # directly.
    node_env_overrides = {"PATH": f"/usr/bin:{os.environ.get('PATH','')}"}

    return [
        Step(
            name="static_forbidden_routes",
            cmd=[sys.executable, "scripts/check_forbidden_direct_routes.py"],
            env_overrides={},
        ),
        Step(
            name="pytest_unit",
            cmd=[sys.executable, "-m", "pytest", "-q", "tests/unit"],
            env_overrides={},
        ),
        Step(
            name="pytest_integration",
            cmd=[sys.executable, "-m", "pytest", "-q", "tests/integration"],
            env_overrides={},
        ),
        Step(
            name="vitest",
            cmd=["npm", "run", "-s", "test:run"],
            env_overrides=node_env_overrides,
        ),
        Step(
            name="playwright_e2e",
            cmd=["npm", "run", "-s", "test:e2e"],
            env_overrides=node_env_overrides,
        ),
        # UBS is best-effort in this environment; callers can skip explicitly.
        Step(
            name="ubs_js_only",
            cmd=["ubs", "--only=js", "."],
            env_overrides={},
        ),
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_step(repo_root: Path, out_dir: Path, step: Step) -> StepResult:
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{step.name}.log"

    env = os.environ.copy()
    env.update(step.env_overrides)

    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(  # noqa: S603 - controlled local commands
            step.cmd,
            cwd=str(repo_root),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        exit_code = proc.wait()
    duration = time.monotonic() - start

    return StepResult(
        name=step.name,
        cmd=list(step.cmd),
        env_overrides=dict(step.env_overrides),
        log_path=str(log_path),
        exit_code=int(exit_code),
        duration_seconds=float(duration),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bd-3g1g verification matrix with structured logs.")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory. Default: .verify/bd-3g1g/<UTC timestamp>/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps JSON and exit without running anything.",
    )
    parser.add_argument(
        "--list-steps",
        action="store_true",
        help="List step names (one per line) and exit.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated step names to run (default: run all).",
    )
    parser.add_argument(
        "--skip-ubs",
        action="store_true",
        help="Skip UBS step (useful when UBS modules are unavailable).",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip Playwright e2e step.",
    )
    parser.add_argument(
        "--skip-vitest",
        action="store_true",
        help="Skip Vitest step.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    steps = _build_steps(repo_root)
    if args.skip_ubs:
        steps = [step for step in steps if step.name != "ubs_js_only"]
    if args.skip_e2e:
        steps = [step for step in steps if step.name != "playwright_e2e"]
    if args.skip_vitest:
        steps = [step for step in steps if step.name != "vitest"]

    only = [item.strip() for item in (args.only or "").split(",") if item.strip()]
    if only:
        allow = set(only)
        steps = [step for step in steps if step.name in allow]
        missing = sorted(set(only) - {step.name for step in steps})
        if missing:
            print(f"error: unknown step(s): {', '.join(missing)}", file=sys.stderr)
            return 2

    if args.list_steps:
        for step in steps:
            print(step.name)
        return 0

    if args.dry_run:
        payload = {"steps": [asdict(step) for step in steps]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    out_dir = Path(args.out_dir) if args.out_dir else (repo_root / ".verify" / "bd-3g1g" / _utc_now())
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[StepResult] = []
    overall_ok = True

    for step in steps:
        result = _run_step(repo_root, out_dir, step)
        results.append(result)
        if result.exit_code != 0:
            overall_ok = False
            # Keep going so reviewers get a complete artifact set.

    manifest = {
        "repo_root": str(repo_root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_ok": overall_ok,
        "results": [asdict(r) for r in results],
    }
    _write_json(out_dir / "manifest.json", manifest)

    # Print the manifest path as the final line for easy copying in evidence.
    print(str(out_dir / "manifest.json"))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
