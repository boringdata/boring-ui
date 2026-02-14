from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_bundle(tmp_path: Path, *, release_id: str = "test-build", app_id: str = "boring-ui") -> Path:
    """Run build_release_bundle.sh with a fake frontend dist and return out_dir."""
    repo_root = _repo_root()
    build_script = repo_root / "src/app/scripts/build_release_bundle.sh"
    assert build_script.exists()

    fake_dist = tmp_path / "fake_dist"
    fake_dist.mkdir(exist_ok=True)
    (fake_dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    out_dir = tmp_path / "out"
    env = dict(os.environ)
    env["FRONTEND_DIST_DIR"] = str(fake_dist)

    p = _run(
        [
            "bash", str(build_script),
            "--release-id", release_id,
            "--app-id", app_id,
            "--out-dir", str(out_dir),
            "--skip-frontend",
        ],
        cwd=repo_root,
        env=env,
    )
    assert p.returncode == 0, p.stdout
    return out_dir


def _bundle_names(bundle_path: Path) -> set[str]:
    """Return normalized entry names from a bundle tarball."""
    with tarfile.open(bundle_path, "r:gz") as tf:
        return {
            n[2:] if n.startswith("./") else n
            for n in tf.getnames()
            if n not in (".", "./")
        }


# ── Bootstrap script tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_bootstrap_exits_non_zero_on_missing_bundle(tmp_path: Path):
    script = _repo_root() / "src/app/deploy/sprite/bootstrap.sh"
    assert script.exists()

    p = _run(["bash", str(script)], cwd=tmp_path)
    assert p.returncode != 0
    assert "bundle.tar.gz not found" in p.stdout


def test_build_bundle_includes_bootstrap_and_runtime_env_example(tmp_path: Path):
    out_dir = _build_bundle(tmp_path)
    bundle = out_dir / "bundle.tar.gz"
    names = _bundle_names(bundle)

    assert "deploy/sprite/bootstrap.sh" in names
    assert "deploy/sprite/runtime.env.example" in names

    with tarfile.open(bundle, "r:gz") as tf:
        try:
            tf.extract("./deploy/sprite/bootstrap.sh", path=tmp_path, filter="fully_trusted")  # noqa: S202
        except TypeError:
            tf.extract("./deploy/sprite/bootstrap.sh", path=tmp_path)  # noqa: S202
        extracted = tmp_path / "deploy/sprite/bootstrap.sh"
        assert extracted.exists()
        assert os.access(extracted, os.X_OK)


# ── Bundle contents tests ───────────────────────────────────────


def test_bundle_contains_dist_and_wheel(tmp_path: Path):
    out_dir = _build_bundle(tmp_path)
    names = _bundle_names(out_dir / "bundle.tar.gz")

    assert any(n.startswith("dist/") for n in names), f"No dist/ entries in bundle: {names}"
    assert any(n.startswith("boring_ui-") and n.endswith(".whl") for n in names), (
        f"No boring_ui-*.whl in bundle: {names}"
    )


def test_bundle_excludes_hidden_dirs(tmp_path: Path):
    """Stale hidden dirs (.wheels/, .bundle_staging/) must not leak into bundle."""
    # Plant hidden dirs in the fake dist to simulate stale artifacts.
    fake_dist = tmp_path / "fake_dist"
    fake_dist.mkdir(exist_ok=True)
    (fake_dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    stale_dir = fake_dist / ".bundle_staging"
    stale_dir.mkdir()
    (stale_dir / "junk.txt").write_text("stale", encoding="utf-8")
    wheels_dir = fake_dist / ".wheels"
    wheels_dir.mkdir()
    (wheels_dir / "old.whl").write_text("stale", encoding="utf-8")

    out_dir = tmp_path / "out"
    env = dict(os.environ)
    env["FRONTEND_DIST_DIR"] = str(fake_dist)

    p = _run(
        [
            "bash", str(_repo_root() / "src/app/scripts/build_release_bundle.sh"),
            "--release-id", "test-hidden",
            "--out-dir", str(out_dir),
            "--skip-frontend",
        ],
        cwd=_repo_root(),
        env=env,
    )
    assert p.returncode == 0, p.stdout

    names = _bundle_names(out_dir / "bundle.tar.gz")
    hidden = [n for n in names if "/." in n or n.startswith(".")]
    assert not hidden, f"Hidden dirs leaked into bundle: {hidden}"


# ── Manifest tests ──────────────────────────────────────────────


def test_manifest_has_required_fields(tmp_path: Path):
    out_dir = _build_bundle(tmp_path, release_id="test-manifest")
    manifest = json.loads((out_dir / "manifest.json").read_text())

    for field in ("app_id", "release_id", "bundle_sha256", "created_at", "git_sha", "files", "bundle_contents"):
        assert field in manifest, f"Missing manifest field: {field}"

    assert manifest["app_id"] == "boring-ui"
    assert manifest["release_id"] == "test-manifest"
    assert isinstance(manifest["files"], list)
    assert "bundle.tar.gz" in manifest["files"]
    assert "manifest.json" in manifest["files"]
    assert isinstance(manifest["bundle_contents"], list)


def test_release_id_flag_sets_manifest_release_id(tmp_path: Path):
    out_dir = _build_bundle(tmp_path, release_id="my-custom-release-42")
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["release_id"] == "my-custom-release-42"


def test_app_id_flag_sets_manifest_app_id(tmp_path: Path):
    out_dir = _build_bundle(tmp_path, app_id="my-other-app")
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["app_id"] == "my-other-app"


# ── SHA256 checksum tests ───────────────────────────────────────


def test_sha256_file_matches_bundle(tmp_path: Path):
    out_dir = _build_bundle(tmp_path)
    bundle_path = out_dir / "bundle.tar.gz"
    sha_path = out_dir / "bundle.tar.gz.sha256"
    assert sha_path.exists()

    # Compute actual SHA256.
    actual_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()

    # Parse SHA from checksum file.
    sha_line = sha_path.read_text().strip()
    file_sha = sha_line.split()[0]

    assert file_sha == actual_sha


def test_manifest_sha256_matches_bundle(tmp_path: Path):
    out_dir = _build_bundle(tmp_path)
    bundle_path = out_dir / "bundle.tar.gz"
    manifest = json.loads((out_dir / "manifest.json").read_text())

    actual_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    assert manifest["bundle_sha256"] == actual_sha
