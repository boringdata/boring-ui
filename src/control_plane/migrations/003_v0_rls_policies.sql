-- V0 RLS Policy Implementation
-- Bead: bd-223o.6.2 (A2)
--
-- Implements all Row Level Security policies from the P5 review
-- (001_rls_policy_review.sql). This migration must run AFTER
-- 002_v0_core_schema.sql (tables and RLS enablement).
--
-- Idempotency: DROP POLICY IF EXISTS before each CREATE POLICY.
--
-- Service-role operations bypass RLS by default in Supabase.
-- No explicit grant is needed — the service_role key inherits
-- the postgres role which bypasses RLS.

-- ============================================================
-- cloud.workspaces POLICIES
-- ============================================================

-- Active members can read workspaces they belong to.
drop policy if exists workspace_member_read on cloud.workspaces;
create policy workspace_member_read on cloud.workspaces
    for select
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.workspaces.id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
        )
    );

-- Active admins can update workspace name.
drop policy if exists workspace_member_update on cloud.workspaces;
create policy workspace_member_update on cloud.workspaces
    for update
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.workspaces.id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    )
    with check (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.workspaces.id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    );

-- No INSERT/DELETE policies for authenticated users.
-- Workspace creation is service-role only (control plane).
-- Workspace deletion is not supported in V0.

-- ============================================================
-- cloud.workspace_members POLICIES
-- ============================================================

-- Active members can read all members of their workspace.
drop policy if exists member_read_own_workspace on cloud.workspace_members;
create policy member_read_own_workspace on cloud.workspace_members
    for select
    using (
        exists (
            select 1 from cloud.workspace_members self
            where self.workspace_id = cloud.workspace_members.workspace_id
              and self.user_id = auth.uid()
              and self.status = 'active'
        )
    );

-- Authenticated users can read pending invites matching their email.
-- This enables auto-accept logic on workspace list load.
drop policy if exists member_read_own_pending on cloud.workspace_members;
create policy member_read_own_pending on cloud.workspace_members
    for select
    using (
        cloud.workspace_members.status = 'pending'
        and lower(cloud.workspace_members.email) = lower(auth.jwt() ->> 'email')
    );

-- No INSERT/UPDATE/DELETE policies for authenticated users.
-- Invite creation and status transitions are service-role only.

-- ============================================================
-- cloud.workspace_runtime POLICIES
-- ============================================================

-- Active members can read runtime status for their workspace.
drop policy if exists runtime_member_read on cloud.workspace_runtime;
create policy runtime_member_read on cloud.workspace_runtime
    for select
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.workspace_runtime.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
        )
    );

-- No INSERT/UPDATE/DELETE policies for authenticated users.
-- All runtime mutations are service-role only (provisioning).

-- ============================================================
-- cloud.workspace_provision_jobs POLICIES
-- ============================================================

-- Active members can read provision job history for their workspace.
drop policy if exists provision_job_member_read on cloud.workspace_provision_jobs;
create policy provision_job_member_read on cloud.workspace_provision_jobs
    for select
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.workspace_provision_jobs.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
        )
    );

-- No INSERT/UPDATE/DELETE policies for authenticated users.
-- All provision job mutations are service-role only.

-- ============================================================
-- cloud.audit_events POLICIES
-- ============================================================

-- Only active admins can read audit events for their workspace.
drop policy if exists audit_member_read on cloud.audit_events;
create policy audit_member_read on cloud.audit_events
    for select
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.audit_events.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    );

-- No INSERT/UPDATE/DELETE policies for authenticated users.
-- Audit emission is service-role only.
-- UPDATE/DELETE are also blocked by triggers (immutability).

-- ============================================================
-- cloud.file_share_links POLICIES
-- ============================================================

-- Active admins can read share links for their workspace.
drop policy if exists share_link_member_read on cloud.file_share_links;
create policy share_link_member_read on cloud.file_share_links
    for select
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.file_share_links.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    );

-- Active admins can revoke share links (set revoked_at).
drop policy if exists share_link_member_revoke on cloud.file_share_links;
create policy share_link_member_revoke on cloud.file_share_links
    for update
    using (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.file_share_links.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    )
    with check (
        exists (
            select 1 from cloud.workspace_members wm
            where wm.workspace_id = cloud.file_share_links.workspace_id
              and wm.user_id = auth.uid()
              and wm.status = 'active'
              and wm.role = 'admin'
        )
    );

-- No INSERT/DELETE policies for authenticated users.
-- Share link creation is service-role only.
-- Share link deletion is not used (soft revoke via revoked_at).
