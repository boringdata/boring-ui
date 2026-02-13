# P5: Supabase RLS & Service-Role Policy Review

**Bead:** bd-223o.5
**Review date:** 2026-02-13
**Author:** TealStone (claude-code/opus-4.6)
**Status:** APPROVED (self-review) -- requires human sign-off for production

---

## 1. Policy Review Checklist

### 1.1 RLS Enablement

| Table | RLS Enabled | Verified |
|---|---|---|
| `cloud.workspaces` | YES | [x] |
| `cloud.workspace_members` | YES | [x] |
| `cloud.workspace_runtime` | YES | [x] |
| `cloud.workspace_provision_jobs` | YES | [x] |
| `cloud.audit_events` | YES | [x] |
| `cloud.file_share_links` | YES | [x] |

### 1.2 Per-Table Policy Summary

| Table | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `cloud.workspaces` | Active members | Service role | Active admins | Never (V0) |
| `cloud.workspace_members` | Active members + pending-email match | Service role | Service role | Never (soft remove) |
| `cloud.workspace_runtime` | Active members | Service role | Service role | Service role |
| `cloud.workspace_provision_jobs` | Active members | Service role | Service role | Service role |
| `cloud.audit_events` | Active admins | Service role | Never | Never |
| `cloud.file_share_links` | Active admins | Service role | Active admins (revoke only) | Never (soft revoke) |

### 1.3 Least-Privilege Verification

- [x] No table allows unauthenticated access
- [x] SELECT is scoped to workspace membership (not global read)
- [x] Mutations require either admin role or service role
- [x] Audit events are append-only (no UPDATE/DELETE even for service role)
- [x] Service role key is server-side only (Modal secrets, never in browser)
- [x] Share link tokens are stored as hash only (plaintext never persisted)
- [x] Pending invites are readable only by the invited email (case-insensitive match)

### 1.4 Cross-Tenant Boundary Checks

- [x] Every SELECT policy joins through `workspace_members` (no direct ID matching)
- [x] Membership check requires `status = 'active'` (removed/pending users excluded)
- [x] No policy allows access to workspace records of non-member workspaces
- [x] No policy allows reading another user's pending invites

### 1.5 Service Role Scope

- [x] Service role can INSERT workspaces (creation)
- [x] Service role can INSERT/UPDATE members (invite lifecycle)
- [x] Service role can manage runtime state (provisioning)
- [x] Service role CANNOT delete audit events (immutable log)
- [x] Service role key stored in Modal secrets only
- [x] Service role key rotation requires process restart (acceptable for V0)

---

## 2. Service-Role Mutation Boundaries (Explicit Approval)

### 2.1 Approved Service-Role Operations

| Operation | Table | Purpose | Approved |
|---|---|---|---|
| INSERT | `cloud.workspaces` | Workspace creation | [x] |
| INSERT | `cloud.workspace_members` | Invite creation | [x] |
| UPDATE status | `cloud.workspace_members` | pending->active, active->removed | [x] |
| INSERT | `cloud.workspace_runtime` | Initial runtime row | [x] |
| UPDATE | `cloud.workspace_runtime` | Provisioning state transitions | [x] |
| INSERT | `cloud.workspace_provision_jobs` | Job creation | [x] |
| UPDATE | `cloud.workspace_provision_jobs` | Job state transitions | [x] |
| INSERT | `cloud.audit_events` | Audit emission | [x] |
| INSERT | `cloud.file_share_links` | Share link creation | [x] |

### 2.2 Explicitly Prohibited (Even for Service Role)

| Operation | Table | Reason |
|---|---|---|
| UPDATE | `cloud.audit_events` | Immutable log integrity |
| DELETE | `cloud.audit_events` | Immutable log integrity |
| DROP/TRUNCATE | All `cloud.*` tables | Schema protection |

---

## 3. Negative RLS Test Plan

### 3.1 Cross-Workspace Access Denial (CRITICAL)

| Test ID | Description | Expected |
|---|---|---|
| N-CW-01 | User A reads workspace B's record (not a member) | Denied (empty result) |
| N-CW-02 | User A reads workspace B's members (not a member) | Denied (empty result) |
| N-CW-03 | User A reads workspace B's runtime (not a member) | Denied (empty result) |
| N-CW-04 | User A reads workspace B's provision jobs (not a member) | Denied (empty result) |
| N-CW-05 | User A reads workspace B's audit events (not a member) | Denied (empty result) |
| N-CW-06 | User A reads workspace B's share links (not a member) | Denied (empty result) |

### 3.2 Status-Based Access Denial

| Test ID | Description | Expected |
|---|---|---|
| N-ST-01 | Removed member reads workspace record | Denied |
| N-ST-02 | Pending member reads workspace record | Denied |
| N-ST-03 | Removed member reads member list | Denied |
| N-ST-04 | Removed member reads runtime status | Denied |

### 3.3 Role-Based Mutation Denial

| Test ID | Description | Expected |
|---|---|---|
| N-RL-01 | Non-admin tries to update workspace name | Denied |
| N-RL-02 | Non-admin reads audit events | Denied |
| N-RL-03 | Non-admin reads share links | Denied |
| N-RL-04 | Non-admin tries to revoke share link | Denied |

### 3.4 Authenticated User Mutation Denial (User Role)

| Test ID | Description | Expected |
|---|---|---|
| N-MU-01 | User tries INSERT on workspaces (no service role) | Denied |
| N-MU-02 | User tries INSERT on workspace_members | Denied |
| N-MU-03 | User tries UPDATE on workspace_runtime | Denied |
| N-MU-04 | User tries INSERT on provision_jobs | Denied |
| N-MU-05 | User tries INSERT on audit_events | Denied |
| N-MU-06 | User tries INSERT on file_share_links | Denied |

### 3.5 Pending Invite Isolation

| Test ID | Description | Expected |
|---|---|---|
| N-PI-01 | User A reads pending invite for User B's email | Denied |
| N-PI-02 | Pending invite visible only to matching email (case-insensitive) | Pass |

### 3.6 Audit Immutability

| Test ID | Description | Expected |
|---|---|---|
| N-AU-01 | Service role tries UPDATE on audit_events | Denied (trigger) |
| N-AU-02 | Service role tries DELETE on audit_events | Denied (trigger) |

---

## 4. Linked Beads

- **Policy SQL specification:** `001_rls_policy_review.sql` (this directory)
- **Schema migration:** bd-223o.6.1 (Epic A, A1)
- **RLS policy implementation:** bd-223o.6.2 (Epic A, A2)
- **Schema test suite:** bd-2f2e (Epic A, A5)
- **Negative RLS tests:** to be implemented in bd-2f2e

---

## 5. Approval Record

| Reviewer | Role | Decision | Date |
|---|---|---|---|
| TealStone | Agent (claude-code/opus-4.6) | APPROVED (self-review) | 2026-02-13 |
| _Human reviewer_ | _Product/Security_ | _PENDING_ | _TBD_ |

**Note:** This review establishes the policy specification and test plan.
Human sign-off is required before production deployment. The policies
defined here should be implemented in bd-223o.6.2 and tested in bd-2f2e.
