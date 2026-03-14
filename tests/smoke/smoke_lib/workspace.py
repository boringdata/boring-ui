"""Workspace lifecycle smoke helpers."""
from __future__ import annotations

import time

from .client import SmokeClient


def create_workspace(client: SmokeClient, *, name: str) -> dict:
    """Create a workspace and return its payload."""
    client.set_phase("create-workspace")
    print(f"[smoke] Creating workspace '{name}'...")
    resp = client.post(
        "/api/v1/workspaces",
        json={"name": name},
        expect_status=(200, 201),
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Create workspace failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    ws = data.get("workspace") or data
    workspace_id = ws.get("workspace_id") or ws.get("id")
    if not workspace_id:
        raise RuntimeError(f"No workspace_id in response: {data}")
    print(f"[smoke] Workspace created: {workspace_id}")
    return data


def list_workspaces(client: SmokeClient, *, expect_id: str | None = None) -> list[dict]:
    """List workspaces. Optionally assert a specific workspace_id is present."""
    client.set_phase("list-workspaces")
    resp = client.get("/api/v1/workspaces", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"List workspaces failed: {resp.status_code}")
    data = resp.json()
    workspaces = data.get("workspaces", [])
    if expect_id:
        ids = {(w.get("workspace_id") or w.get("id") or "") for w in workspaces}
        if expect_id not in ids:
            raise RuntimeError(f"Workspace {expect_id} not in list: {ids}")
    print(f"[smoke] Listed {len(workspaces)} workspace(s)")
    return workspaces


def get_runtime(client: SmokeClient, workspace_id: str) -> dict:
    """Get workspace runtime state."""
    client.set_phase("workspace-runtime-get")
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/runtime",
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Get runtime failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()


def retry_runtime(client: SmokeClient, workspace_id: str) -> dict:
    """Attempt runtime retry (may 409 if not in error/provisioning state)."""
    client.set_phase("workspace-runtime-retry")
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/runtime/retry",
    )
    return {"status_code": resp.status_code, **resp.json()}


def get_workspace_setup(client: SmokeClient, workspace_id: str) -> dict:
    """Get workspace setup route payload.

    This route may resolve to:
    - JSON from the backend boundary router
    - HTML from the frontend setup page in app/dev-server mode
    """
    client.set_phase("workspace-setup-get")
    resp = client.get(
        f"/w/{workspace_id}/setup",
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Workspace setup failed: {resp.status_code} {resp.text[:300]}")
    content_type = str(resp.headers.get("content-type", "")).lower()
    if "application/json" in content_type:
        data = resp.json()
        data["_content_type"] = content_type
        data["_response_kind"] = "json"
        return data
    return {
        "_content_type": content_type,
        "_response_kind": "html",
        "ok": True,
        "workspace_id": workspace_id,
    }


def get_workspace_boundary_runtime(client: SmokeClient, workspace_id: str) -> dict:
    """Get workspace runtime through the boundary path."""
    client.set_phase("workspace-boundary-runtime-get")
    resp = client.get(
        f"/w/{workspace_id}/runtime",
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Workspace boundary runtime failed: {resp.status_code} {resp.text[:300]}")
    content_type = resp.headers.get("content-type", "")
    if "json" not in content_type:
        # Core mode serves SPA HTML for boundary paths — not an API endpoint
        return {}
    return resp.json()


def check_workspace_root(client: SmokeClient, workspace_id: str) -> None:
    """Verify the workspace root boundary is reachable."""
    client.set_phase("workspace-root-get")
    resp = client.get(
        f"/w/{workspace_id}/",
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Workspace root failed: {resp.status_code} {resp.text[:300]}")
    print(f"[smoke] Workspace root OK: {workspace_id}")


def poll_runtime_ready(
    client: SmokeClient,
    workspace_id: str,
    *,
    timeout_seconds: int = 120,
    poll_interval: float = 3.0,
) -> dict:
    """Poll runtime until state=ready or error/timeout."""
    client.set_phase("poll-runtime")
    deadline = time.monotonic() + timeout_seconds
    last_state = ""
    while time.monotonic() < deadline:
        data = get_runtime(client, workspace_id)
        runtime = data.get("runtime", {})
        state = runtime.get("state", "")
        if state != last_state:
            step = runtime.get("provisioning_step", "")
            print(f"[smoke] Runtime state: {state}" + (f" ({step})" if step else ""))
            last_state = state
        if state == "ready":
            return runtime
        if state == "error":
            raise RuntimeError(f"Runtime entered error state: {runtime.get('last_error')}")
        time.sleep(poll_interval)
    raise RuntimeError(f"Runtime did not reach ready within {timeout_seconds}s (last: {last_state})")
