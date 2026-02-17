"""Tests for release artifact store, manifest parsing, and checksum validation.

Bead: bd-3rqb (P1.1)

Validates:
  - ReleaseManifest JSON serialization/deserialization
  - ReleaseManifest immutability (frozen dataclass)
  - Malformed JSON handling
  - SHA-256 checksum computation correctness
  - Checksum file format (BSD-style: "<hex>  <filename>")
  - Checksum mismatch detection
  - FileSystemArtifactStore publish/retrieve lifecycle
  - FileSystemArtifactStore bundle integrity verification
  - FileSystemArtifactStore missing artifact handling
  - FileSystemArtifactStore list_releases
  - Integration with resolve_provisioning_target
  - build_manifest helper
"""

from __future__ import annotations

import json
import hashlib
import pytest
from pathlib import Path

from control_plane.app.provisioning.artifacts import (
    BUNDLE_FILENAME,
    CHECKSUM_FILENAME,
    MANIFEST_FILENAME,
    FileSystemArtifactStore,
    ReleaseManifest,
    build_manifest,
    compute_sha256,
    verify_checksum,
    write_checksum_file,
)
from control_plane.app.provisioning.release_contract import (
    ReleaseUnavailableError,
    resolve_provisioning_target,
)


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path: Path) -> FileSystemArtifactStore:
    """Artifact store rooted in a temp directory."""
    return FileSystemArtifactStore(tmp_path)


@pytest.fixture
def sample_bundle(tmp_path: Path) -> Path:
    """Create a sample bundle file with known content."""
    bundle = tmp_path / "sample_bundle.tar.gz"
    bundle.write_bytes(b"fake-bundle-content-for-testing-12345")
    return bundle


@pytest.fixture
def sample_manifest(sample_bundle: Path) -> ReleaseManifest:
    """Build a manifest from the sample bundle."""
    return build_manifest(
        app_id="test-app",
        release_id="v1.0.0",
        bundle_path=sample_bundle,
        version="1.0.0",
    )


# =====================================================================
# 1. ReleaseManifest serialization
# =====================================================================


class TestReleaseManifestSerialization:

    def test_to_json_round_trip(self, sample_manifest: ReleaseManifest):
        """Serialize and deserialize should produce identical manifest."""
        json_str = sample_manifest.to_json()
        restored = ReleaseManifest.from_json(json_str)
        assert restored == sample_manifest

    def test_to_json_is_valid_json(self, sample_manifest: ReleaseManifest):
        """to_json output must be valid JSON."""
        data = json.loads(sample_manifest.to_json())
        assert data["app_id"] == "test-app"
        assert data["release_id"] == "v1.0.0"
        assert data["version"] == "1.0.0"
        assert isinstance(data["bundle_sha256"], str)
        assert isinstance(data["bundle_size_bytes"], int)
        assert isinstance(data["created_at"], str)

    def test_to_json_includes_all_fields(self, sample_manifest: ReleaseManifest):
        """All dataclass fields appear in JSON output."""
        data = json.loads(sample_manifest.to_json())
        expected_keys = {
            "app_id", "release_id", "bundle_sha256",
            "bundle_size_bytes", "created_at", "version",
        }
        assert set(data.keys()) == expected_keys

    def test_from_json_malformed_raises(self):
        """Malformed JSON raises an error."""
        with pytest.raises(json.JSONDecodeError):
            ReleaseManifest.from_json("{not valid json")

    def test_from_json_missing_fields_raises(self):
        """Missing required fields raise TypeError."""
        with pytest.raises(TypeError):
            ReleaseManifest.from_json('{"app_id": "test"}')

    def test_from_json_extra_fields_raises(self):
        """Extra unexpected fields raise TypeError."""
        data = {
            "app_id": "test", "release_id": "v1",
            "bundle_sha256": "abc", "bundle_size_bytes": 100,
            "created_at": "2026-01-01", "version": "1.0.0",
            "unexpected_field": "should_fail",
        }
        with pytest.raises(TypeError):
            ReleaseManifest.from_json(json.dumps(data))


# =====================================================================
# 2. ReleaseManifest immutability
# =====================================================================


class TestReleaseManifestImmutability:

    def test_frozen_dataclass(self, sample_manifest: ReleaseManifest):
        """Manifest fields cannot be reassigned."""
        with pytest.raises(AttributeError):
            sample_manifest.app_id = "changed"

    def test_frozen_version(self, sample_manifest: ReleaseManifest):
        with pytest.raises(AttributeError):
            sample_manifest.version = "2.0.0"


# =====================================================================
# 3. SHA-256 checksum computation
# =====================================================================


class TestChecksumComputation:

    def test_compute_sha256_correct(self, sample_bundle: Path):
        """compute_sha256 matches hashlib directly."""
        expected = hashlib.sha256(sample_bundle.read_bytes()).hexdigest()
        actual = compute_sha256(sample_bundle)
        assert actual == expected

    def test_compute_sha256_deterministic(self, sample_bundle: Path):
        """Same file always produces same hash."""
        h1 = compute_sha256(sample_bundle)
        h2 = compute_sha256(sample_bundle)
        assert h1 == h2

    def test_compute_sha256_different_content(self, tmp_path: Path):
        """Different content produces different hash."""
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"content-a")
        f2.write_bytes(b"content-b")
        assert compute_sha256(f1) != compute_sha256(f2)

    def test_compute_sha256_hex_format(self, sample_bundle: Path):
        """Result is a 64-char lowercase hex string."""
        digest = compute_sha256(sample_bundle)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


# =====================================================================
# 4. Checksum file format
# =====================================================================


class TestChecksumFile:

    def test_write_checksum_file_format(self, sample_bundle: Path, tmp_path: Path):
        """Checksum file uses BSD-style format: '<hex>  <filename>'."""
        checksum_path = tmp_path / "SHA256SUMS"
        digest = write_checksum_file(sample_bundle, checksum_path)
        text = checksum_path.read_text()
        assert text == f"{digest}  {BUNDLE_FILENAME}\n"

    def test_verify_checksum_valid(self, sample_bundle: Path, tmp_path: Path):
        """verify_checksum returns True for matching checksum."""
        checksum_path = tmp_path / "SHA256SUMS"
        write_checksum_file(sample_bundle, checksum_path)
        assert verify_checksum(sample_bundle, checksum_path) is True

    def test_verify_checksum_mismatch(self, sample_bundle: Path, tmp_path: Path):
        """verify_checksum returns False when content changes."""
        checksum_path = tmp_path / "SHA256SUMS"
        write_checksum_file(sample_bundle, checksum_path)
        # Corrupt the bundle.
        sample_bundle.write_bytes(b"corrupted-content")
        assert verify_checksum(sample_bundle, checksum_path) is False

    def test_verify_checksum_empty_file(self, sample_bundle: Path, tmp_path: Path):
        """Empty checksum file returns False."""
        checksum_path = tmp_path / "SHA256SUMS"
        checksum_path.write_text("")
        assert verify_checksum(sample_bundle, checksum_path) is False

    def test_verify_checksum_bad_format(self, sample_bundle: Path, tmp_path: Path):
        """Malformed checksum file returns False."""
        checksum_path = tmp_path / "SHA256SUMS"
        checksum_path.write_text("not-a-valid-checksum-line")
        assert verify_checksum(sample_bundle, checksum_path) is False


# =====================================================================
# 5. build_manifest helper
# =====================================================================


class TestBuildManifest:

    def test_computes_sha256(self, sample_bundle: Path):
        m = build_manifest(
            app_id="app", release_id="r1", bundle_path=sample_bundle,
        )
        expected = hashlib.sha256(sample_bundle.read_bytes()).hexdigest()
        assert m.bundle_sha256 == expected

    def test_captures_file_size(self, sample_bundle: Path):
        m = build_manifest(
            app_id="app", release_id="r1", bundle_path=sample_bundle,
        )
        assert m.bundle_size_bytes == sample_bundle.stat().st_size

    def test_uses_provided_version(self, sample_bundle: Path):
        m = build_manifest(
            app_id="app", release_id="r1", bundle_path=sample_bundle,
            version="2.5.0",
        )
        assert m.version == "2.5.0"

    def test_default_version(self, sample_bundle: Path):
        m = build_manifest(
            app_id="app", release_id="r1", bundle_path=sample_bundle,
        )
        assert m.version == "0.1.0"

    def test_created_at_is_iso8601(self, sample_bundle: Path):
        m = build_manifest(
            app_id="app", release_id="r1", bundle_path=sample_bundle,
        )
        # ISO-8601 contains 'T' separator and '+' timezone.
        assert "T" in m.created_at


# =====================================================================
# 6. FileSystemArtifactStore publish + retrieve
# =====================================================================


class TestArtifactStorePublish:

    def test_publish_creates_directory(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        assert release_dir.is_dir()

    def test_publish_creates_bundle(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        assert (release_dir / BUNDLE_FILENAME).exists()

    def test_publish_creates_manifest(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        assert (release_dir / MANIFEST_FILENAME).exists()

    def test_publish_creates_checksum(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        assert (release_dir / CHECKSUM_FILENAME).exists()

    def test_publish_bundle_content_matches(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        published = (release_dir / BUNDLE_FILENAME).read_bytes()
        original = sample_bundle.read_bytes()
        assert published == original

    def test_published_manifest_round_trips(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        tmp_store.publish(sample_manifest, sample_bundle)
        loaded = tmp_store.get_manifest("test-app", "v1.0.0")
        assert loaded is not None
        assert loaded.app_id == sample_manifest.app_id
        assert loaded.bundle_sha256 == sample_manifest.bundle_sha256


# =====================================================================
# 7. FileSystemArtifactStore retrieval
# =====================================================================


class TestArtifactStoreRetrieval:

    def test_get_manifest_returns_none_for_missing(
        self, tmp_store: FileSystemArtifactStore,
    ):
        assert tmp_store.get_manifest("nope", "v1") is None

    def test_bundle_sha256_returns_none_for_missing(
        self, tmp_store: FileSystemArtifactStore,
    ):
        assert tmp_store.bundle_sha256("nope", "v1") is None

    def test_bundle_path_returns_none_for_missing(
        self, tmp_store: FileSystemArtifactStore,
    ):
        assert tmp_store.bundle_path("nope", "v1") is None

    def test_checksum_path_returns_none_for_missing(
        self, tmp_store: FileSystemArtifactStore,
    ):
        assert tmp_store.checksum_path("nope", "v1") is None

    def test_bundle_sha256_returns_digest(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        tmp_store.publish(sample_manifest, sample_bundle)
        sha = tmp_store.bundle_sha256("test-app", "v1.0.0")
        assert sha == sample_manifest.bundle_sha256


# =====================================================================
# 8. FileSystemArtifactStore bundle verification
# =====================================================================


class TestArtifactStoreVerification:

    def test_verify_published_bundle(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        tmp_store.publish(sample_manifest, sample_bundle)
        assert tmp_store.verify_bundle("test-app", "v1.0.0") is True

    def test_verify_missing_bundle_returns_false(
        self, tmp_store: FileSystemArtifactStore,
    ):
        assert tmp_store.verify_bundle("nope", "v1") is False

    def test_verify_corrupted_bundle(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        # Corrupt the bundle.
        (release_dir / BUNDLE_FILENAME).write_bytes(b"corrupted")
        assert tmp_store.verify_bundle("test-app", "v1.0.0") is False

    def test_verify_missing_checksum_file(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        (release_dir / CHECKSUM_FILENAME).unlink()
        assert tmp_store.verify_bundle("test-app", "v1.0.0") is False

    def test_verify_missing_manifest(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        (release_dir / MANIFEST_FILENAME).unlink()
        assert tmp_store.verify_bundle("test-app", "v1.0.0") is False

    def test_verify_manifest_sha_mismatch(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        """Manifest SHA-256 doesn't match actual bundle (but checksum file does)."""
        release_dir = tmp_store.publish(sample_manifest, sample_bundle)
        # Replace bundle with different content but update SHA256SUMS.
        new_content = b"different-content-entirely"
        (release_dir / BUNDLE_FILENAME).write_bytes(new_content)
        new_digest = hashlib.sha256(new_content).hexdigest()
        (release_dir / CHECKSUM_FILENAME).write_text(
            f"{new_digest}  {BUNDLE_FILENAME}\n"
        )
        # Checksum file matches bundle, but manifest SHA doesn't.
        assert tmp_store.verify_bundle("test-app", "v1.0.0") is False


# =====================================================================
# 9. FileSystemArtifactStore list_releases
# =====================================================================


class TestArtifactStoreListReleases:

    def test_empty_store(self, tmp_store: FileSystemArtifactStore):
        assert tmp_store.list_releases("test-app") == []

    def test_lists_published_releases(
        self, tmp_store: FileSystemArtifactStore, sample_bundle: Path,
    ):
        for rid in ("v1.0.0", "v2.0.0", "v1.1.0"):
            m = build_manifest(
                app_id="test-app", release_id=rid,
                bundle_path=sample_bundle, version=rid,
            )
            tmp_store.publish(m, sample_bundle)

        releases = tmp_store.list_releases("test-app")
        assert releases == ["v1.0.0", "v1.1.0", "v2.0.0"]  # sorted

    def test_ignores_dirs_without_manifest(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        tmp_store.publish(sample_manifest, sample_bundle)
        # Create a directory without a manifest.
        fake_dir = tmp_store.root / "test-app" / "dangling"
        fake_dir.mkdir(parents=True)
        releases = tmp_store.list_releases("test-app")
        assert "dangling" not in releases
        assert "v1.0.0" in releases

    def test_different_app_ids_isolated(
        self, tmp_store: FileSystemArtifactStore, sample_bundle: Path,
    ):
        for app_id in ("app-a", "app-b"):
            m = build_manifest(
                app_id=app_id, release_id="v1",
                bundle_path=sample_bundle,
            )
            tmp_store.publish(m, sample_bundle)

        assert tmp_store.list_releases("app-a") == ["v1"]
        assert tmp_store.list_releases("app-b") == ["v1"]
        assert tmp_store.list_releases("app-c") == []


# =====================================================================
# 10. Integration with resolve_provisioning_target
# =====================================================================


class TestArtifactStoreProvisioningIntegration:

    def test_store_satisfies_lookup_protocol(
        self, tmp_store: FileSystemArtifactStore,
        sample_manifest: ReleaseManifest, sample_bundle: Path,
    ):
        """FileSystemArtifactStore works as ReleaseArtifactLookup."""
        tmp_store.publish(sample_manifest, sample_bundle)
        target = resolve_provisioning_target(
            app_id="test-app",
            workspace_id="ws-1",
            env="prod",
            requested_release_id="v1.0.0",
            default_release_id=None,
            artifact_lookup=tmp_store,
        )
        assert target.release_id == "v1.0.0"
        assert target.bundle_sha256 == sample_manifest.bundle_sha256
        assert target.sandbox_name == "sbx-test-app-ws-1-prod"

    def test_missing_release_raises_unavailable(
        self, tmp_store: FileSystemArtifactStore,
    ):
        """Missing artifacts trigger ReleaseUnavailableError."""
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id="test-app",
                workspace_id="ws-1",
                env="prod",
                requested_release_id="v99.0.0",
                default_release_id=None,
                artifact_lookup=tmp_store,
            )
        assert exc_info.value.reason == "artifacts_not_found"
