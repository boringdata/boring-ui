# S-001: Login and Session Establishment

## Preconditions
- Control plane deployed and healthy (`/health` returns 200).
- Supabase project configured with auth enabled.
- Test user registered in Supabase `auth.users`.
- `GET /api/v1/app-config` returns valid branding for the host.

## Steps
1. Browser navigates to control plane host.
2. App loads and calls `GET /api/v1/app-config` → branding displayed.
3. User clicks login → redirected to Supabase auth (Google/email).
4. Supabase redirects to `GET /auth/callback?access_token=<jwt>`.
5. Control plane verifies JWT via JWKS.
6. Control plane issues session cookie (`boring_session`).
7. Browser redirected to app root (`/`).
8. App calls `GET /api/v1/me` with session cookie.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/app-config` | 200 | `app_id`, `name`, `logo` |
| 4 | `GET /auth/callback` | 302 | `Set-Cookie: boring_session=...; HttpOnly; Secure; SameSite=Lax` |
| 8 | `GET /api/v1/me` | 200 | `user_id`, `email`, `role` |

### UI
- Login page shows app branding (name + logo from app-config).
- After callback, user sees authenticated state (no login prompt).

## Evidence Artifacts
- Screenshot: Login page with branding.
- Screenshot: Authenticated app state after redirect.
- HAR capture: `/auth/callback` response headers showing cookie flags.
- API response: `/api/v1/me` JSON body.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Invalid/expired Supabase token | `GET /auth/callback` → 401 `auth_callback_failed` |
| Missing access_token param | `GET /auth/callback` → 400 `missing_token` |
| JWKS endpoint unreachable | 401 `jwks_fetch_error` |
| Session cookie missing on `/me` | 401 `no_credentials` |
