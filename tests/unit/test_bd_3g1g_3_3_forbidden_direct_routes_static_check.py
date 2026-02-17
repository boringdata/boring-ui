from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_forbidden_direct_routes.py"


def _run_guard(*args: str, root: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=root or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_guard_passes_for_current_repo_feature_code() -> None:
    result = _run_guard("--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["violation_count"] == 0


def test_guard_reports_legacy_and_workspace_literal_violations(tmp_path: Path) -> None:
    bad_file = tmp_path / "src/front/components/BadFeature.jsx"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text(
        "\n".join(
            [
                "const legacy = '/api/tree'",
                "const wsLegacy = '/ws/stream/session'",
                "const workspace = `/w/${workspaceId}/setup`",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_guard("--root", str(tmp_path), "--format", "json")
    assert result.returncode == 1, result.stdout + result.stderr

    payload = json.loads(result.stdout)
    assert payload["violation_count"] >= 3

    rules = {item["rule"] for item in payload["violations"]}
    assert "legacy-compat-route" in rules
    assert "workspace-proxy-literal" in rules

    sample = payload["violations"][0]
    assert sample["path"].endswith("src/front/components/BadFeature.jsx")
    assert isinstance(sample["line"], int)
    assert sample["snippet"]
    assert sample["message"]


def test_guard_skips_allowlisted_route_modules(tmp_path: Path) -> None:
    allowed_file = tmp_path / "src/front/utils/controlPlane.js"
    allowed_file.parent.mkdir(parents=True, exist_ok=True)
    allowed_file.write_text(
        "\n".join(
            [
                "export const getMePath = () => '/api/v1/me'",
                "export const getWorkspacePath = (workspaceId) => `/w/${workspaceId}/setup`",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_guard("--root", str(tmp_path), "--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["violation_count"] == 0


def test_guard_ignores_route_lookalike_strings(tmp_path: Path) -> None:
    file_path = tmp_path / "src/front/components/LooksSimilar.jsx"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "\n".join(
            [
                "const a = '/api/treehouse'",
                "const b = '/api/gitops'",
                "const c = '/api/v1/agents'",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_guard("--root", str(tmp_path), "--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["violation_count"] == 0


def test_guard_catches_query_or_hash_terminated_forbidden_routes(tmp_path: Path) -> None:
    file_path = tmp_path / "src/front/components/WithQueryHash.jsx"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "\n".join(
            [
                "const a = '/api/file?path=abc'",
                "const b = '/api/v1/git#status'",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_guard("--root", str(tmp_path), "--format", "json")
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    rules = {item["rule"] for item in payload["violations"]}
    assert "legacy-compat-route" in rules
    assert "direct-internal-service-route" in rules


def test_guard_scans_generator_method_lines(tmp_path: Path) -> None:
    file_path = tmp_path / "src/front/components/GeneratorStyle.jsx"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "\n".join(
            [
                "const obj = {",
                "  *gen() { return '/api/tree' }",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_guard("--root", str(tmp_path), "--format", "json")
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["violation_count"] >= 1
