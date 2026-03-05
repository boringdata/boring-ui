"""File operation smoke helpers."""
from __future__ import annotations

from .client import SmokeClient


def check_file_tree(client: SmokeClient, *, path: str = ".") -> dict:
    """GET /api/v1/files/list and return the response data."""
    client.set_phase("file-tree")
    resp = client.get(f"/api/v1/files/list", params={"path": path}, expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"File tree failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    print(f"[smoke] File tree at '{path}': {len(data.get('entries', data.get('files', [])))} entries")
    return data


def create_and_read_file(client: SmokeClient, *, path: str, content: str) -> dict:
    """PUT a file, then GET it back and assert content matches."""
    client.set_phase("create-file")
    write_resp = client.put(
        f"/api/v1/files/write",
        params={"path": path},
        json={"content": content},
        expect_status=(200,),
    )
    if write_resp.status_code != 200:
        raise RuntimeError(f"Write file failed: {write_resp.status_code} {write_resp.text[:300]}")

    client.set_phase("read-file")
    read_resp = client.get(
        f"/api/v1/files/read",
        params={"path": path},
        expect_status=(200,),
    )
    if read_resp.status_code != 200:
        raise RuntimeError(f"Read file failed: {read_resp.status_code} {read_resp.text[:300]}")
    data = read_resp.json()
    actual = data.get("content", "")
    if actual != content:
        raise RuntimeError(f"File content mismatch: expected {content!r}, got {actual!r}")
    print(f"[smoke] File '{path}' write+read OK")
    return data


def check_git_status(client: SmokeClient) -> dict:
    """GET /api/v1/git/status and return the response data."""
    client.set_phase("git-status")
    resp = client.get("/api/v1/git/status", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"Git status failed: {resp.status_code} {resp.text[:300]}")
    print("[smoke] Git status OK")
    return resp.json()
