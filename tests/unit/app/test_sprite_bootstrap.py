from __future__ import annotations

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


@pytest.mark.asyncio
async def test_bootstrap_exits_non_zero_on_missing_bundle(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "src/app/deploy/sprite/bootstrap.sh"
    assert script.exists()

    p = _run(["bash", str(script)], cwd=tmp_path)
    assert p.returncode != 0
    assert "bundle.tar.gz not found" in p.stdout


def test_build_bundle_includes_bootstrap_and_runtime_env_example(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    build_script = repo_root / "src/app/scripts/build_release_bundle.sh"
    assert build_script.exists()

    # Use a fake frontend dist dir to avoid running npm in this test.
    fake_dist = tmp_path / "fake_dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    out_dir = tmp_path / "out"
    env = dict(os.environ)
    env["FRONTEND_DIST_DIR"] = str(fake_dist)

    p = _run(
        ["bash", str(build_script), "--release-id", "test-boot0", "--app-id", "boring-ui", "--out-dir", str(out_dir), "--skip-frontend"],
        cwd=repo_root,
        env=env,
    )
    assert p.returncode == 0, p.stdout

    bundle = out_dir / "bundle.tar.gz"
    assert bundle.exists()

    with tarfile.open(bundle, "r:gz") as tf:
        names = set(
            n[2:] if n.startswith("./") else n
            for n in tf.getnames()
            if n not in (".", "./")
        )
        assert "deploy/sprite/bootstrap.sh" in names
        assert "deploy/sprite/runtime.env.example" in names

        try:
            tf.extract("./deploy/sprite/bootstrap.sh", path=tmp_path, filter="fully_trusted")  # noqa: S202
        except TypeError:
            # Older Python tarfile API (no filter= kwarg).
            tf.extract("./deploy/sprite/bootstrap.sh", path=tmp_path)  # noqa: S202
        extracted = tmp_path / "deploy/sprite/bootstrap.sh"
        assert extracted.exists()
        assert os.access(extracted, os.X_OK)
