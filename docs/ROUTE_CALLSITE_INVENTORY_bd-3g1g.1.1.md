# bd-3g1g.1.1 Route/Callsite Inventory

Scope: inventory all known HTTP/WS route families and callsites across frontend, backend, tests, docs, scripts, and verification utilities.

Tag key:
- `canonical-live`: mounted and reachable in `create_app()`.
- `dynamic-plugin-optional`: mounted only when workspace plugins are enabled.
- `legacy-callsite`: referenced by product/test code but not present in current default runtime route list.
- `legacy-unmounted-backend`: declared in backend modules that are not mounted by `create_app()`.
- `control-plane-canonical-doc`: canonical control-plane contract documented for frontend consumption.
- `external-service-live`: direct-connect route families for Companion/PI services.
- `unknown-missing`: callsite exists but no in-repo backend route declaration was found.

## Runtime-Mounted Families (`create_app`)

| Method(s) | Route family | Tag(s) | Service owner | Evidence |
|---|---|---|---|---|
| `GET` | `/health` | `canonical-live` | runtime utility | `src/back/boring_ui/api/app.py:187` |
| `GET` | `/api/capabilities` | `canonical-live` | workspace-core capability surface | `src/back/boring_ui/api/capabilities.py:172` |
| `GET` | `/api/config` | `canonical-live` | runtime utility | `src/back/boring_ui/api/app.py:196` |
| `GET` | `/api/project` | `canonical-live` | runtime utility | `src/back/boring_ui/api/app.py:207` |
| `GET`, `POST` | `/api/sessions` | `canonical-live` | runtime/session control | `src/back/boring_ui/api/app.py:214`, `src/back/boring_ui/api/app.py:242` |
| `POST`, `GET`, `DELETE` | `/api/approval/*` | `canonical-live` | approval/policy boundary | `src/back/boring_ui/api/approval.py:109` |
| `GET`, `PUT`, `DELETE`, `POST` | `/api/v1/files/{list,read,write,delete,rename,move,search}` | `canonical-live` | workspace-core file authority | `src/back/boring_ui/api/modules/files/router.py:23`, `src/back/boring_ui/api/app.py:161` |
| `GET` | `/api/v1/git/{status,diff,show}` | `canonical-live` | workspace-core git authority | `src/back/boring_ui/api/modules/git/router.py:20`, `src/back/boring_ui/api/app.py:167` |
| `WS` | `/ws/pty` | `canonical-live` | pty-service boundary | `src/back/boring_ui/api/modules/pty/router.py:25` |
| `WS` | `/ws/claude-stream` | `canonical-live` | agent-normal runtime stream | `src/back/boring_ui/api/modules/stream/router.py:609` |
| `GET/POST/...` | `/api/x/{plugin}/...` | `dynamic-plugin-optional` | workspace plugin surface | `src/back/boring_ui/api/workspace_plugins.py:109`, `src/back/boring_ui/api/app.py:176` |
| `WS` | `/ws/plugins` | `dynamic-plugin-optional` | plugin reload notifier | `src/back/boring_ui/api/workspace_plugins.py:118` |

## Frontend Product Callsites

| Method(s) | Route family | Tag(s) | Evidence |
|---|---|---|---|
| `GET` | `/api/tree` | `legacy-callsite` | `src/front/components/FileTree.jsx:45`, `src/front/components/chat/ClaudeStreamChat.jsx:286` |
| `GET`, `PUT`, `DELETE` | `/api/file` | `legacy-callsite` | `src/front/components/FileTree.jsx:276`, `src/front/panels/EditorPanel.jsx:131`, `src/front/App.jsx:559` |
| `POST` | `/api/file/rename` | `legacy-callsite` | `src/front/components/FileTree.jsx:307` |
| `POST` | `/api/file/move` | `legacy-callsite` | `src/front/components/FileTree.jsx:467` |
| `GET` | `/api/search` | `legacy-callsite` | `src/front/components/FileTree.jsx:162`, `src/front/components/chat/ClaudeStreamChat.jsx:252` |
| `GET` | `/api/git/status` | `legacy-callsite` | `src/front/components/FileTree.jsx:52`, `src/front/components/GitChangesView.jsx:19` |
| `GET` | `/api/git/diff` | `legacy-callsite` | `src/front/panels/EditorPanel.jsx:64` |
| `GET` | `/api/git/show` | `legacy-callsite` | `src/front/panels/EditorPanel.jsx:82` |
| `GET` | `/api/capabilities` | `canonical-live` | `src/front/hooks/useCapabilities.js:51` |
| `GET` | `/api/config` | `canonical-live` | `src/front/components/FileTree.jsx:84` |
| `GET` | `/api/project` | `canonical-live` | `src/front/App.jsx:1196` |
| `GET`, `POST` | `/api/approval/{pending,decision}` | `canonical-live` | `src/front/App.jsx:406`, `src/front/App.jsx:444` |
| `GET`, `POST` | `/api/sessions` | `canonical-live` | `src/front/components/chat/ClaudeStreamChat.jsx:240`, `src/front/components/chat/ClaudeStreamChat.jsx:322` |
| `POST` | `/api/attachments` | `unknown-missing` | `src/front/components/chat/ClaudeStreamChat.jsx:228` |
| `WS` | `/ws/pty` | `canonical-live` | `src/front/components/Terminal.jsx:91` |
| `WS` | `/ws/claude-stream` | `canonical-live` | `src/front/components/chat/ClaudeStreamChat.jsx:222` |
| `WS` | `/ws/plugins` | `dynamic-plugin-optional` | `src/front/hooks/useWorkspacePlugins.js:38` |

## External Direct-Connect Families (Companion / PI)

| Method(s) | Route family | Tag(s) | Evidence |
|---|---|---|---|
| `GET`, `POST`, `DELETE` | `/api/sessions/{create,list,kill,archive,...}` | `external-service-live` | `src/front/providers/companion/upstream/api.ts:121` |
| `GET`, `POST`, `DELETE` | `/api/fs/{list,home}` | `external-service-live` | `src/front/providers/companion/upstream/api.ts:141` |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/envs{,/{slug}}` | `external-service-live` | `src/front/providers/companion/upstream/api.ts:148` |
| `GET`, `POST`, `DELETE` | `/api/git/{repo-info,branches,worktrees,worktree,fetch,pull}` | `external-service-live` | `src/front/providers/companion/upstream/api.ts:157` |
| `WS` | `/ws/browser/{session_id}` | `external-service-live` | `src/front/providers/companion/upstream/ws.ts:99` |
| `GET`, `POST` | `/api/sessions`, `/api/sessions/create` | `external-service-live` | `src/front/providers/pi/backendAdapter.jsx:60`, `src/front/providers/pi/backendAdapter.jsx:82` |
| `GET` | `/api/sessions/{id}/history` | `external-service-live` | `src/front/providers/pi/backendAdapter.jsx:70` |
| `POST` (SSE stream) | `/api/sessions/{id}/stream` | `external-service-live` | `src/front/providers/pi/backendAdapter.jsx:197` |

## Legacy Backend Declarations Not Mounted By `create_app`

| Method(s) | Route family | Tag(s) | Evidence |
|---|---|---|---|
| `GET`, `PUT`, `DELETE`, `POST` | `/api/tree`, `/api/file`, `/api/file/rename`, `/api/file/move`, `/api/search`, `/api/git/{status,diff,show}` | `legacy-callsite`, `unknown-missing` | `src/front/components/FileTree.jsx:45`, `src/front/panels/EditorPanel.jsx:64` (no matching declaration in `src/back/boring_ui/api`) |
| `WS` | `/ws/pty` | `legacy-unmounted-backend` | `src/back/boring_ui/api/pty_bridge.py:273` |
| `WS` | `/ws/claude-stream` | `legacy-unmounted-backend` | `src/back/boring_ui/api/stream_bridge.py:1544` |

## Tests, Docs, Scripts, and Verification Surfaces

| Surface | Route family coverage | Tag(s) | Evidence |
|---|---|---|---|
| backend unit/integration tests | `/api/v1/files/*`, `/api/v1/git/*`, `/api/capabilities`, `/ws/pty`, `/ws/claude-stream` | `canonical-live` | `tests/unit/test_file_routes.py:42`, `tests/integration/test_create_app.py:172` |
| frontend component tests/mocks | `/api/tree`, `/api/file`, `/api/file/rename`, `/api/search`, `/api/git/status`, `/api/config` | `legacy-callsite` | `src/front/__tests__/components/FileTree.test.tsx:35`, `src/front/__tests__/utils/mocks.ts:185` |
| e2e tests | `http://localhost:8000/api/capabilities` | `legacy-callsite` | `src/front/__tests__/e2e/companion.spec.ts:15` |
| service split plan + sidebar plan | `/api/v1/me`, `/api/v1/workspaces`, `/api/v1/workspaces/{workspace_id}/{runtime,settings}`, `/auth/{login,callback,logout}`, `/w/{workspace_id}/{setup,...}`, `/api/v1/agent/{normal,companion,pi}/*` | `control-plane-canonical-doc` | `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md:155`, `docs/SIDEBAR_USER_MENU_PLAN.md:35` |
| smoke/verification scripts | `/api/capabilities`; PI script note for missing `/api/pi` and `/ws/pi-*` | `legacy-callsite` | `scripts/pi_backend_smoke.sh:17`, `scripts/pi_reactivity_trust_test.mjs:96` |

## Route Family Ledger (Unique Families)

1. `/health`
2. `/api/capabilities`
3. `/api/config`
4. `/api/project`
5. `/api/sessions`
6. `/api/approval/request`
7. `/api/approval/pending`
8. `/api/approval/decision`
9. `/api/approval/status/{request_id}`
10. `/api/approval/{request_id}`
11. `/api/v1/files/list`
12. `/api/v1/files/read`
13. `/api/v1/files/write`
14. `/api/v1/files/delete`
15. `/api/v1/files/rename`
16. `/api/v1/files/move`
17. `/api/v1/files/search`
18. `/api/v1/git/status`
19. `/api/v1/git/diff`
20. `/api/v1/git/show`
21. `/ws/pty`
22. `/ws/claude-stream`
23. `/api/x/{plugin}/...`
24. `/ws/plugins`
25. `/api/tree`
26. `/api/file`
27. `/api/file/rename`
28. `/api/file/move`
29. `/api/search`
30. `/api/git/status`
31. `/api/git/diff`
32. `/api/git/show`
33. `/api/attachments`
34. `/api/fs/{list,home}`
35. `/api/envs{,/{slug}}`
36. `/api/git/{repo-info,branches,worktrees,worktree,fetch,pull}`
37. `/ws/browser/{session_id}`
38. `/api/sessions/create`
39. `/api/sessions/{id}/history`
40. `/api/sessions/{id}/stream`
41. `/api/v1/me`
42. `/api/v1/workspaces`
43. `/api/v1/workspaces/{workspace_id}/runtime`
44. `/api/v1/workspaces/{workspace_id}/runtime/retry`
45. `/api/v1/workspaces/{workspace_id}/settings`
46. `/auth/login`
47. `/auth/callback`
48. `/auth/logout`
49. `/w/{workspace_id}/setup`
50. `/w/{workspace_id}/{path}`
51. `/api/v1/agent/normal/*`
52. `/api/v1/agent/companion/*`
53. `/api/v1/agent/pi/*`

Status summary:
- Canonical live families are present for `/api/v1/files/*`, `/api/v1/git/*`, `/api/approval/*`, `/api/sessions`, `/api/capabilities`, `/ws/pty`, `/ws/claude-stream`.
- Legacy route callsites remain in product frontend and frontend tests (`/api/tree`, `/api/file`, `/api/git/status`, etc.).
- Control-plane families are currently documentation contracts, not implemented in this repository.
- `/api/attachments` is an unresolved callsite with no in-repo backend declaration.
