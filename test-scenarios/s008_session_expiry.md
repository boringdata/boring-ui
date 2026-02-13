# S-008: Session Expiry and Re-authentication

## Preconditions
- User authenticated with active session cookie.
- Session TTL configured (default: 24 hours).
- Rolling refresh threshold: 1 hour before expiry.

## Steps
1. User is actively using the app with valid session.
2. Session approaches expiry threshold (< 1 hour remaining).
3. Next API call triggers rolling refresh (new cookie issued).
4. User continues without interruption.
5. (Alternative) Session expires without activity.
6. Next API call returns 401 `session_expired`.
7. Frontend detects 401 → redirects to login.
8. User re-authenticates → new session established.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 3 | `GET /auth/session` | 200 | New `Set-Cookie` with extended expiry |
| 6 | Any protected endpoint | 401 | `code: session_expired` |
| 8 | `GET /auth/callback` | 302 | New session cookie |

### UI
- No visible interruption during rolling refresh.
- Clear re-auth prompt on full expiry.
- Redirect back to previous location after re-auth.

## Evidence Artifacts
- HAR capture: Rolling refresh cookie header.
- API response: 401 on expired session.
- Screenshot: Re-auth redirect flow.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Session cookie tampered | 401 `invalid_session`, cookie deleted |
| Rolling refresh fails | Session expires at original TTL |
| Multiple tabs | Each tab gets refreshed cookie independently |
