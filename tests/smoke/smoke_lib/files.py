"""File operation smoke helpers."""
from __future__ import annotations

import time

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


def rename_file(client: SmokeClient, *, old_path: str, new_path: str) -> dict:
    """Rename a file and verify the old path disappears."""
    client.set_phase("rename-file")
    resp = client.post(
        "/api/v1/files/rename",
        json={"old_path": old_path, "new_path": new_path},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Rename file failed: {resp.status_code} {resp.text[:300]}")

    client.set_phase("verify-renamed-file")
    missing_resp = client.get(
        "/api/v1/files/read",
        params={"path": old_path},
        expect_status=(404,),
    )
    if missing_resp.status_code != 404:
        raise RuntimeError(f"Old file still readable after rename: {old_path}")

    read_resp = client.get(
        "/api/v1/files/read",
        params={"path": new_path},
        expect_status=(200,),
    )
    if read_resp.status_code != 200:
        raise RuntimeError(f"Renamed file not readable: {new_path}")
    print(f"[smoke] Rename OK: {old_path} -> {new_path}")
    return read_resp.json()


def delete_file(client: SmokeClient, *, path: str) -> None:
    """Delete a file and verify it is gone."""
    client.set_phase("delete-file")
    resp = client.delete(
        "/api/v1/files/delete",
        params={"path": path},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Delete file failed: {resp.status_code} {resp.text[:300]}")

    client.set_phase("verify-deleted-file")
    verify_resp = client.get(
        "/api/v1/files/read",
        params={"path": path},
        expect_status=(404,),
    )
    if verify_resp.status_code != 404:
        raise RuntimeError(f"Deleted file still readable: {path}")
    print(f"[smoke] Delete OK: {path}")


def search_files(client: SmokeClient, *, pattern: str, path: str = ".") -> list[dict]:
    """Search for files and return results."""
    client.set_phase("search-files")
    resp = client.get(
        "/api/v1/files/search",
        params={"q": pattern, "path": path},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Search files failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    results = data.get("results", [])
    print(f"[smoke] Search '{pattern}' returned {len(results)} result(s)")
    return results


def full_file_cycle(client: SmokeClient, *, prefix: str = "smoke-fs", include_search: bool = False) -> dict:
    """Run a simple create/read/rename/delete file cycle.

    Search is optional because it is a broader surface than core CRUD and may
    be excluded from deploy-level smoke gates.
    """
    ts = int(time.time())
    original_path = f"{prefix}-{ts}.txt"
    renamed_path = f"{prefix}-{ts}-renamed.txt"
    content = f"{prefix}-{ts}"

    check_file_tree(client)
    create_and_read_file(client, path=original_path, content=content)
    if include_search:
        results = search_files(client, pattern=f"{prefix}-{ts}*")
        if not any(item.get("path") == original_path for item in results):
            raise RuntimeError(f"Search did not find {original_path}")
    rename_file(client, old_path=original_path, new_path=renamed_path)
    if include_search:
        results_after = search_files(client, pattern=f"{prefix}-{ts}*")
        if not any(item.get("path") == renamed_path for item in results_after):
            raise RuntimeError(f"Search did not find renamed file {renamed_path}")
    delete_file(client, path=renamed_path)
    return {"original_path": original_path, "renamed_path": renamed_path}


def check_git_status(client: SmokeClient) -> dict:
    """GET /api/v1/git/status and return the response data."""
    client.set_phase("git-status")
    resp = client.get("/api/v1/git/status", expect_status=(200,))
    if resp.status_code != 200:
        raise RuntimeError(f"Git status failed: {resp.status_code} {resp.text[:300]}")
    print("[smoke] Git status OK")
    return resp.json()
