"""Unit tests for eval harness cleanup safety and idempotency.

Run with: python3 -m pytest tests/eval/tests/test_cleanup.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.eval.cleanup import _safe_delete_project, run_cleanup
from tests.eval.contracts import NamingContract, RunManifest


class StubFlyAdapter:
    def __init__(self, *, exists=True, delete_success=True):
        self.exists = exists
        self.delete_success = delete_success
        self.app_exists_calls: list[str] = []
        self.delete_calls: list[str] = []

    def app_exists(self, app_name: str) -> bool:
        self.app_exists_calls.append(app_name)
        return self.exists

    def delete_app(self, app_name: str) -> bool:
        self.delete_calls.append(app_name)
        return self.delete_success


class StubNeonAdapter:
    def __init__(self, *, destroy_success=True, error: Exception | None = None):
        self.destroy_success = destroy_success
        self.error = error
        self.destroy_calls: list[str] = []

    def destroy_project(self, project_id: str) -> bool:
        self.destroy_calls.append(project_id)
        if self.error is not None:
            raise self.error
        return self.destroy_success


def _make_manifest(tmp_path: Path) -> RunManifest:
    naming = NamingContract.from_eval_id(
        "child-eval-20260324T120000Z-abcd1234",
        projects_root=str(tmp_path),
    )
    manifest = RunManifest.from_naming(naming, platform_profile="core")
    Path(manifest.project_root).mkdir(parents=True, exist_ok=True)
    manifest.evidence_dir = str(tmp_path / ".eval-evidence" / manifest.app_slug)
    Path(manifest.evidence_dir).mkdir(parents=True, exist_ok=True)
    manifest.report_output_path = str(Path(manifest.evidence_dir) / "report.json")
    manifest.event_log_path = str(Path(manifest.evidence_dir) / "events.jsonl")
    return manifest


class TestSafeDeleteProject:
    def test_rejects_path_outside_projects_root_even_with_shared_prefix(self, tmp_path):
        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        evil_parent = tmp_path / "projects-evil"
        evil_parent.mkdir()
        evil_path = evil_parent / "ce-0324-abcd1234"
        evil_path.mkdir()

        success, error = _safe_delete_project(str(evil_path), str(projects_root))

        assert success is False
        assert "not under" in error

    def test_rejects_non_eval_prefix(self, tmp_path):
        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        bad_dir = projects_root / "plain-app"
        bad_dir.mkdir()

        success, error = _safe_delete_project(str(bad_dir), str(projects_root))

        assert success is False
        assert "does not match eval prefix" in error

    def test_rejects_symlink_project_root(self, tmp_path):
        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        target = tmp_path / "real-ce-0324-abcd1234"
        target.mkdir()
        symlink_path = projects_root / "ce-0324-abcd1234"
        symlink_path.symlink_to(target, target_is_directory=True)

        success, error = _safe_delete_project(str(symlink_path), str(projects_root))

        assert success is False
        assert "is a symlink" in error


class TestRunCleanup:
    def test_run_cleanup_is_idempotent(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        fly = StubFlyAdapter(exists=False)
        neon = StubNeonAdapter()

        first = run_cleanup(
            manifest,
            fly_adapter=fly,
            neon_adapter=neon,
            kill_local_processes=False,
        )
        assert first.completed is True
        assert Path(manifest.project_root).exists() is False

        second = run_cleanup(
            manifest,
            fly_adapter=fly,
            neon_adapter=neon,
            kill_local_processes=False,
        )

        directory_result = next(
            result for result in second.results if result.resource_type == "directory"
        )
        assert directory_result.success is True
        assert directory_result.error == "already deleted"

        manifest_path = Path(manifest.evidence_dir) / "cleanup_manifest.json"
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert saved["completed"] is True
        assert saved["total"] == len(second.results)

    def test_run_cleanup_continues_after_provider_failures_and_records_manifest(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        project_root = Path(manifest.project_root)
        boring_dir = project_root / ".boring"
        boring_dir.mkdir()
        (boring_dir / "neon-config.env").write_text(
            "NEON_PROJECT_ID=neon-test-123\n",
            encoding="utf-8",
        )

        fly = StubFlyAdapter(exists=True, delete_success=False)
        neon = StubNeonAdapter(destroy_success=False)

        cleanup = run_cleanup(
            manifest,
            fly_adapter=fly,
            neon_adapter=neon,
            kill_local_processes=False,
        )

        results = {result.resource_type: result for result in cleanup.results}
        assert results["fly_app"].success is False
        assert results["neon_project"].success is False
        assert results["directory"].success is True
        assert neon.destroy_calls == ["neon-test-123"]

        saved = json.loads(
            (Path(manifest.evidence_dir) / "cleanup_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert saved["failed"] == 2
        assert saved["succeeded"] == 1

    def test_run_cleanup_records_neon_exception_without_skipping_directory_cleanup(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        project_root = Path(manifest.project_root)
        boring_dir = project_root / ".boring"
        boring_dir.mkdir()
        (boring_dir / "neon-config.env").write_text(
            "NEON_PROJECT_ID=neon-test-123\n",
            encoding="utf-8",
        )

        fly = StubFlyAdapter(exists=False)
        neon = StubNeonAdapter(error=RuntimeError("neon api unavailable"))

        cleanup = run_cleanup(
            manifest,
            fly_adapter=fly,
            neon_adapter=neon,
            kill_local_processes=False,
        )

        results = {result.resource_type: result for result in cleanup.results}
        assert results["neon_project"].success is False
        assert "neon api unavailable" in results["neon_project"].error
        assert results["directory"].success is True
