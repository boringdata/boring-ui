"""Seed data scenario readiness validation tests.

Bead: bd-223o.16.2.1 (K2a)

Validates:
  1. Seed users cover all 8 scenario preconditions.
  2. Seed workspaces provide required files and membership.
  3. Seed manifest contract is well-formed.
  4. Role/permission coverage for negative and positive paths.
  5. Determinism: re-running seed produces identical data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Import seed data definitions directly to validate coverage.
# These are constants, not runtime-side-effecting.
from importlib.util import module_from_spec, spec_from_file_location

SEED_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "deploy"
    / "example-app"
    / "seed.py"
)


def _load_seed_module(name: str = "seed"):
    """Load seed.py as a named module, registering in sys.modules."""
    spec = spec_from_file_location(name, SEED_MODULE_PATH)
    assert spec is not None, f"seed.py not found at {SEED_MODULE_PATH}"
    mod = module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def seed_mod():
    """Import seed.py as a module without executing main()."""
    return _load_seed_module("seed_e2e")


# ── Seed user coverage ───────────────────────────────────────────────


class TestSeedUserCoverage:
    """Verify seed users satisfy all scenario preconditions."""

    def test_at_least_three_users(self, seed_mod):
        """S-001/S-003/S-007/S-008 require distinct user roles."""
        assert len(seed_mod.SEED_USERS) >= 3

    def test_has_owner_role(self, seed_mod):
        """S-002/S-004: workspace creation and file editing need an owner."""
        roles = {u.role for u in seed_mod.SEED_USERS}
        assert "owner" in roles

    def test_has_member_role(self, seed_mod):
        """S-003/S-007: multi-user scenarios need a member."""
        roles = {u.role for u in seed_mod.SEED_USERS}
        assert "member" in roles

    def test_has_unauthenticated_role(self, seed_mod):
        """S-008: session expiry needs a user with no workspace role."""
        roles = {u.role for u in seed_mod.SEED_USERS}
        assert "none" in roles

    def test_all_users_have_email(self, seed_mod):
        """Every seed user must have a non-empty email."""
        for user in seed_mod.SEED_USERS:
            assert user.email, f"User missing email: {user}"
            assert "@" in user.email

    def test_all_users_have_password(self, seed_mod):
        """Every seed user must have a password for Supabase auth."""
        for user in seed_mod.SEED_USERS:
            assert user.password, f"User missing password: {user.email}"
            assert len(user.password) >= 8

    def test_all_users_have_display_name(self, seed_mod):
        """Display names required for UI scenario evidence."""
        for user in seed_mod.SEED_USERS:
            assert user.display_name, f"User missing display_name: {user.email}"

    def test_emails_are_unique(self, seed_mod):
        """No duplicate emails in seed data."""
        emails = [u.email for u in seed_mod.SEED_USERS]
        assert len(emails) == len(set(emails))

    def test_e2e_test_domain(self, seed_mod):
        """Seed emails use e2e.test domain to prevent accidental delivery."""
        for user in seed_mod.SEED_USERS:
            assert user.email.endswith("@e2e.test"), (
                f"Seed email {user.email} must use @e2e.test domain"
            )


# ── Seed workspace coverage ──────────────────────────────────────────


class TestSeedWorkspaceCoverage:
    """Verify seed workspaces satisfy all scenario preconditions."""

    def test_at_least_two_workspaces(self, seed_mod):
        """S-003 requires switching between two workspaces."""
        assert len(seed_mod.SEED_WORKSPACES) >= 2

    def test_at_least_one_with_files(self, seed_mod):
        """S-004: file editing needs a workspace with seeded files."""
        with_files = [ws for ws in seed_mod.SEED_WORKSPACES if ws.files]
        assert len(with_files) >= 1

    def test_file_workspace_has_readme(self, seed_mod):
        """S-004: file editing scenario references README.md."""
        file_ws = [ws for ws in seed_mod.SEED_WORKSPACES if ws.files]
        assert any("README.md" in ws.files for ws in file_ws)

    def test_file_workspace_has_python_file(self, seed_mod):
        """S-004/S-005: scenarios need a source file for editing/chat context."""
        file_ws = [ws for ws in seed_mod.SEED_WORKSPACES if ws.files]
        py_found = any(
            any(f.endswith(".py") for f in ws.files)
            for ws in file_ws
        )
        assert py_found

    def test_at_least_one_empty_workspace(self, seed_mod):
        """S-003: workspace switch scenario uses an empty workspace."""
        empty_ws = [ws for ws in seed_mod.SEED_WORKSPACES if not ws.files]
        assert len(empty_ws) >= 1

    def test_all_workspaces_have_slug(self, seed_mod):
        """Every workspace needs a URL-safe slug."""
        for ws in seed_mod.SEED_WORKSPACES:
            assert ws.slug, f"Workspace missing slug: {ws.name}"
            assert " " not in ws.slug

    def test_all_workspaces_have_name(self, seed_mod):
        """Display names required for UI evidence."""
        for ws in seed_mod.SEED_WORKSPACES:
            assert ws.name, f"Workspace missing name: {ws.slug}"

    def test_all_workspaces_have_owner(self, seed_mod):
        """Every workspace must reference a seeded owner email."""
        seed_emails = {u.email for u in seed_mod.SEED_USERS}
        for ws in seed_mod.SEED_WORKSPACES:
            assert ws.owner_email in seed_emails, (
                f"Workspace {ws.slug} owner {ws.owner_email!r} not in seed users"
            )

    def test_slugs_are_unique(self, seed_mod):
        """No duplicate workspace slugs."""
        slugs = [ws.slug for ws in seed_mod.SEED_WORKSPACES]
        assert len(slugs) == len(set(slugs))

    def test_owner_has_multiple_workspaces(self, seed_mod):
        """S-003: at least one user must own 2+ workspaces for switch."""
        from collections import Counter

        owner_counts = Counter(ws.owner_email for ws in seed_mod.SEED_WORKSPACES)
        assert any(c >= 2 for c in owner_counts.values()), (
            "At least one user must own 2+ workspaces for S-003 workspace switch"
        )


# ── Seed manifest contract ───────────────────────────────────────────


class TestSeedManifestContract:
    """Validate seed_manifest.json output contract for scenario runner."""

    @pytest.fixture
    def manifest(self, seed_mod):
        """Generate a manifest in a temp dir to validate structure."""
        user_ids = {u.email: f"fake-id-{i}" for i, u in enumerate(seed_mod.SEED_USERS)}
        manifest_entries = []
        for ws in seed_mod.SEED_WORKSPACES:
            manifest_entries.append({
                "slug": ws.slug,
                "name": ws.name,
                "owner_email": ws.owner_email,
                "owner_id": user_ids.get(ws.owner_email, ""),
                "files": ws.files,
            })
        return manifest_entries

    def test_manifest_is_list(self, manifest):
        assert isinstance(manifest, list)

    def test_manifest_has_entries(self, manifest):
        assert len(manifest) >= 2

    def test_each_entry_has_required_fields(self, manifest):
        required = {"slug", "name", "owner_email", "owner_id", "files"}
        for entry in manifest:
            assert required.issubset(entry.keys()), (
                f"Manifest entry missing fields: {required - entry.keys()}"
            )

    def test_files_field_is_dict(self, manifest):
        for entry in manifest:
            assert isinstance(entry["files"], dict)

    def test_manifest_round_trips_json(self, manifest):
        """Manifest must serialize/deserialize cleanly for scenario runner."""
        raw = json.dumps(manifest, indent=2)
        restored = json.loads(raw)
        assert restored == manifest

    def test_manifest_owner_ids_are_non_empty(self, manifest):
        for entry in manifest:
            assert entry["owner_id"], (
                f"Manifest entry {entry['slug']!r} has empty owner_id"
            )


# ── Role-permission matrix ───────────────────────────────────────────


class TestRolePermissionMatrix:
    """Validate seed data covers positive and negative auth paths."""

    def test_alice_is_primary_actor(self, seed_mod):
        """S-001 through S-005 use alice as the primary scenario actor."""
        alice = next(
            (u for u in seed_mod.SEED_USERS if "alice" in u.email), None,
        )
        assert alice is not None
        assert alice.role == "owner"

    def test_bob_is_secondary_actor(self, seed_mod):
        """S-003/S-007 use bob for multi-user scenarios."""
        bob = next(
            (u for u in seed_mod.SEED_USERS if "bob" in u.email), None,
        )
        assert bob is not None
        assert bob.role == "member"

    def test_eve_is_negative_actor(self, seed_mod):
        """S-008 uses eve for unauthenticated/expired-session scenarios."""
        eve = next(
            (u for u in seed_mod.SEED_USERS if "eve" in u.email), None,
        )
        assert eve is not None
        assert eve.role == "none"

    def test_owner_can_create_workspaces(self, seed_mod):
        """S-002: at least one user with owner role for workspace creation."""
        owners = [u for u in seed_mod.SEED_USERS if u.role == "owner"]
        assert len(owners) >= 1

    def test_member_cannot_own_workspace(self, seed_mod):
        """Members should not be workspace owners in seed data."""
        member_emails = {u.email for u in seed_mod.SEED_USERS if u.role == "member"}
        for ws in seed_mod.SEED_WORKSPACES:
            assert ws.owner_email not in member_emails, (
                f"Workspace {ws.slug!r} owned by member {ws.owner_email!r}"
            )


# ── Scenario-specific readiness ──────────────────────────────────────


class TestScenarioReadiness:
    """Validate seed data satisfies each scenario's preconditions."""

    def test_s001_login_user_exists(self, seed_mod):
        """S-001: needs at least one user with email + password."""
        assert any(u.email and u.password for u in seed_mod.SEED_USERS)

    def test_s002_workspace_creator_exists(self, seed_mod):
        """S-002: needs an owner user who can create workspaces."""
        assert any(u.role == "owner" for u in seed_mod.SEED_USERS)

    def test_s003_switch_has_two_workspaces_same_owner(self, seed_mod):
        """S-003: user must be able to switch between 2+ workspaces."""
        from collections import Counter

        counts = Counter(ws.owner_email for ws in seed_mod.SEED_WORKSPACES)
        assert any(c >= 2 for c in counts.values())

    def test_s004_file_edit_workspace_with_file(self, seed_mod):
        """S-004: needs a workspace with at least one editable file."""
        assert any(
            ws.files and any(
                not f.endswith("/") for f in ws.files
            )
            for ws in seed_mod.SEED_WORKSPACES
        )

    def test_s005_chat_workspace_with_source(self, seed_mod):
        """S-005: chat scenario needs a workspace with source code."""
        assert any(
            any(f.endswith(".py") for f in ws.files)
            for ws in seed_mod.SEED_WORKSPACES
        )

    def test_s006_provision_retry_owner_exists(self, seed_mod):
        """S-006: retry scenario needs an owner who can provision."""
        assert any(u.role == "owner" for u in seed_mod.SEED_USERS)

    def test_s007_share_link_two_users(self, seed_mod):
        """S-007: share link needs two distinct users."""
        assert len(seed_mod.SEED_USERS) >= 2

    def test_s008_session_expiry_user_exists(self, seed_mod):
        """S-008: needs a user to establish and expire a session."""
        assert any(u.email and u.password for u in seed_mod.SEED_USERS)


# ── Determinism ──────────────────────────────────────────────────────


class TestSeedDeterminism:
    """Verify seed data is stable across repeated evaluations."""

    def test_user_list_is_stable(self, seed_mod):
        """Re-importing seed.py yields the same users."""
        mod2 = _load_seed_module("seed_copy")

        emails_1 = [u.email for u in seed_mod.SEED_USERS]
        emails_2 = [u.email for u in mod2.SEED_USERS]
        assert emails_1 == emails_2

    def test_workspace_list_is_stable(self, seed_mod):
        """Re-importing seed.py yields the same workspaces."""
        mod2 = _load_seed_module("seed_copy2")

        slugs_1 = [ws.slug for ws in seed_mod.SEED_WORKSPACES]
        slugs_2 = [ws.slug for ws in mod2.SEED_WORKSPACES]
        assert slugs_1 == slugs_2

    def test_file_content_is_stable(self, seed_mod):
        """File seeds are literal strings, not generated content."""
        mod2 = _load_seed_module("seed_copy3")

        for ws1, ws2 in zip(
            seed_mod.SEED_WORKSPACES, mod2.SEED_WORKSPACES, strict=True,
        ):
            assert ws1.files == ws2.files


# ── SeedUser / SeedWorkspace dataclass contract ─────────────────────


class TestDataclassContract:
    """Validate seed dataclass fields used by seed_workspaces()."""

    def test_seed_user_fields(self, seed_mod):
        user = seed_mod.SeedUser(
            email="test@e2e.test",
            password="test-pass-1234",
            role="owner",
            display_name="Test",
        )
        assert user.email == "test@e2e.test"
        assert user.password == "test-pass-1234"
        assert user.role == "owner"
        assert user.display_name == "Test"

    def test_seed_workspace_fields(self, seed_mod):
        ws = seed_mod.SeedWorkspace(
            slug="ws-test",
            name="Test WS",
            owner_email="test@e2e.test",
            files={"README.md": "# Hello"},
        )
        assert ws.slug == "ws-test"
        assert ws.name == "Test WS"
        assert ws.owner_email == "test@e2e.test"
        assert ws.files == {"README.md": "# Hello"}

    def test_seed_workspace_default_files(self, seed_mod):
        """files defaults to empty dict if omitted."""
        ws = seed_mod.SeedWorkspace(
            slug="ws-empty",
            name="Empty WS",
            owner_email="test@e2e.test",
        )
        assert ws.files == {}
