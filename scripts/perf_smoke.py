#!/usr/bin/env python3
"""Lightweight performance smoke suite for Phase-5 verification matrix.

This intentionally measures a small set of representative operations and fails
only on egregious regressions. Thresholds are configurable via a single env var:

  PERF_SMOKE_THRESHOLDS_JSON='{"git_status": 10.0, "pty_connect": 5.0}'

The suite prints a JSON summary to stdout and returns non-zero if any threshold
is exceeded or a required operation fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import websockets


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "package.json").exists():
            return parent
    raise RuntimeError("Could not locate repository root (pyproject.toml + package.json)")


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _load_thresholds() -> dict[str, float]:
    defaults: dict[str, float] = {
        "file_list": 5.0,
        "file_write_1mb": 2.0,
        "file_read_1mb": 2.0,
        "git_status": 8.0,
        "git_diff_name_only": 8.0,
        "server_startup": 10.0,
        "pty_connect": 5.0,
        "pty_roundtrip": 5.0,
        "stream_connect": 8.0,
    }
    raw = (os.environ.get("PERF_SMOKE_THRESHOLDS_JSON") or "").strip()
    if not raw:
        return defaults
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid PERF_SMOKE_THRESHOLDS_JSON: {e}") from e
    if not isinstance(payload, dict):
        raise RuntimeError("PERF_SMOKE_THRESHOLDS_JSON must be a JSON object")
    thresholds = dict(defaults)
    for k, v in payload.items():
        try:
            thresholds[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return thresholds


def _run(cmd: list[str], cwd: Path) -> tuple[int, float]:
    start = time.monotonic()
    proc = subprocess.run(  # noqa: S603 - local smoke commands
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return int(proc.returncode), float(time.monotonic() - start)


@dataclass(frozen=True)
class Measurement:
    name: str
    seconds: float
    ok: bool
    detail: str = ""


async def _ws_first_message(url: str, *, send_json: dict[str, Any] | None = None) -> tuple[float, str]:
    start = time.monotonic()
    async with websockets.connect(  # type: ignore[attr-defined]
        url,
        ping_interval=None,
        close_timeout=1,
        max_queue=1,
    ) as ws:
        if send_json is not None:
            await ws.send(json.dumps(send_json))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
    return float(time.monotonic() - start), str(msg)


async def _pty_connect_and_ping(base_http_url: str) -> tuple[float, float]:
    # Expect /ws/pty router mounted and provider=claude to exist (may be overridden in env).
    ws_url = base_http_url.replace("http://", "ws://") + "/ws/pty?provider=claude&session_id=00000000-0000-0000-0000-000000000001"
    connect_start = time.monotonic()
    async with websockets.connect(  # type: ignore[attr-defined]
        ws_url,
        ping_interval=None,
        close_timeout=1,
        max_queue=1,
    ) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)  # session (or error) message
        connect_seconds = float(time.monotonic() - connect_start)
        roundtrip_start = time.monotonic()
        await ws.send(json.dumps({"type": "ping"}))
        await asyncio.wait_for(ws.recv(), timeout=5)  # pong
        roundtrip_seconds = float(time.monotonic() - roundtrip_start)
    return connect_seconds, roundtrip_seconds


def _start_backend(repo_root: Path, port: int) -> tuple[subprocess.Popen[str], float, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src/back"
    env["BORING_UI_WORKSPACE_ROOT"] = str(repo_root)
    # Keep the perf smoke hermetic: don't require an external `claude` executable for PTY.
    env.setdefault("BORING_UI_PTY_CLAUDE_COMMAND", "bash")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "boring_ui.runtime:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
        "--no-access-log",
    ]

    start = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603 - controlled local server
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    base_http = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10.0
    last_exc: str = ""
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_http}/health", timeout=0.5)
            if r.status_code == 200:
                return proc, float(time.monotonic() - start), base_http
        except Exception as e:  # noqa: BLE001
            last_exc = str(e)
        time.sleep(0.05)

    try:
        proc.terminate()
    except Exception:
        pass
    return proc, float(time.monotonic() - start), base_http + f" (unhealthy: {last_exc})"


def _stop_backend(proc: subprocess.Popen[str]) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-5 performance smoke suite.")
    parser.add_argument("--dry-run", action="store_true", help="Print thresholds + plan JSON and exit.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    thresholds = _load_thresholds()

    if args.dry_run:
        print(json.dumps({"thresholds": thresholds, "repo_root": str(repo_root)}, indent=2, sort_keys=True))
        return 0

    measurements: list[Measurement] = []

    # File list: enumerate files under src/ (stable-ish, representative).
    start = time.monotonic()
    src_dir = repo_root / "src"
    try:
        count = 0
        for _ in src_dir.rglob("*"):
            count += 1
        seconds = float(time.monotonic() - start)
        measurements.append(Measurement("file_list", seconds, True, detail=f"entries={count}"))
    except Exception as e:  # noqa: BLE001
        measurements.append(Measurement("file_list", float(time.monotonic() - start), False, detail=str(e)))

    # File write/read: 1 MiB payload in temp dir.
    payload = b"x" * (1024 * 1024)
    with tempfile.TemporaryDirectory(prefix="perf_smoke_") as td:
        path = Path(td) / "blob.bin"
        w_start = time.monotonic()
        try:
            path.write_bytes(payload)
            measurements.append(Measurement("file_write_1mb", float(time.monotonic() - w_start), True))
        except Exception as e:  # noqa: BLE001
            measurements.append(Measurement("file_write_1mb", float(time.monotonic() - w_start), False, detail=str(e)))

        r_start = time.monotonic()
        try:
            _ = path.read_bytes()
            measurements.append(Measurement("file_read_1mb", float(time.monotonic() - r_start), True))
        except Exception as e:  # noqa: BLE001
            measurements.append(Measurement("file_read_1mb", float(time.monotonic() - r_start), False, detail=str(e)))

    # Git status/diff.
    rc, sec = _run(["git", "status", "--porcelain"], repo_root)
    measurements.append(Measurement("git_status", sec, rc == 0, detail=f"exit={rc}"))
    rc, sec = _run(["git", "diff", "--name-only"], repo_root)
    measurements.append(Measurement("git_diff_name_only", sec, rc == 0, detail=f"exit={rc}"))

    # Backend + WS handshakes.
    port = _pick_free_port()
    proc, startup_seconds, base_http = _start_backend(repo_root, port)
    measurements.append(Measurement("server_startup", startup_seconds, base_http.startswith("http://"), detail=base_http))

    if base_http.startswith("http://"):
        try:
            connect_s, rtt_s = asyncio.run(_pty_connect_and_ping(base_http))
            measurements.append(Measurement("pty_connect", connect_s, True))
            measurements.append(Measurement("pty_roundtrip", rtt_s, True))
        except Exception as e:  # noqa: BLE001
            measurements.append(Measurement("pty_connect", 0.0, False, detail=str(e)))
            measurements.append(Measurement("pty_roundtrip", 0.0, False, detail=str(e)))

        try:
            stream_url = base_http.replace("http://", "ws://") + (
                "/ws/agent/normal/stream?mode=ask&session_id=00000000-0000-0000-0000-000000000002"
            )
            sec, first = asyncio.run(_ws_first_message(stream_url))
            # The stream handshake may legitimately fail fast if `claude` is unavailable; we still record timing.
            measurements.append(Measurement("stream_connect", sec, True, detail=first[:200]))
        except Exception as e:  # noqa: BLE001
            measurements.append(Measurement("stream_connect", 0.0, False, detail=str(e)))

    _stop_backend(proc)

    # Apply thresholds.
    failures: list[str] = []
    for m in measurements:
        max_s = thresholds.get(m.name)
        if not m.ok:
            failures.append(f"{m.name}: failed ({m.detail})")
            continue
        if max_s is not None and m.seconds > max_s:
            failures.append(f"{m.name}: {m.seconds:.3f}s > {max_s:.3f}s")

    report = {
        "created_at": _utc_iso(),
        "repo_root": str(repo_root),
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "thresholds": thresholds,
        "measurements": [asdict(m) for m in measurements],
        "ok": not failures,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

