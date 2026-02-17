# S-008: Session Expiry and Re-Authentication

## Preconditions
- User previously authenticated with an active session cookie.
- Session cookie has bounded TTL (default 24 hours).
- Control plane has rolling refresh threshold (default 1 hour before expiry).

## Steps
1. User is authenticated and using the app normally.
2. Session cookie approaches rolling refresh threshold (<1 hour remaining).
3. User makes an API call (`GET /auth/session` or any authenticated endpoint).
4. Control plane detects near-expiry and issues a refreshed session cookie.
5. User continues using the app with the new cookie.
6. **Expiry scenario**: user leaves the app and returns after session TTL elapses.
7. App calls `GET /api/v1/me` with the expired session cookie.
8. Control plane returns 401 `session_expired`.
9. App detects 401 and redirects user to login flow.
10. User re-authenticates through Supabase auth.
11. New session cookie established.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 3 | `GET /auth/session` | 200 | Identity data + new `Set-Cookie` header |
| 7 | `GET /api/v1/me` | 401 | `code: session_expired` |
| 8 | Auth guard middleware | 401 | `Set-Cookie` clearing expired cookie |
| 10 | `GET /auth/callback` | 302 | New `Set-Cookie: boring_session=...` |

### UI
- App operates normally during active session.
- Rolling refresh is invisible to user (cookie silently updated).
- On expiry, user sees login prompt or redirect (not a raw error).
- After re-auth, user returns to previous state or app root.

## Evidence Artifacts
- API response: `/auth/session` with refreshed `Set-Cookie` header.
- API response: 401 from expired session attempt.
- HAR capture: rolling refresh cookie exchange.
- Screenshot: login redirect after session expiry.
- Cookie inspection: old vs. new session cookie after refresh.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Session cookie tampered with | 401 `invalid_session` |
| Session cookie signed with wrong secret | 401 `invalid_session` |
| Rolling refresh fails (signing error) | Original cookie still valid until expiry |
| Supabase auth unavailable during re-auth | Login page shows connectivity error |
| Multiple tabs with stale sessions | Each tab independently triggers re-auth |
| Session cookie missing entirely | 401 `no_credentials`, redirect to login |
