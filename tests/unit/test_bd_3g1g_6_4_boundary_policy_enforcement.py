"""Boundary policy enforcement tests for bd-3g1g.6.4.

These tests assert deny-by-default behavior for delegated requests when the
`X-Scope-Context` claim envelope is malformed or insufficient.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from boring_ui.api import APIConfig, create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Test Project\n", encoding="utf-8")
    return tmp_path


def _scope_headers(
    *,
    claims: list[str],
    request_id: str = "req_test_1",
    workspace_id: str = "ws_test_1",
    cwd_or_worktree: str = ".",
    session_id: str | None = None,
) -> dict[str, str]:
    payload: dict[str, object] = {
        "request_id": request_id,
        "workspace_id": workspace_id,
        "actor": {"user_id": "u_test", "service": "agent-normal", "role": "runtime"},
        "capability_claims": claims,
        "cwd_or_worktree": cwd_or_worktree,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return {"X-Scope-Context": json.dumps(payload)}


def _assert_error_envelope(data: dict, expected_code: str) -> None:
    assert data["code"] == expected_code
    assert isinstance(data["message"], str) and data["message"]
    assert data["retryable"] is False
    details = data.get("details")
    assert isinstance(details, dict)
    assert "request_id" in details
    assert "workspace_id" in details


def test_files_invalid_scope_context_header_is_400_envelope(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)

    resp = client.get(
        "/api/v1/files/list",
        params={"path": "."},
        headers={"X-Scope-Context": "{not-json]"},
    )
    assert resp.status_code == 400
    _assert_error_envelope(resp.json(), "invalid_scope_context")


def test_files_write_denied_without_write_claim_and_no_side_effects(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)

    target = workspace / "new.txt"
    assert not target.exists()

    resp = client.put(
        "/api/v1/files/write",
        params={"path": "new.txt"},
        headers=_scope_headers(claims=["workspace.files.read"]),
        json={"content": "nope"},
    )
    assert resp.status_code == 403
    _assert_error_envelope(resp.json(), "capability_denied")
    assert not target.exists(), "Denied delegated write must not create files"


def test_git_status_denied_without_git_read_claim(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)

    resp = client.get(
        "/api/v1/git/status",
        headers=_scope_headers(claims=["workspace.files.read"]),
    )
    assert resp.status_code == 403
    _assert_error_envelope(resp.json(), "capability_denied")


def test_pty_lifecycle_create_denied_without_start_claim(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_stream=False,
        include_approval=False,
        include_pty=True,
    )
    client = TestClient(app)

    resp = client.post(
        "/api/v1/pty/sessions",
        headers=_scope_headers(claims=["pty.session.attach"]),
    )
    assert resp.status_code == 403
    _assert_error_envelope(resp.json(), "capability_denied")


def test_pty_ws_attach_denied_without_attach_claim(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_stream=False,
        include_approval=False,
        include_pty=True,
    )
    client = TestClient(app)

    sess = str(uuid.uuid4())
    headers = _scope_headers(claims=["pty.session.start"], session_id=sess)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/pty?provider=shell&session_id={sess}", headers=headers) as ws:
            ws.receive_text()

    assert excinfo.value.code == 4004


def test_pty_ws_session_mismatch_is_denied(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_stream=False,
        include_approval=False,
        include_pty=True,
    )
    client = TestClient(app)

    sess = str(uuid.uuid4())
    other = str(uuid.uuid4())
    headers = _scope_headers(claims=["pty.session.attach"], session_id=other)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/pty?provider=shell&session_id={sess}", headers=headers) as ws:
            ws.receive_text()

    assert excinfo.value.code == 4004

