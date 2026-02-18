"""Guards for bd-3g1g.6.3 agent-pi runtime-only surface.

PI is allowed to own its session/history/stream lifecycle endpoints, but must not
expose direct workspace-core or PTY ownership endpoints.

This is intentionally behavior-level (HTTP probes against a real PI server process)
to avoid brittle source-text scanning.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _pick_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def _node_binary() -> str:
    # Prefer system Node; repo docs use /usr/bin/node explicitly.
    for candidate in ("/usr/bin/node", shutil.which("node")):
        if candidate and Path(candidate).exists():
            return candidate
    pytest.skip("node is required to run PI service surface test")


def _http_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:  # nosec - localhost-only in tests
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return int(resp.status), json.loads(body or "{}")
            except json.JSONDecodeError:
                return int(resp.status), {"_raw": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(body or "{}")
        except json.JSONDecodeError:
            return int(exc.code), {"_raw": body}


def _wait_for_health(base_url: str, proc: subprocess.Popen, log_path: Path) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            log = log_path.read_text(encoding="utf-8", errors="replace")
            raise AssertionError(f"PI service exited before becoming healthy.\n\n{log}")
        status = 0
        payload: dict = {}
        try:
            status, payload = _http_json("GET", f"{base_url}/health")
        except Exception:
            status, payload = 0, {}
        if status == 200 and payload.get("service") == "pi-service":
            return
        time.sleep(0.1)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    raise AssertionError(f"PI service did not become healthy in time.\n\n{log}")


def _start_pi_service(repo_root: Path, *, max_attempts: int = 5) -> tuple[subprocess.Popen, str, Path]:
    server_path = repo_root / "src/pi_service/server.mjs"
    assert server_path.exists()

    env = os.environ.copy()
    # Satisfy server startup gate; value does not need to be valid for route probes.
    env["ANTHROPIC_API_KEY"] = "test"
    env["PI_SERVICE_HOST"] = "127.0.0.1"

    last_error = ""
    for attempt in range(1, max_attempts + 1):
        port = _pick_free_port()
        base = f"http://127.0.0.1:{port}"
        env["PI_SERVICE_PORT"] = str(port)

        tmpdir = Path(tempfile.mkdtemp(prefix="pi-service-test-"))
        log_path = tmpdir / "pi_service.log"
        log = log_path.open("w", encoding="utf-8")

        proc = subprocess.Popen(  # noqa: S603 - test-only local subprocess
            [_node_binary(), str(server_path)],
            cwd=str(repo_root),
            env=env,
            stdout=log,
            stderr=log,
        )
        log.close()

        try:
            _wait_for_health(base, proc, log_path)
            return proc, base, tmpdir
        except Exception as exc:
            last_error = f"attempt={attempt}: {exc}"
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=2)
            with contextlib.suppress(Exception):
                proc.kill()
            with contextlib.suppress(Exception):
                shutil.rmtree(tmpdir, ignore_errors=True)
            continue

    raise AssertionError(f"PI service failed to start after {max_attempts} attempts. {last_error}")


def test_pi_service_surface_is_canonical_and_runtime_only() -> None:
    repo_root = _repo_root()
    proc, base, tmpdir_path = _start_pi_service(repo_root)
    log_path = tmpdir_path / "pi_service.log"
    try:
        # Canonical PI runtime family must be reachable.
        status, payload = _http_json("GET", f"{base}/api/v1/agent/pi/sessions")
        assert status == 200, payload

        status, payload = _http_json("POST", f"{base}/api/v1/agent/pi/sessions/create", payload={})
        assert status == 201, payload
        session_id = payload.get("session", {}).get("id")
        assert isinstance(session_id, str) and session_id

        status, payload = _http_json("GET", f"{base}/api/v1/agent/pi/sessions/{session_id}/history")
        assert status == 200, payload

        status, payload = _http_json("POST", f"{base}/api/v1/agent/pi/sessions/{session_id}/stop", payload={})
        assert status == 200, payload

        # Legacy PI family must not be reachable after cutover.
        status, _ = _http_json("GET", f"{base}/api/sessions")
        assert status == 404
        status, _ = _http_json("POST", f"{base}/api/sessions/create", payload={})
        assert status == 404

        # Agent services must not directly own workspace-core or PTY surfaces.
        forbidden_paths = [
            "/api/v1/files",
            "/api/v1/git",
            "/api/v1/pty/sessions",
            "/ws/pty",
            "/api/fs",
            "/api/git",
            "/api/envs",
        ]
        for path in forbidden_paths:
            status, _ = _http_json("GET", f"{base}{path}")
            assert status == 404, f"unexpected GET status={status} for {path}"
            status, _ = _http_json("POST", f"{base}{path}", payload={})
            assert status == 404, f"unexpected POST status={status} for {path}"
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=3)
        if proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.kill()
                proc.wait(timeout=3)
        with contextlib.suppress(Exception):
            shutil.rmtree(tmpdir_path, ignore_errors=True)
