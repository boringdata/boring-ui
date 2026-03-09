"""Settings smoke helpers — user settings and workspace settings CRUD."""
from __future__ import annotations

from .client import SmokeClient


def get_user_settings(client: SmokeClient) -> dict:
    """GET /api/v1/me/settings — read user settings."""
    client.set_phase("user-settings-get")
    print("[smoke] Getting user settings...")
    resp = client.get("/api/v1/me/settings", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"Get user settings failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print(f"[smoke] User settings OK: {list(data.get('settings', {}).keys())}")
    return data


def update_user_settings(client: SmokeClient, *, display_name: str) -> dict:
    """PUT /api/v1/me/settings — update user settings."""
    client.set_phase("user-settings-update")
    print(f"[smoke] Updating user display_name to '{display_name}'...")
    resp = client.put(
        "/api/v1/me/settings",
        json={"display_name": display_name},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Update user settings failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print("[smoke] User settings updated OK")
    return data


def verify_user_settings(client: SmokeClient, *, expected_display_name: str) -> None:
    """Read-back verification: GET settings and assert display_name matches."""
    client.set_phase("user-settings-verify")
    print(f"[smoke] Verifying user display_name = '{expected_display_name}'...")
    resp = client.get("/api/v1/me/settings", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"Verify user settings failed: {resp.status_code}")
    settings = resp.json().get("settings", {})
    actual = settings.get("display_name", "")
    if actual != expected_display_name:
        raise RuntimeError(
            f"User display_name mismatch: expected={expected_display_name!r}, actual={actual!r}"
        )
    print("[smoke] User settings verification OK")


def get_workspace_settings(client: SmokeClient, workspace_id: str) -> dict:
    """GET /api/v1/workspaces/{id}/settings — read workspace settings."""
    client.set_phase("workspace-settings-get")
    print(f"[smoke] Getting workspace settings for {workspace_id[:8]}...")
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/settings",
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Get workspace settings failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print(f"[smoke] Workspace settings OK: {list(data.get('settings', {}).keys())}")
    return data


def update_workspace_settings(client: SmokeClient, workspace_id: str, *, settings: dict) -> dict:
    """PUT /api/v1/workspaces/{id}/settings — update workspace settings."""
    client.set_phase("workspace-settings-update")
    keys = list(settings.keys())
    print(f"[smoke] Updating workspace settings for {workspace_id[:8]}: {keys}")
    resp = client.put(
        f"/api/v1/workspaces/{workspace_id}/settings",
        json=settings,
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Update workspace settings failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print("[smoke] Workspace settings updated OK")
    return data


def rename_workspace(client: SmokeClient, workspace_id: str, *, name: str) -> dict:
    """PATCH /api/v1/workspaces/{id} — rename workspace."""
    client.set_phase("workspace-rename")
    print(f"[smoke] Renaming workspace {workspace_id[:8]} to '{name}'...")
    resp = client.request(
        "PATCH",
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": name},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Rename workspace failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print("[smoke] Workspace renamed OK")
    return data


def verify_workspace_name(client: SmokeClient, workspace_id: str, *, expected_name: str) -> None:
    """Read-back verification: list workspaces and assert name matches."""
    client.set_phase("workspace-name-verify")
    print(f"[smoke] Verifying workspace name = '{expected_name}'...")
    resp = client.get("/api/v1/workspaces", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"List workspaces for verify failed: {resp.status_code}")
    workspaces = resp.json().get("workspaces", [])
    ws = next((w for w in workspaces if (w.get("id") or w.get("workspace_id")) == workspace_id), None)
    if ws is None:
        raise RuntimeError(f"Workspace {workspace_id} not found in list")
    actual = ws.get("name", "")
    if actual != expected_name:
        raise RuntimeError(f"Workspace name mismatch: expected={expected_name!r}, actual={actual!r}")
    print("[smoke] Workspace name verification OK")
