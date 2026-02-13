-- Migration 002: Feature 3 V0 Core Schema
-- Bead: bd-1joj.11 (MIG0)
--
-- Creates the cloud schema and all 6 core tables for the
-- control-plane workspace management system.
--
-- Tables:
--   cloud.workspaces
--   cloud.workspace_members
--   cloud.workspace_runtime
--   cloud.workspace_provision_jobs
--   cloud.audit_events
--   cloud.file_share_links
--
-- Reference: Feature doc sections 12, 12.1, 11.1

BEGIN;

-- ── Schema ──────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS cloud;

-- ── 1. Workspaces ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.workspaces (
    id              text PRIMARY KEY DEFAULT 'ws_' || substr(gen_random_uuid()::text, 1, 12),
    app_id          text NOT NULL DEFAULT 'boring-ui',
    name            text NOT NULL,
    owner_id        uuid NOT NULL,  -- references auth.users(id)
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_workspaces_app_id
    ON cloud.workspaces(app_id);

CREATE INDEX IF NOT EXISTS ix_workspaces_owner_id
    ON cloud.workspaces(owner_id);

-- ── 2. Workspace Members ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.workspace_members (
    id              text PRIMARY KEY DEFAULT 'mem_' || substr(gen_random_uuid()::text, 1, 12),
    workspace_id    text NOT NULL REFERENCES cloud.workspaces(id) ON DELETE CASCADE,
    user_id         uuid,           -- bound on first login (nullable for pending invites)
    email           text NOT NULL,
    role            text NOT NULL DEFAULT 'admin' CHECK (role IN ('admin')),
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'removed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Unique constraint: one active/pending membership per email per workspace
CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_members_email
    ON cloud.workspace_members(workspace_id, lower(email))
    WHERE status IN ('pending', 'active');

CREATE INDEX IF NOT EXISTS ix_workspace_members_user_id
    ON cloud.workspace_members(user_id)
    WHERE user_id IS NOT NULL;

-- ── 3. Workspace Runtime ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.workspace_runtime (
    workspace_id    text PRIMARY KEY REFERENCES cloud.workspaces(id) ON DELETE CASCADE,
    app_id          text NOT NULL DEFAULT 'boring-ui',
    state           text NOT NULL DEFAULT 'provisioning'
                    CHECK (state IN ('provisioning', 'ready', 'error')),
    release_id      text,
    sandbox_name    text,
    bundle_sha256   text,
    last_error_code text,
    last_error_detail text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_workspace_runtime_app_id
    ON cloud.workspace_runtime(app_id);

CREATE INDEX IF NOT EXISTS ix_workspace_runtime_app_release
    ON cloud.workspace_runtime(app_id, release_id);

CREATE INDEX IF NOT EXISTS ix_workspace_runtime_sandbox_name
    ON cloud.workspace_runtime(sandbox_name);

-- ── 4. Provisioning Jobs ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.workspace_provision_jobs (
    id              text PRIMARY KEY DEFAULT 'job_' || substr(gen_random_uuid()::text, 1, 12),
    workspace_id    text NOT NULL REFERENCES cloud.workspaces(id) ON DELETE CASCADE,
    state           text NOT NULL DEFAULT 'queued'
                    CHECK (state IN ('queued', 'release_resolve', 'creating_sandbox',
                                     'uploading_artifact', 'bootstrapping', 'health_check',
                                     'ready', 'error')),
    step            text,
    attempt         integer NOT NULL DEFAULT 1,
    modal_call_id   text,
    idempotency_key text,
    last_error_code text,
    last_error_detail text,
    request_id      text,
    created_by      uuid,           -- references auth.users(id)
    started_at      timestamptz,
    finished_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Single active job per workspace (jobs not in terminal state)
CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_jobs_active
    ON cloud.workspace_provision_jobs(workspace_id)
    WHERE state IN ('queued', 'release_resolve', 'creating_sandbox',
                    'uploading_artifact', 'bootstrapping', 'health_check');

-- Client idempotency dedup
CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_jobs_idempotency
    ON cloud.workspace_provision_jobs(workspace_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ── 5. Audit Events ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.audit_events (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id    text NOT NULL,
    user_id         uuid,           -- nullable for system actor
    action          text NOT NULL,
    request_id      text,
    payload         jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Correlation index: workspace + request-ID + time
CREATE INDEX IF NOT EXISTS ix_audit_events_workspace_request
    ON cloud.audit_events(workspace_id, request_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_events_workspace_action
    ON cloud.audit_events(workspace_id, action, created_at DESC);

-- ── 6. File Share Links ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud.file_share_links (
    id              text PRIMARY KEY DEFAULT 'shr_' || substr(gen_random_uuid()::text, 1, 12),
    workspace_id    text NOT NULL REFERENCES cloud.workspaces(id) ON DELETE CASCADE,
    token_hash      text NOT NULL,  -- only hash stored, never plaintext
    path            text NOT NULL,  -- normalized absolute workspace-relative path
    access          text NOT NULL DEFAULT 'read' CHECK (access IN ('read', 'write')),
    created_by      uuid NOT NULL,  -- references auth.users(id)
    expires_at      timestamptz NOT NULL,
    revoked_at      timestamptz,    -- soft revocation
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_file_share_links_token_hash
    ON cloud.file_share_links(token_hash);

CREATE INDEX IF NOT EXISTS ix_file_share_links_workspace_path
    ON cloud.file_share_links(workspace_id, path);

CREATE INDEX IF NOT EXISTS ix_file_share_links_expires
    ON cloud.file_share_links(expires_at)
    WHERE revoked_at IS NULL;

COMMIT;
