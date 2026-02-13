"""Schema invariant tests for V0 control-plane migrations.

Bead: bd-2f2e (A5)

Validates migration SQL files enforce the design-doc contracts:
  - All expected tables exist with correct constraints
  - RLS is enabled on every table
  - Migration idempotency patterns (IF NOT EXISTS / IF EXISTS)
  - Audit immutability triggers
  - updated_at automation
  - Unique index enforcement definitions
  - Check constraint coverage

These tests parse the SQL migration files directly — no live database
required.  They catch regressions in the migration source before
deployment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ── Migration file paths ──────────────────────────────────────────────

_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[3]
    / 'src'
    / 'control_plane'
    / 'migrations'
)

_SCHEMA_SQL = (_MIGRATIONS_DIR / '002_v0_core_schema.sql').read_text()
_RLS_SQL = (_MIGRATIONS_DIR / '003_v0_rls_policies.sql').read_text()

# ── Expected V0 tables (design doc section 12) ───────────────────────

V0_TABLES = (
    'cloud.workspaces',
    'cloud.workspace_members',
    'cloud.workspace_runtime',
    'cloud.workspace_provision_jobs',
    'cloud.audit_events',
    'cloud.file_share_links',
)

# ── Helpers ───────────────────────────────────────────────────────────


def _normalise(sql: str) -> str:
    """Lower-case and collapse whitespace for pattern matching."""
    return re.sub(r'\s+', ' ', sql.lower())


_SCHEMA_NORM = _normalise(_SCHEMA_SQL)
_RLS_NORM = _normalise(_RLS_SQL)


# =====================================================================
# 1. Table creation
# =====================================================================


class TestTableCreation:
    """Every V0 table must be created with IF NOT EXISTS."""

    @pytest.mark.parametrize('table', V0_TABLES)
    def test_table_created(self, table: str):
        pattern = f'create table if not exists {table}'
        assert pattern in _SCHEMA_NORM, (
            f'{table} not created with IF NOT EXISTS'
        )


# =====================================================================
# 2. RLS enablement
# =====================================================================


class TestRLSEnablement:
    """RLS must be enabled on every V0 table (design doc section 12.1)."""

    @pytest.mark.parametrize('table', V0_TABLES)
    def test_rls_enabled(self, table: str):
        pattern = f'alter table {table} enable row level security'
        assert pattern in _SCHEMA_NORM, (
            f'RLS not enabled on {table}'
        )


# =====================================================================
# 3. Check constraints (state enums, role enums, access enums)
# =====================================================================


class TestCheckConstraints:
    """Verify enum-like check constraints exist for key columns."""

    def test_workspace_members_role_check(self):
        assert "check (role in ('admin'))" in _SCHEMA_NORM

    def test_workspace_members_status_check(self):
        assert "check (status in ('pending', 'active', 'removed'))" in _SCHEMA_NORM

    def test_workspace_runtime_state_check(self):
        assert "'provisioning'" in _SCHEMA_NORM
        assert "'ready'" in _SCHEMA_NORM
        assert "'error'" in _SCHEMA_NORM

    def test_provision_jobs_state_check(self):
        for state in (
            'queued', 'release_resolve', 'creating_sandbox',
            'uploading_artifact', 'bootstrapping', 'health_check',
            'ready', 'error',
        ):
            assert f"'{state}'" in _SCHEMA_NORM, (
                f'Provision job state {state!r} not found in schema'
            )

    def test_file_share_links_access_check(self):
        assert "check (access in ('read', 'write'))" in _SCHEMA_NORM


# =====================================================================
# 4. Unique indexes (design doc section 12)
# =====================================================================


class TestUniqueIndexes:
    """Critical unique indexes that enforce business invariants."""

    def test_active_email_unique_index(self):
        """Prevent duplicate pending/active invites per workspace+email."""
        assert 'ux_workspace_members_active_email' in _SCHEMA_NORM

    def test_active_job_unique_index(self):
        """At most one active provisioning job per workspace."""
        assert 'ux_workspace_jobs_active' in _SCHEMA_NORM

    def test_idempotency_key_unique_index(self):
        """Idempotency key dedupe for client retries."""
        assert 'ux_workspace_jobs_idempotency' in _SCHEMA_NORM

    def test_token_hash_unique(self):
        """Share link token_hash is unique."""
        assert 'token_hash' in _SCHEMA_NORM
        assert 'unique' in _SCHEMA_NORM


# =====================================================================
# 5. Audit immutability
# =====================================================================


class TestAuditImmutability:
    """Audit events must be protected by immutability triggers."""

    def test_no_update_trigger(self):
        assert 'trg_audit_events_no_update' in _SCHEMA_NORM

    def test_no_delete_trigger(self):
        assert 'trg_audit_events_no_delete' in _SCHEMA_NORM

    def test_immutability_function(self):
        assert 'audit_events_immutable' in _SCHEMA_NORM

    def test_trigger_raises_exception(self):
        assert 'audit_events is immutable' in _SCHEMA_NORM


# =====================================================================
# 6. updated_at triggers
# =====================================================================


class TestUpdatedAtTriggers:
    """Mutable tables must have updated_at automation."""

    MUTABLE_TABLES = (
        'cloud.workspaces',
        'cloud.workspace_members',
        'cloud.workspace_runtime',
        'cloud.workspace_provision_jobs',
    )

    def test_set_updated_at_function(self):
        assert 'cloud.set_updated_at()' in _SCHEMA_NORM

    # Map table names to their actual trigger names in the migration.
    # workspace_provision_jobs uses shortened name trg_provision_jobs_updated_at.
    _TRIGGER_NAMES = {
        'cloud.workspaces': 'trg_workspaces_updated_at',
        'cloud.workspace_members': 'trg_workspace_members_updated_at',
        'cloud.workspace_runtime': 'trg_workspace_runtime_updated_at',
        'cloud.workspace_provision_jobs': 'trg_provision_jobs_updated_at',
    }

    @pytest.mark.parametrize('table', MUTABLE_TABLES)
    def test_trigger_exists(self, table: str):
        trigger = self._TRIGGER_NAMES[table]
        assert trigger in _SCHEMA_NORM, (
            f'Missing updated_at trigger for {table}'
        )


# =====================================================================
# 7. Migration idempotency patterns
# =====================================================================


class TestMigrationIdempotency:
    """Migrations must be safe to re-run."""

    def test_schema_uses_if_not_exists_for_tables(self):
        creates = re.findall(r'create table\b', _SCHEMA_NORM)
        creates_idempotent = re.findall(
            r'create table if not exists\b', _SCHEMA_NORM
        )
        assert len(creates) == len(creates_idempotent), (
            'All CREATE TABLE statements must use IF NOT EXISTS'
        )

    def test_schema_uses_if_not_exists_for_indexes(self):
        creates = re.findall(r'create (?:unique )?index\b', _SCHEMA_NORM)
        creates_idempotent = re.findall(
            r'create (?:unique )?index if not exists\b', _SCHEMA_NORM
        )
        assert len(creates) == len(creates_idempotent), (
            'All CREATE INDEX statements must use IF NOT EXISTS'
        )

    def test_schema_uses_create_or_replace_for_functions(self):
        creates = re.findall(r'create (?:or replace )?function\b', _SCHEMA_NORM)
        creates_safe = re.findall(
            r'create or replace function\b', _SCHEMA_NORM
        )
        assert len(creates) == len(creates_safe), (
            'All CREATE FUNCTION statements must use OR REPLACE'
        )

    def test_schema_drops_triggers_before_create(self):
        """Each CREATE TRIGGER must be preceded by DROP TRIGGER IF EXISTS."""
        creates = re.findall(r'create trigger (\w+)', _SCHEMA_NORM)
        for trigger in creates:
            assert f'drop trigger if exists {trigger}' in _SCHEMA_NORM, (
                f'Missing DROP TRIGGER IF EXISTS for {trigger}'
            )

    def test_rls_drops_policies_before_create(self):
        """Each CREATE POLICY must be preceded by DROP POLICY IF EXISTS."""
        creates = re.findall(r'create policy (\w+)', _RLS_NORM)
        assert len(creates) > 0, 'No policies found in RLS migration'
        for policy in creates:
            assert f'drop policy if exists {policy}' in _RLS_NORM, (
                f'Missing DROP POLICY IF EXISTS for {policy}'
            )


# =====================================================================
# 8. RLS policy coverage (matches P5 review checklist section 1.2)
# =====================================================================


class TestRLSPolicyCoverage:
    """Every table must have the policies specified in P5 review."""

    def test_workspaces_select_policy(self):
        assert 'workspace_member_read' in _RLS_NORM

    def test_workspaces_update_policy(self):
        assert 'workspace_member_update' in _RLS_NORM

    def test_workspace_members_select_active(self):
        assert 'member_read_own_workspace' in _RLS_NORM

    def test_workspace_members_select_pending(self):
        assert 'member_read_own_pending' in _RLS_NORM

    def test_workspace_runtime_select(self):
        assert 'runtime_member_read' in _RLS_NORM

    def test_provision_jobs_select(self):
        assert 'provision_job_member_read' in _RLS_NORM

    def test_audit_events_select(self):
        assert 'audit_member_read' in _RLS_NORM

    def test_file_share_links_select(self):
        assert 'share_link_member_read' in _RLS_NORM

    def test_file_share_links_update(self):
        assert 'share_link_member_revoke' in _RLS_NORM

    def test_total_policy_count(self):
        """P5 review specifies exactly 9 user-facing policies."""
        policies = re.findall(r'create policy \w+', _RLS_NORM)
        assert len(policies) == 9, (
            f'Expected 9 policies from P5 review, found {len(policies)}'
        )


# =====================================================================
# 9. RLS policy correctness (membership joins, status checks)
# =====================================================================


class TestRLSPolicyCorrectness:
    """Verify policies enforce the correct access patterns."""

    def test_all_select_policies_check_workspace_membership(self):
        """Every SELECT policy must join through workspace_members."""
        # Extract each CREATE POLICY ... FOR SELECT block
        policy_blocks = re.findall(
            r'create policy \w+ on [\w.]+ for select using \([^;]+\);',
            _RLS_NORM,
        )
        for block in policy_blocks:
            # The pending-invite policy uses email match instead of membership join
            if 'member_read_own_pending' in block:
                assert "auth.jwt()" in block, (
                    'Pending invite policy must use auth.jwt() for email match'
                )
                continue
            assert 'workspace_members' in block, (
                f'SELECT policy missing workspace_members join: {block[:80]}'
            )

    def test_select_policies_require_active_status(self):
        """Non-pending SELECT policies must check status = 'active'."""
        policy_blocks = re.findall(
            r'create policy \w+ on [\w.]+ for select using \([^;]+\);',
            _RLS_NORM,
        )
        for block in policy_blocks:
            if 'member_read_own_pending' in block:
                assert "'pending'" in block
                continue
            # Policies may use different aliases (wm, self) for the join
            assert ".status = 'active'" in block, (
                f'SELECT policy missing active status check: {block[:80]}'
            )

    def test_admin_only_policies_check_role(self):
        """Audit events and share links must require admin role."""
        for policy_name in ('audit_member_read', 'share_link_member_read', 'share_link_member_revoke'):
            # Find the policy block
            pattern = rf'create policy {policy_name}[^;]+;'
            matches = re.findall(pattern, _RLS_NORM)
            assert len(matches) == 1, f'Policy {policy_name} not found'
            assert "wm.role = 'admin'" in matches[0], (
                f'{policy_name} must require admin role'
            )

    def test_update_policies_have_with_check(self):
        """UPDATE policies must include WITH CHECK clause."""
        update_blocks = re.findall(
            r'create policy \w+ on [\w.]+ for update[^;]+;',
            _RLS_NORM,
        )
        for block in update_blocks:
            assert 'with check' in block, (
                f'UPDATE policy missing WITH CHECK: {block[:80]}'
            )

    def test_workspace_update_requires_admin(self):
        """Only admins can update workspace name."""
        pattern = r'create policy workspace_member_update[^;]+;'
        matches = re.findall(pattern, _RLS_NORM)
        assert len(matches) == 1
        assert "wm.role = 'admin'" in matches[0]

    def test_pending_invite_uses_case_insensitive_email(self):
        """Pending invite match must be case-insensitive."""
        pattern = r'create policy member_read_own_pending[^;]+;'
        matches = re.findall(pattern, _RLS_NORM)
        assert len(matches) == 1
        assert 'lower(' in matches[0], (
            'Pending invite email match must use lower() for case insensitivity'
        )


# =====================================================================
# 10. No user INSERT/DELETE policies
# =====================================================================


class TestNoUserMutationPolicies:
    """Authenticated users must NOT have INSERT or DELETE policies.

    All mutations (except admin-only UPDATE on workspaces/share_links)
    are service-role only.  The migration comments document this, but
    we verify no accidental INSERT/DELETE policies were created.
    """

    def test_no_insert_policies(self):
        inserts = re.findall(r'create policy \w+ on [\w.]+ for insert', _RLS_NORM)
        assert len(inserts) == 0, (
            f'No INSERT policies should exist for authenticated users: {inserts}'
        )

    def test_no_delete_policies(self):
        deletes = re.findall(r'create policy \w+ on [\w.]+ for delete', _RLS_NORM)
        assert len(deletes) == 0, (
            f'No DELETE policies should exist for authenticated users: {deletes}'
        )


# =====================================================================
# 11. Foreign key references
# =====================================================================


class TestForeignKeys:
    """Verify FK references to enforce referential integrity."""

    def test_workspaces_created_by_references_auth_users(self):
        assert 'references auth.users(id)' in _SCHEMA_NORM

    def test_workspace_members_references_workspaces(self):
        assert 'references cloud.workspaces(id)' in _SCHEMA_NORM

    def test_workspace_runtime_references_workspaces(self):
        # workspace_runtime has workspace_id FK
        pattern = r'workspace_runtime.*references cloud\.workspaces\(id\)'
        assert re.search(pattern, _SCHEMA_NORM, re.DOTALL)

    def test_provision_jobs_references_workspaces(self):
        pattern = r'provision_jobs.*references cloud\.workspaces\(id\)'
        assert re.search(pattern, _SCHEMA_NORM, re.DOTALL)

    def test_audit_events_references_workspaces(self):
        pattern = r'audit_events.*references cloud\.workspaces\(id\)'
        assert re.search(pattern, _SCHEMA_NORM, re.DOTALL)

    def test_file_share_links_references_workspaces(self):
        pattern = r'file_share_links.*references cloud\.workspaces\(id\)'
        assert re.search(pattern, _SCHEMA_NORM, re.DOTALL)


# =====================================================================
# 12. Schema creation
# =====================================================================


class TestSchemaSetup:
    """The cloud schema must be created before tables."""

    def test_schema_created(self):
        assert 'create schema if not exists cloud' in _SCHEMA_NORM
