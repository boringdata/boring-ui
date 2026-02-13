"""Release artifact store and manifest management.

Bead: bd-223o.1 (P1)

Implements :class:`ReleaseArtifactLookup` for provisioning orchestration.
Artifacts are stored in a well-known directory layout::

    {root}/
        {app_id}/
            {release_id}/
                bundle.tar.gz
                manifest.json
                SHA256SUMS

The filesystem store works identically against a local directory or a
mounted Modal Volume.  No Modal-specific code is needed at runtime
because the volume is mounted at a fixed path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .release_contract import ReleaseArtifactLookup


BUNDLE_FILENAME = "bundle.tar.gz"
MANIFEST_FILENAME = "manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Immutable manifest describing a published release artifact."""

    app_id: str
    release_id: str
    bundle_sha256: str
    bundle_size_bytes: int
    created_at: str  # ISO-8601
    version: str

    def to_json(self) -> str:
        """Serialize to indented JSON."""
        return json.dumps(asdict(self), indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> ReleaseManifest:
        """Deserialize from JSON string."""
        data = json.loads(text)
        return cls(**data)


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksum_file(bundle_path: Path, checksum_path: Path) -> str:
    """Compute SHA-256 of *bundle_path* and write *checksum_path*.

    Returns the hex digest string.
    """
    digest = compute_sha256(bundle_path)
    checksum_path.write_text(f"{digest}  {BUNDLE_FILENAME}\n")
    return digest


def verify_checksum(bundle_path: Path, checksum_path: Path) -> bool:
    """Verify *bundle_path* matches the digest recorded in *checksum_path*."""
    text = checksum_path.read_text().strip()
    if not text:
        return False
    # Format: "<hex>  <filename>"
    parts = text.split("  ", 1)
    if len(parts) != 2:
        return False
    expected_digest = parts[0]
    actual_digest = compute_sha256(bundle_path)
    return actual_digest == expected_digest


def build_manifest(
    *,
    app_id: str,
    release_id: str,
    bundle_path: Path,
    version: str = "0.1.0",
) -> ReleaseManifest:
    """Build a :class:`ReleaseManifest` from an existing bundle file."""
    digest = compute_sha256(bundle_path)
    size = bundle_path.stat().st_size
    return ReleaseManifest(
        app_id=app_id,
        release_id=release_id,
        bundle_sha256=digest,
        bundle_size_bytes=size,
        created_at=datetime.now(timezone.utc).isoformat(),
        version=version,
    )


class FileSystemArtifactStore:
    """Read release artifacts from a local directory or mounted volume.

    Implements the :class:`ReleaseArtifactLookup` protocol so it can be
    injected into :func:`resolve_provisioning_target`.

    Directory layout::

        {root}/{app_id}/{release_id}/bundle.tar.gz
        {root}/{app_id}/{release_id}/manifest.json
        {root}/{app_id}/{release_id}/SHA256SUMS
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def _release_dir(self, app_id: str, release_id: str) -> Path:
        return self.root / app_id / release_id

    def bundle_sha256(self, app_id: str, release_id: str) -> str | None:
        """Return bundle checksum or ``None`` if artifacts are missing."""
        manifest = self.get_manifest(app_id, release_id)
        if manifest is None:
            return None
        return manifest.bundle_sha256

    def get_manifest(self, app_id: str, release_id: str) -> ReleaseManifest | None:
        """Load manifest.json for a release, or ``None`` if not found."""
        manifest_path = self._release_dir(app_id, release_id) / MANIFEST_FILENAME
        if not manifest_path.exists():
            return None
        return ReleaseManifest.from_json(manifest_path.read_text())

    def bundle_path(self, app_id: str, release_id: str) -> Path | None:
        """Return path to bundle.tar.gz if it exists."""
        path = self._release_dir(app_id, release_id) / BUNDLE_FILENAME
        return path if path.exists() else None

    def checksum_path(self, app_id: str, release_id: str) -> Path | None:
        """Return path to SHA256SUMS if it exists."""
        path = self._release_dir(app_id, release_id) / CHECKSUM_FILENAME
        return path if path.exists() else None

    def verify_bundle(self, app_id: str, release_id: str) -> bool:
        """Verify bundle integrity: manifest, checksum file, and actual digest all agree."""
        manifest = self.get_manifest(app_id, release_id)
        if manifest is None:
            return False

        bp = self.bundle_path(app_id, release_id)
        if bp is None:
            return False

        cp = self.checksum_path(app_id, release_id)
        if cp is None:
            return False

        # Verify checksum file matches bundle.
        if not verify_checksum(bp, cp):
            return False

        # Verify manifest digest matches bundle.
        actual = compute_sha256(bp)
        return actual == manifest.bundle_sha256

    def publish(self, manifest: ReleaseManifest, bundle_path: Path) -> Path:
        """Write a release to the store directory.

        Creates the directory layout, copies the bundle, writes
        manifest.json and SHA256SUMS.

        Returns the release directory path.
        """
        release_dir = self._release_dir(manifest.app_id, manifest.release_id)
        release_dir.mkdir(parents=True, exist_ok=True)

        # Copy bundle.
        dest_bundle = release_dir / BUNDLE_FILENAME
        dest_bundle.write_bytes(bundle_path.read_bytes())

        # Write manifest.
        (release_dir / MANIFEST_FILENAME).write_text(manifest.to_json())

        # Write checksum file.
        write_checksum_file(dest_bundle, release_dir / CHECKSUM_FILENAME)

        return release_dir

    def list_releases(self, app_id: str) -> list[str]:
        """List available release IDs for an app."""
        app_dir = self.root / app_id
        if not app_dir.is_dir():
            return []
        return sorted(
            d.name
            for d in app_dir.iterdir()
            if d.is_dir() and (d / MANIFEST_FILENAME).exists()
        )
