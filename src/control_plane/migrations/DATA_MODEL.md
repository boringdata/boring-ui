# V0 Data Model Reference

**Bead:** bd-223o.6.4 (A4)
**Schema:** `cloud`
**Migrations:** `002_v0_core_schema.sql`, `003_v0_rls_policies.sql`

---

## Tables

### cloud.workspaces
Workspace metadata scoped to an `app_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | Workspace identifier |
| `name` | `text` NOT NULL | Display name |
| `app_id` | `text` NOT NULL | App scope (default: `boring-ui`) |
| `created_by` | `uuid` FK → `auth.users` | Creator |
| `created_at` | `timestamptz` | Auto |
| `updated_at` | `timestamptz` | Auto (trigger) |

**RLS:** Active members SELECT, active admins UPDATE. No INSERT/DELETE for users.

---

### cloud.workspace_members
Membership with invite lifecycle. V0 uses `admin` role only.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` IDENTITY PK | |
| `workspace_id` | `text` FK → `workspaces` | |
| `user_id` | `uuid` FK → `auth.users` | NULL until accepted |
| `email` | `text` NOT NULL | Invite target |
| `role` | `text` CHECK `('admin')` | V0: admin only |
| `status` | `text` CHECK `('pending','active','removed')` | Lifecycle state |
| `invited_by` | `uuid` FK → `auth.users` | |
| `created_at` / `updated_at` | `timestamptz` | Auto |

**Unique:** `ux_workspace_members_active_email` — one pending/active invite per workspace+email.
**RLS:** Active members SELECT own workspace. Pending invites visible to matching email (case-insensitive).

---

### cloud.workspace_runtime
One row per workspace tracking runtime state and sandbox identity.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` IDENTITY PK | |
| `workspace_id` | `text` FK → `workspaces` UNIQUE | One-to-one |
| `app_id` | `text` NOT NULL | |
| `state` | `text` CHECK `('provisioning','ready','error')` | Current state |
| `step` | `text` | Current provisioning step |
| `attempt` | `int` | Retry count |
| `release_id` | `text` | Deployed release |
| `sandbox_name` | `text` | Modal sandbox identifier |
| `bundle_sha256` | `text` | Artifact checksum |
| `last_error_code` / `last_error_detail` | `text` | Last failure info |
| `config` | `jsonb` | Runtime config (includes `login_branding`) |
| `updated_at` | `timestamptz` | Auto (trigger) |

**RLS:** Active members SELECT. All mutations service-role only.

---

### cloud.workspace_provision_jobs
Provisioning job lifecycle with idempotency enforcement.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` IDENTITY PK | |
| `workspace_id` | `text` FK → `workspaces` | |
| `state` | `text` CHECK (7 states) | Job lifecycle state |
| `attempt` | `int` | |
| `modal_call_id` | `text` | Modal function call ID |
| `started_at` / `finished_at` | `timestamptz` | |
| `last_error_code` / `last_error_detail` | `text` | |
| `request_id` | `text` | Correlation ID |
| `idempotency_key` | `text` | Client retry dedupe |
| `created_by` | `uuid` FK | |
| `created_at` / `updated_at` | `timestamptz` | Auto |

**States:** `queued` → `release_resolve` → `creating_sandbox` → `uploading_artifact` → `bootstrapping` → `health_check` → `ready` | `error`

**Unique indexes:**
- `ux_workspace_jobs_active` — at most one active job per workspace.
- `ux_workspace_jobs_idempotency` — dedupe by workspace+idempotency_key.

**RLS:** Active members SELECT. All mutations service-role only.

---

### cloud.audit_events
Immutable append-only audit log.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` IDENTITY PK | |
| `workspace_id` | `text` FK → `workspaces` | |
| `user_id` | `uuid` FK → `auth.users` | Actor |
| `action` | `text` NOT NULL | Event type |
| `request_id` | `text` | Correlation ID |
| `payload` | `jsonb` | Event-specific data |
| `created_at` | `timestamptz` | Immutable |

**Immutability:** UPDATE and DELETE blocked by `trg_audit_events_no_update` and `trg_audit_events_no_delete` triggers. Even service-role cannot modify existing events.

**RLS:** Active admins SELECT only. INSERT service-role only.

---

### cloud.file_share_links
Authenticated share links with exact-path scope.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` IDENTITY PK | |
| `workspace_id` | `text` FK → `workspaces` | |
| `path` | `text` NOT NULL | Exact file path |
| `token_hash` | `text` NOT NULL UNIQUE | SHA-256 of plaintext token |
| `access` | `text` CHECK `('read','write')` | Permission level |
| `created_by` | `uuid` FK | |
| `expires_at` | `timestamptz` NOT NULL | Hard expiry |
| `revoked_at` | `timestamptz` | Soft revoke timestamp |
| `created_at` | `timestamptz` | |

**Security:** Plaintext token is never stored. Only the hash is persisted.

**RLS:** Active admins SELECT and UPDATE (revoke only). INSERT service-role only. No DELETE (soft revoke via `revoked_at`).

---

## Cross-Cutting Invariants

1. **RLS enabled on all tables.** No table allows unauthenticated access.
2. **SELECT scoped to workspace membership.** No global reads.
3. **Mutations require admin or service role.** No user-level writes.
4. **Audit log is immutable.** Even service-role cannot UPDATE/DELETE.
5. **Service-role key is server-side only.** Never in browser, stored in Modal secrets.
6. **Pending invites visible only to matching email.** Case-insensitive.
7. **One active provisioning job per workspace.** Enforced by partial unique index.
8. **Idempotency key dedupe.** Client retries are safe.
9. **Migrations are idempotent.** Safe to re-run (`IF NOT EXISTS`, `OR REPLACE`, `DROP IF EXISTS`).

## Troubleshooting

| Symptom | Investigation |
|---|---|
| User can't see workspace | Check `workspace_members.status = 'active'` and `user_id` is set |
| Provisioning stuck | Query `workspace_provision_jobs` for active job state; check `last_error_code` |
| Duplicate invite error | `ux_workspace_members_active_email` blocks duplicate pending/active invites |
| Audit events can't be corrected | By design — append compensating events instead |
| Share link doesn't work | Check `expires_at` and `revoked_at`; verify `token_hash` matches |
| Cross-workspace data leak | RLS policy failure — verify membership join in policy SQL |
