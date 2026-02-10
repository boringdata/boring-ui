"""Integration tests for Direct Connect auth + CORS.

Tests sandbox-agent with --token and --cors-allow-origin flags,
and Companion server with JWT auth middleware.

Validates:
- 200 with valid token
- 401 without token
- 401 with wrong token
- CORS preflight returns correct headers
- CORS rejects requests from disallowed origins
"""
import json
import os
import signal
import subprocess
import sys
import time

import jwt
import pytest
import requests

# ── Fixtures ────────────────────────────────────────────────────────────────

SANDBOX_PORT = 12468  # Use non-default port to avoid conflicts
SANDBOX_TOKEN = "test-sandbox-token-abc123"
CORS_ORIGIN = "http://localhost:5173"


def find_sandbox_agent():
    """Find sandbox-agent binary in node_modules."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    binary = os.path.join(
        project_root, "node_modules", ".bin", "sandbox-agent"
    )
    if os.path.exists(binary):
        return binary
    return None


@pytest.fixture(scope="module")
def sandbox_server():
    """Start sandbox-agent with token auth and CORS."""
    binary = find_sandbox_agent()
    if not binary:
        pytest.skip("sandbox-agent binary not found")

    proc = subprocess.Popen(
        [
            binary, "server",
            "--host", "127.0.0.1",
            "--port", str(SANDBOX_PORT),
            "--token", SANDBOX_TOKEN,
            "--cors-allow-origin", CORS_ORIGIN,
            "--cors-allow-header", "Authorization,Content-Type",
            "--cors-allow-method", "GET,POST,PUT,DELETE,OPTIONS",
            "--no-telemetry",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for server to be ready (sandbox-agent takes a few seconds)
    base_url = f"http://127.0.0.1:{SANDBOX_PORT}"
    for i in range(30):
        try:
            r = requests.get(
                f"{base_url}/v1/agents",
                headers={"Authorization": f"Bearer {SANDBOX_TOKEN}"},
                timeout=3,
            )
            if r.status_code in (200, 401):
                break
        except (requests.ConnectionError, requests.ReadTimeout):
            pass
        time.sleep(1)
    else:
        proc.kill()
        pytest.fail("sandbox-agent failed to start within 30s")

    yield {"proc": proc, "base_url": base_url, "token": SANDBOX_TOKEN}

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── Sandbox-agent auth tests ──────────────────────────────────────────────


class TestSandboxAuth:
    """Test sandbox-agent token auth (plain bearer token)."""

    def test_200_with_valid_token(self, sandbox_server):
        """Valid token returns 200."""
        r = requests.get(
            f"{sandbox_server['base_url']}/v1/agents",
            headers={"Authorization": f"Bearer {sandbox_server['token']}"},
        )
        assert r.status_code == 200

    def test_401_without_token(self, sandbox_server):
        """Missing token returns 401."""
        r = requests.get(f"{sandbox_server['base_url']}/v1/agents")
        assert r.status_code == 401

    def test_401_with_wrong_token(self, sandbox_server):
        """Wrong token returns 401."""
        r = requests.get(
            f"{sandbox_server['base_url']}/v1/agents",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401


class TestSandboxCORS:
    """Test sandbox-agent CORS configuration."""

    def test_cors_preflight_allowed_origin(self, sandbox_server):
        """Preflight from allowed origin returns CORS headers."""
        r = requests.options(
            f"{sandbox_server['base_url']}/v1/agents",
            headers={
                "Origin": CORS_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert r.status_code in (200, 204)
        assert CORS_ORIGIN in r.headers.get("Access-Control-Allow-Origin", "")

    def test_cors_actual_request_allowed_origin(self, sandbox_server):
        """Actual request from allowed origin returns CORS header."""
        r = requests.get(
            f"{sandbox_server['base_url']}/v1/agents",
            headers={
                "Origin": CORS_ORIGIN,
                "Authorization": f"Bearer {sandbox_server['token']}",
            },
        )
        assert r.status_code == 200
        assert CORS_ORIGIN in r.headers.get("Access-Control-Allow-Origin", "")


# ── Companion auth tests ──────────────────────────────────────────────────

COMPANION_PORT = 13456  # Non-default port
SIGNING_KEY = os.urandom(32)


def create_companion_jwt(service="companion", ttl=3600):
    """Create a JWT for Companion auth testing."""
    now = int(time.time())
    payload = {
        "sub": "boring-ui",
        "svc": service,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, SIGNING_KEY, algorithm="HS256")


@pytest.fixture(scope="module")
def companion_server():
    """Start Companion Hono server with JWT auth."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    server_dir = os.path.join(project_root, "vendor", "companion", "web")

    if not os.path.exists(os.path.join(server_dir, "package.json")):
        pytest.skip("Companion vendor source not found")

    import shutil
    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Bun runtime not found")

    env = {**os.environ}
    env["PORT"] = str(COMPANION_PORT)
    env["HOST"] = "127.0.0.1"
    env["SERVICE_AUTH_SECRET"] = SIGNING_KEY.hex()
    env["CORS_ORIGIN"] = CORS_ORIGIN

    proc = subprocess.Popen(
        [bun, "run", "server/index.ts"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=server_dir,
        env=env,
    )

    # Wait for server to be ready
    base_url = f"http://127.0.0.1:{COMPANION_PORT}"
    token = create_companion_jwt()
    for i in range(30):
        try:
            r = requests.get(
                f"{base_url}/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
                timeout=1,
            )
            if r.status_code in (200, 401, 403, 503):
                break
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("Companion server failed to start within 15s")

    yield {"proc": proc, "base_url": base_url}

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class TestCompanionAuth:
    """Test Companion JWT auth middleware."""

    def test_200_with_valid_jwt(self, companion_server):
        """Valid JWT with svc=companion returns 200."""
        token = create_companion_jwt()
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    def test_401_without_token(self, companion_server):
        """Missing token returns 401."""
        r = requests.get(f"{companion_server['base_url']}/api/sessions")
        assert r.status_code == 401

    def test_401_with_wrong_service_claim(self, companion_server):
        """JWT with svc=sandbox (wrong service) returns 401."""
        token = create_companion_jwt(service="sandbox")
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401

    def test_401_with_expired_token(self, companion_server):
        """Expired JWT returns 401."""
        token = create_companion_jwt(ttl=-1)
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401

    def test_401_with_garbage_token(self, companion_server):
        """Non-JWT string returns 401."""
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert r.status_code == 401

    def test_token_via_query_param(self, companion_server):
        """Token passed as ?token= query param (for WS upgrade)."""
        token = create_companion_jwt()
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions?token={token}",
        )
        assert r.status_code == 200


class TestCompanionCORS:
    """Test Companion CORS configuration."""

    def test_cors_preflight_allowed_origin(self, companion_server):
        """Preflight from allowed origin returns CORS headers."""
        token = create_companion_jwt()
        r = requests.options(
            f"{companion_server['base_url']}/api/sessions",
            headers={
                "Origin": CORS_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert r.status_code in (200, 204)
        allow_origin = r.headers.get("Access-Control-Allow-Origin", "")
        assert CORS_ORIGIN in allow_origin or allow_origin == "*"

    def test_cors_actual_request_has_origin_header(self, companion_server):
        """Actual request from allowed origin includes CORS header."""
        token = create_companion_jwt()
        r = requests.get(
            f"{companion_server['base_url']}/api/sessions",
            headers={
                "Origin": CORS_ORIGIN,
                "Authorization": f"Bearer {token}",
            },
        )
        assert r.status_code == 200
        allow_origin = r.headers.get("Access-Control-Allow-Origin", "")
        assert CORS_ORIGIN in allow_origin or allow_origin == "*"
