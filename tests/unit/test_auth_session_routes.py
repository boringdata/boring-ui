"""Unit tests for /auth/* session lifecycle routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from boring_ui.api import APIConfig, create_app
from boring_ui.api.modules.control_plane.auth_session import create_session_cookie


def _client(tmp_path: Path, *, auth_dev_login_enabled: bool = True) -> TestClient:
    config = APIConfig(workspace_root=tmp_path, auth_dev_login_enabled=auth_dev_login_enabled)
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    return TestClient(app)


def test_auth_login_requires_identity_params(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "LOGIN_IDENTITY_REQUIRED"
    assert payload["error"] == "bad_request"


def test_auth_login_disabled_by_default(tmp_path: Path) -> None:
    client = _client(tmp_path, auth_dev_login_enabled=False)
    response = client.get(
        "/auth/login?user_id=user-1&email=owner@example.com&redirect_uri=/",
        follow_redirects=False,
    )
    assert response.status_code == 501
    assert response.json()["code"] == "LOGIN_NOT_CONFIGURED"


def test_auth_login_sets_session_cookie_and_redirects(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get(
        "/auth/login?user_id=user-1&email=owner@example.com&redirect_uri=/w/workspace-1",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/w/workspace-1"
    assert "boring_session=" in response.headers.get("set-cookie", "")
    assert "HttpOnly" in response.headers.get("set-cookie", "")

    session = client.get("/auth/session")
    assert session.status_code == 200
    payload = session.json()
    assert payload["authenticated"] is True
    assert payload["user"]["user_id"] == "user-1"
    assert payload["user"]["email"] == "owner@example.com"


def test_auth_callback_sets_cookie_and_session(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get(
        "/auth/callback?user_id=user-2&email=viewer@example.com&redirect_uri=/",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "boring_session=" in response.headers.get("set-cookie", "")

    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["user_id"] == "user-2"


def test_auth_session_returns_401_without_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/auth/session")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_auth_session_returns_401_for_invalid_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/auth/session", headers={"Cookie": "boring_session=invalid.token"})
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_INVALID"


def test_auth_session_returns_401_for_expired_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    expired_token = create_session_cookie(
        "user-expired",
        "expired@example.com",
        secret=client.app.state.app_config.auth_session_secret,
        ttl_seconds=-1,
    )
    response = client.get("/auth/session", headers={"Cookie": f"boring_session={expired_token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_EXPIRED"


def test_auth_login_sanitizes_encoded_redirects(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get(
        "/auth/login?user_id=user-9&email=redirect@example.com&redirect_uri=/%2F%2Fevil.com",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_auth_logout_clears_cookie_and_session(tmp_path: Path) -> None:
    client = _client(tmp_path)
    login = client.get(
        "/auth/login?user_id=user-3&email=logout@example.com&redirect_uri=/",
        follow_redirects=False,
    )
    assert login.status_code == 302

    logout = client.get("/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["status"] == "logged_out"
    assert "Max-Age=0" in logout.headers.get("set-cookie", "")

    session = client.get("/auth/session")
    assert session.status_code == 401
    assert session.json()["code"] == "SESSION_REQUIRED"
