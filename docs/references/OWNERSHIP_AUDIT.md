# Final Ownership Audit

Date: 2026-03-04  
Scope: Final keep-vs-move split between `boring-ui`, `boring-macro`, and `boring-sandbox`.

## Keep vs Move Matrix

### Route-Family Ownership

| Surface / Route Family | Final Owner | Decision | Notes |
| --- | --- | --- | --- |
| `/auth/*` | `boring-ui` core | Move to core / keep in core | Session/auth authority stays in one backend source of truth. |
| `/api/v1/me*` | `boring-ui` core | Move to core / keep in core | User identity/settings authority remains core-owned. |
| `/api/v1/workspaces*` | `boring-ui` core | Move to core / keep in core | Workspace lifecycle/settings authority remains core-owned. |
| `/api/v1/workspaces/{id}/members*` | `boring-ui` core | Move to core / keep in core | Membership authority is core-owned. |
| `/api/v1/workspaces/{id}/invites*` | `boring-ui` core | Move to core / keep in core | Invite authority is core-owned. |
| `/api/v1/files*` | `boring-ui` workspace-core | Keep in core | Filesystem ownership stays workspace-level in core only. |
| `/api/v1/git*` | `boring-ui` workspace-core | Keep in core | Git ownership stays workspace-level in core only. |
| `/api/v1/macro/*` | `boring-macro` | Keep in macro | Domain-only extension route family. |
| edge proxy/routing/provisioning/token injection | `boring-sandbox` | Keep in sandbox | Edge infrastructure only; no workspace business logic. |

### Module-Level Ownership

| Module Area | Keep In `boring-ui` | Keep In `boring-sandbox` | Keep In `boring-macro` |
| --- | --- | --- | --- |
| auth/session | yes | no | no |
| user/workspace/membership/invite/settings | yes | no | no |
| workspace boundary pass-through policy | yes | no | no |
| files/git business logic and policy checks | yes | no | no |
| macro domain adapters (`/api/v1/macro/*`) | no | no | yes |
| edge ingress/routing/provisioning/header injection | no | yes | no |

## Sandbox Cleanup Checklist

Status applies to the ownership target state and cleanup tracking.

1. Remove or deprecate duplicate auth/session business logic from `boring-sandbox` - `required`.
2. Remove or deprecate duplicate user/workspace/membership/invite/settings business logic from `boring-sandbox` - `required`.
3. Remove or deprecate duplicate filesystem/git policy/business logic from `boring-sandbox` - `required`.
4. Keep only edge routing/proxying/provisioning/token-injection in `boring-sandbox` - `required`.
5. Keep `boring-sandbox` workspace API behavior as pass-through (status/envelope preserving) - `required`.
6. Keep `boring-macro` limited to `/api/v1/macro/*` domain routes - `required`.
7. Keep `boring-ui` as the single source of truth for workspace/user management - `required`.

## Verification Commands

```bash
python3 scripts/bd_3g1g_verify.py
br lint
python3 scripts/check_forbidden_direct_routes.py
pytest tests/ -v -k "macro or sandbox or ownership or boundary"
```
