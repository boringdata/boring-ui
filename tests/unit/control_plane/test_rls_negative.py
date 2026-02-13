"""Cross-workspace RLS negative test suite.

Bead: bd-223o.6.2.1 (A2a)

Validates that RLS policies correctly deny access in all negative
scenarios defined in the P5 review checklist (P5_REVIEW_CHECKLIST.md,
section 3).  Each test ID (N-CW-*, N-ST-*, etc.) maps to a concrete
assertion about the policy SQL.

These tests analyse the migration SQL directly — no live database
required.  They prove the policy definitions structurally enforce
the expected denials.

Test categories:
  N-CW  Cross-workspace access denial (non-member → empty result)
  N-ST  Status-based denial (removed/pending member → denied)
  N-RL  Role-based mutation denial (non-admin → denied)
  N-MU  Authenticated user mutation denial (no INSERT/DELETE policies)
  N-PI  Pending invite isolation (email scoping)
  N-AU  Audit immutability (triggers block UPDATE/DELETE)
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

# ── Helpers ───────────────────────────────────────────────────────────


def _normalise(sql: str) -> str:
    """Lower-case and collapse whitespace for pattern matching."""
    return re.sub(r'\s+', ' ', sql.lower())


def _extract_policy(name: str, sql_norm: str) -> str:
    """Extract a single CREATE POLICY block by name."""
    pattern = rf'create policy {name}\b[^;]+;'
    matches = re.findall(pattern, sql_norm)
    assert len(matches) == 1, f'Expected 1 policy {name!r}, found {len(matches)}'
    return matches[0]


_SCHEMA_NORM = _normalise(_SCHEMA_SQL)
_RLS_NORM = _normalise(_RLS_SQL)

# All V0 tables governed by RLS.
_V0_TABLES = (
    'cloud.workspaces',
    'cloud.workspace_members',
    'cloud.workspace_runtime',
    'cloud.workspace_provision_jobs',
    'cloud.audit_events',
    'cloud.file_share_links',
)

# Map tables → their SELECT policy names (for cross-workspace checks).
_SELECT_POLICIES = {
    'cloud.workspaces': 'workspace_member_read',
    'cloud.workspace_members': ['member_read_own_workspace', 'member_read_own_pending'],
    'cloud.workspace_runtime': 'runtime_member_read',
    'cloud.workspace_provision_jobs': 'provision_job_member_read',
    'cloud.audit_events': 'audit_member_read',
    'cloud.file_share_links': 'share_link_member_read',
}


# =====================================================================
# N-CW: Cross-Workspace Access Denial
# =====================================================================
# A user who is NOT a member of workspace B must see empty results
# when querying any table scoped to workspace B.
#
# Mechanism: every SELECT policy joins through workspace_members
# checking auth.uid() matches a membership row.  Without a membership
# row the USING clause evaluates FALSE → row invisible.
# =====================================================================


class TestCrossWorkspaceAccessDenial:
    """N-CW-01 through N-CW-06: non-member gets empty results."""

    def test_n_cw_01_workspace_record_denied(self):
        """N-CW-01: User A reads workspace B's record (not a member) → denied."""
        policy = _extract_policy('workspace_member_read', _RLS_NORM)
        # Must join workspace_members and check auth.uid()
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        # Must check the JOIN is on the SAME workspace
        assert 'wm.workspace_id = cloud.workspaces.id' in policy

    def test_n_cw_02_members_denied(self):
        """N-CW-02: User A reads workspace B's members (not a member) → denied."""
        policy = _extract_policy('member_read_own_workspace', _RLS_NORM)
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        # The self-join must correlate on workspace_id
        assert 'self.workspace_id = cloud.workspace_members.workspace_id' in policy

    def test_n_cw_03_runtime_denied(self):
        """N-CW-03: User A reads workspace B's runtime (not a member) → denied."""
        policy = _extract_policy('runtime_member_read', _RLS_NORM)
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        assert 'wm.workspace_id = cloud.workspace_runtime.workspace_id' in policy

    def test_n_cw_04_provision_jobs_denied(self):
        """N-CW-04: User A reads workspace B's provision jobs (not a member) → denied."""
        policy = _extract_policy('provision_job_member_read', _RLS_NORM)
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        assert 'wm.workspace_id = cloud.workspace_provision_jobs.workspace_id' in policy

    def test_n_cw_05_audit_events_denied(self):
        """N-CW-05: User A reads workspace B's audit events (not a member) → denied."""
        policy = _extract_policy('audit_member_read', _RLS_NORM)
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        assert 'wm.workspace_id = cloud.audit_events.workspace_id' in policy

    def test_n_cw_06_share_links_denied(self):
        """N-CW-06: User A reads workspace B's share links (not a member) → denied."""
        policy = _extract_policy('share_link_member_read', _RLS_NORM)
        assert 'workspace_members' in policy
        assert 'auth.uid()' in policy
        assert 'wm.workspace_id = cloud.file_share_links.workspace_id' in policy


# =====================================================================
# N-ST: Status-Based Access Denial
# =====================================================================
# Users whose membership status is NOT 'active' must be denied access.
# This covers removed members and pending (not-yet-accepted) members.
# =====================================================================


class TestStatusBasedAccessDenial:
    """N-ST-01 through N-ST-04: non-active members are denied."""

    def test_n_st_01_removed_member_workspace_denied(self):
        """N-ST-01: Removed member reads workspace record → denied."""
        policy = _extract_policy('workspace_member_read', _RLS_NORM)
        assert "wm.status = 'active'" in policy, (
            'workspace_member_read must require active status'
        )

    def test_n_st_02_pending_member_workspace_denied(self):
        """N-ST-02: Pending member reads workspace record → denied.

        The workspace_member_read policy requires status='active'.
        A pending member has status='pending', so the EXISTS subquery
        returns false.  The separate member_read_own_pending policy
        only covers workspace_members table, not workspaces.
        """
        policy = _extract_policy('workspace_member_read', _RLS_NORM)
        assert "wm.status = 'active'" in policy
        # Confirm member_read_own_pending is scoped to workspace_members only
        pending = _extract_policy('member_read_own_pending', _RLS_NORM)
        assert 'on cloud.workspace_members' in pending
        assert 'on cloud.workspaces' not in pending

    def test_n_st_03_removed_member_member_list_denied(self):
        """N-ST-03: Removed member reads member list → denied."""
        policy = _extract_policy('member_read_own_workspace', _RLS_NORM)
        assert ".status = 'active'" in policy

    def test_n_st_04_removed_member_runtime_denied(self):
        """N-ST-04: Removed member reads runtime status → denied."""
        policy = _extract_policy('runtime_member_read', _RLS_NORM)
        assert "wm.status = 'active'" in policy

    def test_status_check_on_all_membership_policies(self):
        """All policies using workspace_members join must check active status."""
        # Collect all policy blocks that reference workspace_members wm
        policy_blocks = re.findall(
            r'create policy \w+ on [\w.]+ for (?:select|update)[^;]+;',
            _RLS_NORM,
        )
        for block in policy_blocks:
            if 'member_read_own_pending' in block:
                # This policy intentionally checks pending status
                continue
            if 'workspace_members wm' in block:
                assert "wm.status = 'active'" in block, (
                    f'Policy with wm join missing active check: {block[:100]}'
                )
            elif 'workspace_members self' in block:
                assert ".status = 'active'" in block, (
                    f'Policy with self join missing active check: {block[:100]}'
                )


# =====================================================================
# N-RL: Role-Based Mutation Denial
# =====================================================================
# Certain operations require admin role.  Non-admin members must be
# denied even if they have active membership.
# =====================================================================


class TestRoleBasedMutationDenial:
    """N-RL-01 through N-RL-04: non-admin members denied."""

    def test_n_rl_01_non_admin_workspace_update_denied(self):
        """N-RL-01: Non-admin tries to update workspace name → denied."""
        policy = _extract_policy('workspace_member_update', _RLS_NORM)
        assert "wm.role = 'admin'" in policy
        # Both USING and WITH CHECK must require admin
        assert policy.count("wm.role = 'admin'") >= 2, (
            'Both USING and WITH CHECK must require admin role'
        )

    def test_n_rl_02_non_admin_audit_read_denied(self):
        """N-RL-02: Non-admin reads audit events → denied."""
        policy = _extract_policy('audit_member_read', _RLS_NORM)
        assert "wm.role = 'admin'" in policy

    def test_n_rl_03_non_admin_share_links_read_denied(self):
        """N-RL-03: Non-admin reads share links → denied."""
        policy = _extract_policy('share_link_member_read', _RLS_NORM)
        assert "wm.role = 'admin'" in policy

    def test_n_rl_04_non_admin_share_link_revoke_denied(self):
        """N-RL-04: Non-admin tries to revoke share link → denied."""
        policy = _extract_policy('share_link_member_revoke', _RLS_NORM)
        assert "wm.role = 'admin'" in policy
        # Both USING and WITH CHECK
        assert policy.count("wm.role = 'admin'") >= 2

    def test_admin_check_accompanies_active_check(self):
        """Admin-gated policies must also require active membership."""
        for name in ('audit_member_read', 'share_link_member_read',
                      'share_link_member_revoke', 'workspace_member_update'):
            policy = _extract_policy(name, _RLS_NORM)
            assert "wm.status = 'active'" in policy, (
                f'{name} requires admin but missing active status check'
            )


# =====================================================================
# N-MU: Authenticated User Mutation Denial
# =====================================================================
# Authenticated users must NOT have INSERT or DELETE policies on any
# table.  All data mutations (except admin UPDATE on workspaces and
# share_links) require service_role which bypasses RLS entirely.
# =====================================================================


class TestAuthenticatedUserMutationDenial:
    """N-MU-01 through N-MU-06: users cannot INSERT/DELETE."""

    def test_n_mu_01_user_insert_workspaces_denied(self):
        """N-MU-01: User tries INSERT on workspaces → no policy exists."""
        inserts = re.findall(
            r'create policy \w+ on cloud\.workspaces for insert', _RLS_NORM
        )
        assert len(inserts) == 0

    def test_n_mu_02_user_insert_members_denied(self):
        """N-MU-02: User tries INSERT on workspace_members → no policy."""
        inserts = re.findall(
            r'create policy \w+ on cloud\.workspace_members for insert', _RLS_NORM
        )
        assert len(inserts) == 0

    def test_n_mu_03_user_update_runtime_denied(self):
        """N-MU-03: User tries UPDATE on workspace_runtime → no policy."""
        updates = re.findall(
            r'create policy \w+ on cloud\.workspace_runtime for update', _RLS_NORM
        )
        assert len(updates) == 0

    def test_n_mu_04_user_insert_provision_jobs_denied(self):
        """N-MU-04: User tries INSERT on provision_jobs → no policy."""
        inserts = re.findall(
            r'create policy \w+ on cloud\.workspace_provision_jobs for insert', _RLS_NORM
        )
        assert len(inserts) == 0

    def test_n_mu_05_user_insert_audit_events_denied(self):
        """N-MU-05: User tries INSERT on audit_events → no policy."""
        inserts = re.findall(
            r'create policy \w+ on cloud\.audit_events for insert', _RLS_NORM
        )
        assert len(inserts) == 0

    def test_n_mu_06_user_insert_share_links_denied(self):
        """N-MU-06: User tries INSERT on file_share_links → no policy."""
        inserts = re.findall(
            r'create policy \w+ on cloud\.file_share_links for insert', _RLS_NORM
        )
        assert len(inserts) == 0

    def test_no_delete_policies_on_any_table(self):
        """No DELETE policy should exist for any table."""
        for table in _V0_TABLES:
            deletes = re.findall(
                rf'create policy \w+ on {re.escape(table)} for delete', _RLS_NORM
            )
            assert len(deletes) == 0, f'Unexpected DELETE policy on {table}'

    def test_no_insert_policies_on_any_table(self):
        """No INSERT policy should exist for any table."""
        for table in _V0_TABLES:
            inserts = re.findall(
                rf'create policy \w+ on {re.escape(table)} for insert', _RLS_NORM
            )
            assert len(inserts) == 0, f'Unexpected INSERT policy on {table}'

    def test_only_allowed_update_policies(self):
        """Only workspaces and file_share_links should have UPDATE policies."""
        allowed = {'cloud.workspaces', 'cloud.file_share_links'}
        for table in _V0_TABLES:
            updates = re.findall(
                rf'create policy \w+ on {re.escape(table)} for update', _RLS_NORM
            )
            if table in allowed:
                # These are expected (admin-only)
                continue
            assert len(updates) == 0, (
                f'Unexpected UPDATE policy on {table}'
            )


# =====================================================================
# N-PI: Pending Invite Isolation
# =====================================================================
# A user should only see pending invites that match their own email
# (case-insensitive).  They must NOT see invites for other users.
# =====================================================================


class TestPendingInviteIsolation:
    """N-PI-01 and N-PI-02: pending invite email scoping."""

    def test_n_pi_01_user_a_cannot_read_user_b_pending_invite(self):
        """N-PI-01: User A reads pending invite for User B's email → denied.

        The member_read_own_pending policy requires:
          status = 'pending' AND lower(email) = lower(auth.jwt() ->> 'email')
        So a different user's email won't match.
        """
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        # Must match email from JWT token
        assert "auth.jwt()" in policy
        assert "'email'" in policy
        # Must filter to pending status only
        assert "'pending'" in policy

    def test_n_pi_02_pending_invite_case_insensitive(self):
        """N-PI-02: Pending invite visible only to matching email (case-insensitive)."""
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        # Both sides of the comparison must use lower()
        lower_count = policy.count('lower(')
        assert lower_count >= 2, (
            f'Expected lower() on both sides of email comparison, found {lower_count} uses'
        )

    def test_pending_policy_scoped_to_workspace_members_only(self):
        """Pending invite policy must only apply to workspace_members table."""
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        assert 'on cloud.workspace_members' in policy

    def test_pending_policy_is_select_only(self):
        """Pending invite policy must be FOR SELECT only (no mutations)."""
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        assert 'for select' in policy

    def test_pending_policy_does_not_expose_active_members(self):
        """The pending policy must only show rows with status='pending'.

        Without the status='pending' filter, users could bypass the
        member_read_own_workspace policy by matching email alone.
        """
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        assert "cloud.workspace_members.status = 'pending'" in policy


# =====================================================================
# N-AU: Audit Immutability
# =====================================================================
# Even service_role must not UPDATE or DELETE audit_events.
# This is enforced by BEFORE triggers that RAISE EXCEPTION.
# =====================================================================


class TestAuditImmutability:
    """N-AU-01 and N-AU-02: audit events are immutable."""

    def test_n_au_01_update_trigger_blocks_service_role(self):
        """N-AU-01: Service role tries UPDATE on audit_events → denied (trigger)."""
        assert 'trg_audit_events_no_update' in _SCHEMA_NORM
        # Trigger must be BEFORE UPDATE (prevents the operation)
        assert 'before update on cloud.audit_events' in _SCHEMA_NORM
        # Must execute the immutability function
        assert 'audit_events_immutable()' in _SCHEMA_NORM

    def test_n_au_02_delete_trigger_blocks_service_role(self):
        """N-AU-02: Service role tries DELETE on audit_events → denied (trigger)."""
        assert 'trg_audit_events_no_delete' in _SCHEMA_NORM
        assert 'before delete on cloud.audit_events' in _SCHEMA_NORM
        assert 'audit_events_immutable()' in _SCHEMA_NORM

    def test_immutability_function_raises_exception(self):
        """The trigger function must RAISE EXCEPTION to block the operation."""
        assert "raise exception 'audit_events is immutable" in _SCHEMA_NORM

    def test_immutability_triggers_are_row_level(self):
        """Triggers must fire FOR EACH ROW (not statement-level)."""
        # Find the trigger creation statements
        for trigger in ('trg_audit_events_no_update', 'trg_audit_events_no_delete'):
            pattern = rf'create trigger {trigger}\s+before \w+ on cloud\.audit_events\s+for each row'
            assert re.search(pattern, _SCHEMA_NORM), (
                f'{trigger} must be FOR EACH ROW'
            )

    def test_no_update_policy_on_audit_events(self):
        """No RLS UPDATE policy exists for audit_events (belt + suspenders)."""
        updates = re.findall(
            r'create policy \w+ on cloud\.audit_events for update', _RLS_NORM
        )
        assert len(updates) == 0

    def test_no_delete_policy_on_audit_events(self):
        """No RLS DELETE policy exists for audit_events."""
        deletes = re.findall(
            r'create policy \w+ on cloud\.audit_events for delete', _RLS_NORM
        )
        assert len(deletes) == 0


# =====================================================================
# Cross-cutting: auth.uid() presence
# =====================================================================


class TestAuthUidPresence:
    """All membership-gated policies must use auth.uid() to bind the
    check to the requesting user's identity."""

    @pytest.mark.parametrize('policy_name', [
        'workspace_member_read',
        'workspace_member_update',
        'member_read_own_workspace',
        'runtime_member_read',
        'provision_job_member_read',
        'audit_member_read',
        'share_link_member_read',
        'share_link_member_revoke',
    ])
    def test_policy_uses_auth_uid(self, policy_name: str):
        policy = _extract_policy(policy_name, _RLS_NORM)
        assert 'auth.uid()' in policy, (
            f'{policy_name} must use auth.uid() for user identity binding'
        )

    def test_pending_invite_uses_auth_jwt(self):
        """Pending invite uses auth.jwt() instead of auth.uid()."""
        policy = _extract_policy('member_read_own_pending', _RLS_NORM)
        assert 'auth.jwt()' in policy


# =====================================================================
# Cross-cutting: workspace_id correlation
# =====================================================================


class TestWorkspaceIdCorrelation:
    """Every membership-join policy must correlate workspace_id between
    the target table and the workspace_members subquery.  Without this,
    a member of workspace A could read workspace B's data."""

    _TABLE_POLICY_MAP = {
        'cloud.workspaces': ('workspace_member_read', 'cloud.workspaces.id'),
        'cloud.workspace_runtime': ('runtime_member_read', 'cloud.workspace_runtime.workspace_id'),
        'cloud.workspace_provision_jobs': ('provision_job_member_read', 'cloud.workspace_provision_jobs.workspace_id'),
        'cloud.audit_events': ('audit_member_read', 'cloud.audit_events.workspace_id'),
        'cloud.file_share_links': ('share_link_member_read', 'cloud.file_share_links.workspace_id'),
    }

    @pytest.mark.parametrize(
        'table,policy_name,expected_correlation',
        [(t, p, c) for t, (p, c) in _TABLE_POLICY_MAP.items()],
        ids=[t.split('.')[-1] for t in _TABLE_POLICY_MAP],
    )
    def test_workspace_id_is_correlated(self, table, policy_name, expected_correlation):
        policy = _extract_policy(policy_name, _RLS_NORM)
        assert f'wm.workspace_id = {expected_correlation}' in policy, (
            f'{policy_name} must correlate wm.workspace_id to {expected_correlation}'
        )

    def test_workspace_members_self_join_correlation(self):
        """member_read_own_workspace must correlate on workspace_id."""
        policy = _extract_policy('member_read_own_workspace', _RLS_NORM)
        assert 'self.workspace_id = cloud.workspace_members.workspace_id' in policy
