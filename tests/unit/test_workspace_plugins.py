from pathlib import Path

from boring_ui.api.workspace_plugins import WorkspacePluginManager


def _write_plugin(workspace_root: Path, name: str) -> None:
    api_dir = workspace_root / "kurt" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / f"{name}.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n",
        encoding="utf-8",
    )


def test_workspace_plugin_allowlist_none_allows_all(tmp_path):
    _write_plugin(tmp_path, "alpha")
    _write_plugin(tmp_path, "beta")

    manager = WorkspacePluginManager(tmp_path, allowed_plugins=None)
    routes = manager.list_workspace_routes()

    assert {r["name"] for r in routes} == {"alpha", "beta"}


def test_workspace_plugin_allowlist_empty_set_blocks_all(tmp_path):
    _write_plugin(tmp_path, "alpha")

    manager = WorkspacePluginManager(tmp_path, allowed_plugins=set())
    routes = manager.list_workspace_routes()

    assert routes == []
