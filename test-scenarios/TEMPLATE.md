# S-XXX: <Scenario Title>

<!--
Scenario Metadata (machine-parseable):
  id: S-XXX
  title: <Scenario Title>
  critical_path: true|false
  epics: [B, C, D, ...]
  acceptance_criteria: [18.1.1, 18.2.3, ...]
  depends_on: [S-001, S-002, ...]
  estimated_duration: <minutes>
-->

## Preconditions

List every condition that MUST hold before step 1 begins.
Each precondition should be independently verifiable.

- **System state**: What services must be running and healthy.
- **User state**: Authentication status, permissions, existing data.
- **Data state**: What records must exist (workspaces, files, etc.).

Example:
- Control plane deployed and healthy (`/health` returns 200).
- User authenticated (session cookie active, `/api/v1/me` returns 200).

## Steps

Numbered, deterministic steps. Each step must be:
1. **Atomic** — one action per step.
2. **Observable** — produces a verifiable signal (API response or UI change).
3. **Reproducible** — same input always produces same output.

Format:
```
N. <Actor> <action> <target>.
   App calls `<METHOD> <endpoint>` with <payload>.
```

Example:
1. User navigates to workspace list.
2. App calls `GET /api/v1/workspaces` → returns workspace list.
3. User clicks "Create workspace" and enters name.

## Expected Signals

### API

Table of expected API responses per step.

| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| N | `METHOD /path` | NNN | `field_a`, `field_b` |

### UI

Bullet list of observable UI state changes.

- Description of what the user should see after each significant step.

## Evidence Artifacts

List of concrete outputs that prove the scenario passed.
Each artifact should be collectible by the scenario runner.

Types:
- **Screenshot**: Visual capture of UI state.
- **API response**: JSON body from a specific endpoint call.
- **HAR capture**: HTTP archive of request/response exchange.
- **Log entry**: Specific log line or structured log event.
- **Cookie/header**: Specific header value or cookie state.

Example:
- API response: `POST /api/v1/workspaces` showing 202 with metadata.
- Screenshot: workspace list showing newly created workspace.
- HAR capture: `/auth/callback` response headers showing cookie flags.

## Failure Modes

Table of expected behavior when things go wrong.
Each row defines one failure scenario and its expected system response.

| Failure | Expected Behavior |
|---|---|
| <What goes wrong> | <HTTP status> `<error_code>` or UI behavior |

Every failure mode should be testable — include the specific error
code or status code expected.

## Notes

Optional section for:
- Known limitations of this scenario.
- Links to related design doc sections.
- Caveats about environment-specific behavior.
