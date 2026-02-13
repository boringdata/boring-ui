-- Migration 003: Feature 3 V0 RLS Policies
-- Bead: bd-1joj.11 (MIG0)
--
-- Enables Row Level Security on all cloud.* tables and creates
-- policies for member-scoped reads and service-role writes.
--
-- RLS baseline (from Feature doc section 12):
--   1. Members can read their workspace records.
--   2. Active workspace membership (admin in V0) required for membership mutation.
--   3. Provisioning/internal mutations via service role.
--
-- Policy naming convention: {table}_{operation}_{scope}

BEGIN;

-- ── Enable RLS on all tables ────────────────────────────────────
ALTER TABLE cloud.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud.workspace_runtime ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud.workspace_provision_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud.file_share_links ENABLE ROW LEVEL SECURITY;

-- ── Helper: check if user is an active member of a workspace ────
-- (Used by multiple policies below)
-- Note: auth.uid() returns the authenticated Supabase user's UUID.

-- ── 1. Workspaces policies ──────────────────────────────────────

-- Members can read workspaces they belong to
CREATE POLICY workspaces_select_member ON cloud.workspaces
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm
            WHERE wm.workspace_id = id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
        OR owner_id = auth.uid()
    );

-- Service role can do everything (provisioning, admin ops)
CREATE POLICY workspaces_all_service ON cloud.workspaces
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── 2. Workspace Members policies ───────────────────────────────

-- Active members can read membership list for their workspaces
CREATE POLICY members_select_member ON cloud.workspace_members
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm2
            WHERE wm2.workspace_id = workspace_id
              AND wm2.user_id = auth.uid()
              AND wm2.status = 'active'
        )
    );

-- Service role can manage all memberships
CREATE POLICY members_all_service ON cloud.workspace_members
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── 3. Workspace Runtime policies ───────────────────────────────

-- Members can read runtime status for their workspaces
CREATE POLICY runtime_select_member ON cloud.workspace_runtime
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm
            WHERE wm.workspace_id = workspace_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

-- Service role manages runtime state (provisioning system)
CREATE POLICY runtime_all_service ON cloud.workspace_runtime
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── 4. Provisioning Jobs policies ───────────────────────────────

-- Members can read provisioning jobs for their workspaces
CREATE POLICY jobs_select_member ON cloud.workspace_provision_jobs
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm
            WHERE wm.workspace_id = workspace_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

-- Service role manages provisioning jobs
CREATE POLICY jobs_all_service ON cloud.workspace_provision_jobs
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── 5. Audit Events policies ────────────────────────────────────

-- Members can read audit events for their workspaces
CREATE POLICY audit_select_member ON cloud.audit_events
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm
            WHERE wm.workspace_id = workspace_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

-- Service role writes audit events
CREATE POLICY audit_all_service ON cloud.audit_events
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── 6. File Share Links policies ────────────────────────────────

-- Members can read share links for their workspaces
CREATE POLICY shares_select_member ON cloud.file_share_links
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM cloud.workspace_members wm
            WHERE wm.workspace_id = workspace_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

-- Service role manages share links
CREATE POLICY shares_all_service ON cloud.file_share_links
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

COMMIT;
