"""Regression tests for bd-3g1g.7.7 (PTY stability without external claude binary)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from boring_ui.api import APIConfig, create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Test Project\n", encoding="utf-8")
    return tmp_path


def test_pty_missing_provider_command_sends_error_envelope(workspace: Path) -> None:
    # Simulate an environment where the "claude" CLI is not on PATH.
    config = APIConfig(
        workspace_root=workspace,
        pty_providers={
            "shell": ["bash"],
            "claude": ["definitely-not-a-real-command-binary"],
        },
    )
    app = create_app(config, include_stream=False, include_approval=False, include_pty=True)
    client = TestClient(app)

    with client.websocket_connect("/ws/pty?provider=claude") as ws:
        payload = ws.receive_json()

    assert payload["type"] == "error"
    err = payload.get("error") or {}
    assert err.get("type") == "spawn_failed"
    assert "command not found" in str(err.get("reason", "")).lower()
