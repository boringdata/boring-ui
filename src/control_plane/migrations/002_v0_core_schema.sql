-- V0 Core Schema Migration
-- Bead: bd-223o.6.1 (A1)
--
-- Creates all tables, constraints, indexes, and DDL additions
-- required for the Feature 3 V0 data model (design doc section 12).
--
-- This migration is designed to be idempotent: safe to re-run
-- on a database where partial application occurred.
--
-- Prerequisites: bd-223o.5 (P5) RLS policy review approved.

-- ============================================================
-- SCHEMA
-- ============================================================
create schema if not exists cloud;

-- ============================================================
-- TABLE: cloud.workspaces
-- ============================================================
create table if not exists cloud.workspaces (
    id              text primary key,
    name            text not null,
    app_id          text not null default 'boring-ui',
    created_by      uuid not null references auth.users(id),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists ix_workspaces_app_id
    on cloud.workspaces(app_id);

create index if not exists ix_workspaces_created_by
    on cloud.workspaces(created_by);

comment on table cloud.workspaces is
    'Workspace metadata. Each workspace is scoped to an app_id.';

-- ============================================================
-- TABLE: cloud.workspace_members
-- ============================================================
create table if not exists cloud.workspace_members (
    id              bigint generated always as identity primary key,
    workspace_id    text not null references cloud.workspaces(id),
    user_id         uuid references auth.users(id),
    email           text not null,
    role            text not null default 'admin'
                    check (role in ('admin')),
    status          text not null default 'pending'
                    check (status in ('pending', 'active', 'removed')),
    invited_by      uuid references auth.users(id),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Prevent duplicate pending/active invites for same workspace+email.
create unique index if not exists ux_workspace_members_active_email
    on cloud.workspace_members(workspace_id, lower(email))
    where status in ('pending', 'active');

create index if not exists ix_workspace_members_user_id
    on cloud.workspace_members(user_id)
    where user_id is not null;

create index if not exists ix_workspace_members_email
    on cloud.workspace_members(lower(email));

comment on table cloud.workspace_members is
    'Workspace membership with invite lifecycle. V0 uses admin role only.';

-- ============================================================
-- TABLE: cloud.workspace_runtime
-- ============================================================
create table if not exists cloud.workspace_runtime (
    id              bigint generated always as identity primary key,
    workspace_id    text not null references cloud.workspaces(id) unique,
    app_id          text not null default 'boring-ui',
    state           text not null default 'provisioning'
                    check (state in ('provisioning', 'ready', 'error')),
    step            text,
    attempt         int not null default 1,
    release_id      text,
    sandbox_name    text,
    bundle_sha256   text,
    last_error_code text,
    last_error_detail text,
    config          jsonb not null default '{}'::jsonb,
    updated_at      timestamptz not null default now()
);

-- Exactly one runtime row per workspace (enforced by unique constraint above).
create index if not exists ix_workspace_runtime_app_id
    on cloud.workspace_runtime(app_id);

create index if not exists ix_workspace_runtime_app_release
    on cloud.workspace_runtime(app_id, release_id);

create index if not exists ix_workspace_runtime_sandbox_name
    on cloud.workspace_runtime(sandbox_name);

comment on table cloud.workspace_runtime is
    'One row per workspace tracking runtime state, release deployment metadata, and sandbox identity.';

-- ============================================================
-- TABLE: cloud.workspace_provision_jobs
-- ============================================================
create table if not exists cloud.workspace_provision_jobs (
    id              bigint generated always as identity primary key,
    workspace_id    text not null references cloud.workspaces(id),
    state           text not null default 'queued'
                    check (state in (
                        'queued', 'release_resolve', 'creating_sandbox',
                        'uploading_artifact', 'bootstrapping', 'health_check',
                        'ready', 'error'
                    )),
    attempt         int not null default 1,
    modal_call_id   text,
    started_at      timestamptz,
    finished_at     timestamptz,
    last_error_code text,
    last_error_detail text,
    request_id      text,
    idempotency_key text,
    created_by      uuid references auth.users(id),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- At most one active provisioning job per workspace (design doc section 9.2).
create unique index if not exists ux_workspace_jobs_active
    on cloud.workspace_provision_jobs(workspace_id)
    where state in (
        'queued', 'release_resolve', 'creating_sandbox',
        'uploading_artifact', 'bootstrapping', 'health_check'
    );

-- Idempotency key dedupe for client retries.
create unique index if not exists ux_workspace_jobs_idempotency
    on cloud.workspace_provision_jobs(workspace_id, idempotency_key)
    where idempotency_key is not null;

create index if not exists ix_provision_jobs_workspace_state
    on cloud.workspace_provision_jobs(workspace_id, state);

comment on table cloud.workspace_provision_jobs is
    'Provisioning job lifecycle with idempotency and single-active-job enforcement.';

-- ============================================================
-- TABLE: cloud.audit_events
-- ============================================================
create table if not exists cloud.audit_events (
    id              bigint generated always as identity primary key,
    workspace_id    text not null references cloud.workspaces(id),
    user_id         uuid references auth.users(id),
    action          text not null,
    request_id      text,
    payload         jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

-- Audit query by workspace + request_id + time (design doc section 12.1).
create index if not exists ix_audit_events_workspace_request
    on cloud.audit_events(workspace_id, request_id, created_at desc);

create index if not exists ix_audit_events_workspace_action
    on cloud.audit_events(workspace_id, action, created_at desc);

comment on table cloud.audit_events is
    'Immutable append-only audit log for all mutating control-plane operations.';

-- Immutability trigger: prevent UPDATE and DELETE on audit_events.
create or replace function cloud.audit_events_immutable()
returns trigger as $$
begin
    raise exception 'audit_events is immutable: % not permitted', tg_op;
end;
$$ language plpgsql;

drop trigger if exists trg_audit_events_no_update on cloud.audit_events;
create trigger trg_audit_events_no_update
    before update on cloud.audit_events
    for each row execute function cloud.audit_events_immutable();

drop trigger if exists trg_audit_events_no_delete on cloud.audit_events;
create trigger trg_audit_events_no_delete
    before delete on cloud.audit_events
    for each row execute function cloud.audit_events_immutable();

-- ============================================================
-- TABLE: cloud.file_share_links
-- ============================================================
create table if not exists cloud.file_share_links (
    id              bigint generated always as identity primary key,
    workspace_id    text not null references cloud.workspaces(id),
    path            text not null,
    token_hash      text not null unique,
    access          text not null default 'read'
                    check (access in ('read', 'write')),
    created_by      uuid not null references auth.users(id),
    expires_at      timestamptz not null,
    revoked_at      timestamptz,
    created_at      timestamptz not null default now()
);

-- Lookup share links by workspace + path.
create index if not exists ix_file_share_links_workspace_path
    on cloud.file_share_links(workspace_id, path);

-- Token hash lookup for share resolution.
create index if not exists ix_file_share_links_token_hash
    on cloud.file_share_links(token_hash)
    where revoked_at is null;

comment on table cloud.file_share_links is
    'Authenticated share links with exact-path scope. Only token_hash is stored; plaintext token is never persisted.';

-- ============================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================
-- Automatically update updated_at on row modification.
create or replace function cloud.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

-- Apply updated_at triggers to mutable tables.
drop trigger if exists trg_workspaces_updated_at on cloud.workspaces;
create trigger trg_workspaces_updated_at
    before update on cloud.workspaces
    for each row execute function cloud.set_updated_at();

drop trigger if exists trg_workspace_members_updated_at on cloud.workspace_members;
create trigger trg_workspace_members_updated_at
    before update on cloud.workspace_members
    for each row execute function cloud.set_updated_at();

drop trigger if exists trg_workspace_runtime_updated_at on cloud.workspace_runtime;
create trigger trg_workspace_runtime_updated_at
    before update on cloud.workspace_runtime
    for each row execute function cloud.set_updated_at();

drop trigger if exists trg_provision_jobs_updated_at on cloud.workspace_provision_jobs;
create trigger trg_provision_jobs_updated_at
    before update on cloud.workspace_provision_jobs
    for each row execute function cloud.set_updated_at();

-- ============================================================
-- ENABLE RLS ON ALL TABLES
-- ============================================================
alter table cloud.workspaces enable row level security;
alter table cloud.workspace_members enable row level security;
alter table cloud.workspace_runtime enable row level security;
alter table cloud.workspace_provision_jobs enable row level security;
alter table cloud.audit_events enable row level security;
alter table cloud.file_share_links enable row level security;
