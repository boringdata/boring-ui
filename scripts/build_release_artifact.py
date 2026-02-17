#!/usr/bin/env python3
"""Build and publish a release artifact bundle for boring-ui.

Bead: bd-223o.1 (P1)

Creates the canonical release layout::

    {store_root}/{app_id}/{release_id}/
        bundle.tar.gz
        manifest.json
        SHA256SUMS

Usage::

    python scripts/build_release_artifact.py --app-id boring-ui --release-id v0.1.0
    python scripts/build_release_artifact.py --app-id boring-ui --release-id v0.1.0 \
        --store-root /data/releases

The bundle includes the built frontend (dist/) and backend wheel.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from control_plane.app.provisioning.artifacts import (
    FileSystemArtifactStore,
    build_manifest,
)

DEFAULT_STORE_ROOT = project_root / ".release-store"


def _build_frontend(root: Path) -> Path:
    """Build frontend and return the dist directory."""
    dist_dir = root / "dist"
    if not dist_dir.is_dir():
        print("[build] Running npm build...")
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(root),
            check=True,
            capture_output=True,
        )
    else:
        print(f"[build] Using existing dist/ at {dist_dir}")
    return dist_dir


def _build_wheel(root: Path, work_dir: Path) -> Path:
    """Build Python wheel and return the path."""
    wheel_dir = work_dir / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    print("[build] Building backend wheel...")
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(root), "-w", str(wheel_dir)],
        check=True,
        capture_output=True,
    )
    wheels = sorted(wheel_dir.glob("boring_ui-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel produced")
    return wheels[-1]


def _create_bundle(
    root: Path,
    dist_dir: Path,
    wheel_path: Path | None,
    work_dir: Path,
) -> Path:
    """Create bundle.tar.gz from project artifacts."""
    bundle_path = work_dir / "bundle.tar.gz"
    print(f"[build] Creating bundle: {bundle_path}")

    with tarfile.open(bundle_path, "w:gz") as tar:
        # Frontend dist.
        if dist_dir.is_dir():
            tar.add(str(dist_dir), arcname="dist")

        # Backend source.
        back_src = root / "src" / "back"
        if back_src.is_dir():
            tar.add(str(back_src), arcname="src/back")

        # pyproject.toml for metadata.
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            tar.add(str(pyproject), arcname="pyproject.toml")

        # Wheel if built.
        if wheel_path and wheel_path.exists():
            tar.add(str(wheel_path), arcname=f"wheels/{wheel_path.name}")

    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and publish boring-ui release artifact"
    )
    parser.add_argument(
        "--app-id", default="boring-ui", help="Application identifier"
    )
    parser.add_argument(
        "--release-id", required=True, help="Release identifier (e.g. v0.1.0)"
    )
    parser.add_argument(
        "--store-root",
        type=Path,
        default=DEFAULT_STORE_ROOT,
        help="Artifact store root directory",
    )
    parser.add_argument(
        "--version", default="0.1.0", help="Semantic version string"
    )
    parser.add_argument(
        "--skip-frontend", action="store_true", help="Skip frontend build"
    )
    parser.add_argument(
        "--skip-wheel", action="store_true", help="Skip wheel build"
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Bundle source only (no npm/pip builds)",
    )
    args = parser.parse_args()

    if args.source_only:
        args.skip_frontend = True
        args.skip_wheel = True

    with tempfile.TemporaryDirectory(prefix="boring-ui-release-") as tmp:
        work_dir = Path(tmp)

        # Build frontend.
        dist_dir = project_root / "dist"
        if not args.skip_frontend:
            dist_dir = _build_frontend(project_root)
        elif not dist_dir.is_dir():
            print("[build] No dist/ found; bundle will omit frontend assets")
            dist_dir = Path("/nonexistent")

        # Build wheel.
        wheel_path = None
        if not args.skip_wheel:
            wheel_path = _build_wheel(project_root, work_dir)

        # Create bundle.
        bundle_path = _create_bundle(
            project_root, dist_dir, wheel_path, work_dir
        )

        # Build manifest and publish.
        manifest = build_manifest(
            app_id=args.app_id,
            release_id=args.release_id,
            bundle_path=bundle_path,
            version=args.version,
        )

        store = FileSystemArtifactStore(args.store_root)
        release_dir = store.publish(manifest, bundle_path)

        # Verify.
        if store.verify_bundle(args.app_id, args.release_id):
            print(f"\n[OK] Release published and verified:")
        else:
            print(f"\n[ERROR] Verification failed!")
            sys.exit(1)

        print(f"  Store root:  {args.store_root}")
        print(f"  Release dir: {release_dir}")
        print(f"  App ID:      {manifest.app_id}")
        print(f"  Release ID:  {manifest.release_id}")
        print(f"  SHA-256:     {manifest.bundle_sha256}")
        print(f"  Size:        {manifest.bundle_size_bytes} bytes")
        print(f"  Version:     {manifest.version}")

        # Show artifact files.
        print(f"\nArtifacts:")
        for f in sorted(release_dir.iterdir()):
            print(f"  {f.name} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
