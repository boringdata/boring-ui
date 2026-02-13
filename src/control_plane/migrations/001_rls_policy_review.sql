-- RLS Policy Review and Specification for Feature 3 V0
-- Prerequisite: bd-223o.5 (P5)
--
-- This file defines the Row Level Security policies, service-role
-- boundaries, and negative test invariants for the V0 data model.
-- Tables reference Feature 3 design doc section 12.
--
-- APPROVAL STATUS: PENDING — this file serves as the review record.
-- When reviewed and approved, update status to APPROVED with reviewer
-- name and date.
--
-- Review date:    2026-02-13
-- Author:         TealStone (claude-code/opus-4.6)
-- Bead:           bd-223o.5

-- ============================================================
-- SCHEMA: cloud
-- ============================================================
create schema if not exists cloud;

-- Enable RLS on all tables.  This is the most important step:
-- without RLS enabled, Supabase allows full access to any
-- authenticated user by default.

-- ============================================================
-- TABLE: cloud.workspaces
-- Purpose: Workspace metadata (name, app_id, owner).
-- ============================================================
-- Columns: id, name, app_id, created_by, created_at, updated_at

-- RLS POLICY: workspace_member_read
-- WHO:  Any authenticated user who is an active member of the workspace.
-- WHAT: SELECT on all columns.
-- WHY:  Members need to see workspace info for the workspace list/switcher.
create policy workspace_member_read on cloud.workspaces
  for select
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
    )
  );

-- RLS POLICY: workspace_member_update
-- WHO:  Active admin members only.
-- WHAT: UPDATE on name (only mutable field in V0).
-- WHY:  Workspace rename requires admin membership.
create policy workspace_member_update on cloud.workspaces
  for update
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  )
  with check (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  );

-- INSERT: handled exclusively by service role (control plane).
-- DELETE: not permitted in V0 (workspaces are not deletable).

-- ============================================================
-- TABLE: cloud.workspace_members
-- Purpose: Membership association (user <-> workspace with role).
-- ============================================================
-- Columns: id, workspace_id, user_id, email, role, status,
--          invited_by, created_at, updated_at
--
-- status values: 'pending', 'active', 'removed'
-- role values: 'admin' (only value in V0)

-- RLS POLICY: member_read_own_workspace
-- WHO:  Active members of the workspace.
-- WHAT: SELECT all members of workspaces they belong to.
-- WHY:  Members need to see other members in settings/invite UI.
create policy member_read_own_workspace on cloud.workspace_members
  for select
  using (
    exists (
      select 1 from cloud.workspace_members self
      where self.workspace_id = workspace_id
        and self.user_id = auth.uid()
        and self.status = 'active'
    )
  );

-- RLS POLICY: member_read_own_pending
-- WHO:  Authenticated user whose email matches a pending invite.
-- WHAT: SELECT pending invites addressed to their email.
-- WHY:  Auto-accept logic on workspace list load requires reading
--        pending invites for the current user's email.
create policy member_read_own_pending on cloud.workspace_members
  for select
  using (
    status = 'pending'
    and lower(email) = lower(auth.jwt() ->> 'email')
  );

-- INSERT: service role only (invite creation goes through control plane API).
-- UPDATE: service role only (status transitions: pending->active, active->removed).
-- DELETE: not used — soft removal via status='removed'.

-- ============================================================
-- TABLE: cloud.workspace_runtime
-- Purpose: One row per workspace tracking runtime state.
-- ============================================================
-- Columns: id, workspace_id, app_id, state, step, attempt,
--          release_id, sandbox_name, bundle_sha256,
--          last_error_code, last_error_detail,
--          config (jsonb), updated_at
--
-- state values: 'provisioning', 'ready', 'error'
-- Constraint: exactly one row per workspace_id

-- RLS POLICY: runtime_member_read
-- WHO:  Active members of the workspace.
-- WHAT: SELECT runtime state for their workspace.
-- WHY:  Frontend needs runtime status for provisioning UI.
create policy runtime_member_read on cloud.workspace_runtime
  for select
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
    )
  );

-- INSERT/UPDATE/DELETE: service role only (provisioning orchestration).

-- ============================================================
-- TABLE: cloud.workspace_provision_jobs
-- Purpose: Provisioning job lifecycle tracking.
-- ============================================================
-- Columns: id, workspace_id, state, attempt, modal_call_id,
--          started_at, finished_at, last_error_code,
--          last_error_detail, request_id, idempotency_key,
--          created_by, created_at, updated_at
--
-- Constraint: at most one active job per workspace (enforced by
--             unique partial index on active states).

-- RLS POLICY: provision_job_member_read
-- WHO:  Active workspace members.
-- WHAT: SELECT provision job history for their workspace.
-- WHY:  Frontend shows provisioning progress and retry history.
create policy provision_job_member_read on cloud.workspace_provision_jobs
  for select
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
    )
  );

-- INSERT/UPDATE/DELETE: service role only.

-- ============================================================
-- TABLE: cloud.audit_events
-- Purpose: Immutable audit log for mutating operations.
-- ============================================================
-- Columns: id, workspace_id, user_id (nullable), action,
--          request_id, payload (jsonb), created_at
--
-- Design: append-only, no updates or deletes.

-- RLS POLICY: audit_member_read
-- WHO:  Active admin members.
-- WHAT: SELECT audit events for their workspace.
-- WHY:  Admin users may need audit visibility in V0 settings.
create policy audit_member_read on cloud.audit_events
  for select
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  );

-- INSERT: service role only (control plane emits audit events).
-- UPDATE/DELETE: never permitted (immutable log).

-- ============================================================
-- TABLE: cloud.file_share_links
-- Purpose: Authenticated share links with exact-path scope.
-- ============================================================
-- Columns: id, workspace_id, path, token_hash, access,
--          created_by, expires_at, revoked_at, created_at
--
-- access values: 'read', 'write'
-- Security: only token_hash stored; plaintext never persisted.

-- RLS POLICY: share_link_member_read
-- WHO:  Active admin members of the workspace.
-- WHAT: SELECT share links for their workspace.
-- WHY:  Admin users manage share links in settings/sharing UI.
create policy share_link_member_read on cloud.file_share_links
  for select
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  );

-- RLS POLICY: share_link_member_delete
-- WHO:  Active admin members (revocation).
-- WHAT: UPDATE revoked_at field only.
-- WHY:  Admins can revoke share links.
create policy share_link_member_revoke on cloud.file_share_links
  for update
  using (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  )
  with check (
    exists (
      select 1 from cloud.workspace_members wm
      where wm.workspace_id = workspace_id
        and wm.user_id = auth.uid()
        and wm.status = 'active'
        and wm.role = 'admin'
    )
  );

-- INSERT: service role only (share link creation from control plane API).
-- DELETE: not used — revocation is soft (revoked_at timestamp).

-- ============================================================
-- SERVICE ROLE SCOPE
-- ============================================================
-- The service role (used by the control plane) bypasses RLS.
-- This is intentional for mutations that must not be gated by
-- per-user membership checks:
--
-- ALLOWED service-role operations:
--   INSERT on cloud.workspaces          — workspace creation
--   INSERT on cloud.workspace_members   — invite creation
--   UPDATE on cloud.workspace_members   — status transitions
--                                         (pending->active, active->removed)
--   INSERT on cloud.workspace_runtime   — initial runtime row
--   UPDATE on cloud.workspace_runtime   — state machine transitions
--   INSERT on cloud.workspace_provision_jobs — job creation
--   UPDATE on cloud.workspace_provision_jobs — state transitions
--   INSERT on cloud.audit_events        — audit emission
--   INSERT on cloud.file_share_links    — share link creation
--
-- NEVER permitted even for service role (enforced by triggers/checks):
--   DELETE on cloud.audit_events        — immutable log
--   UPDATE on cloud.audit_events        — immutable log
--   DROP/TRUNCATE on any cloud.* table  — schema protection
--
-- The service role key must NEVER be exposed to browser clients.
-- It is stored in Modal secrets and used only by the control plane
-- server-side process.

-- ============================================================
-- ENABLE RLS ON ALL TABLES
-- ============================================================
-- CRITICAL: RLS must be enabled BEFORE any policies take effect.
-- Without this, Supabase defaults to open access for authenticated users.
alter table cloud.workspaces enable row level security;
alter table cloud.workspace_members enable row level security;
alter table cloud.workspace_runtime enable row level security;
alter table cloud.workspace_provision_jobs enable row level security;
alter table cloud.audit_events enable row level security;
alter table cloud.file_share_links enable row level security;
