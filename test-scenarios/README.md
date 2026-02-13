# Test Scenario Catalog

**Bead:** bd-223o.16.1 (K1)

Canonical user-journey scenarios for Feature 3 V0 end-to-end validation.
Each scenario is source-controlled and defines preconditions, deterministic
steps, expected signals, and required evidence artifacts.

## Scenario Index

| ID | Scenario | File | Critical Path |
|---|---|---|---|
| S-001 | Login and session establishment | [s001_login.md](s001_login.md) | Yes |
| S-002 | Workspace creation and provisioning | [s002_workspace_create.md](s002_workspace_create.md) | Yes |
| S-003 | Workspace selection and switch | [s003_workspace_switch.md](s003_workspace_switch.md) | Yes |
| S-004 | File editing workflow | [s004_file_edit.md](s004_file_edit.md) | Yes |
| S-005 | Chat with agent | [s005_chat_agent.md](s005_chat_agent.md) | Yes |
| S-006 | Provisioning failure and retry | [s006_provision_retry.md](s006_provision_retry.md) | No |
| S-007 | Share link create and access | [s007_share_link.md](s007_share_link.md) | No |
| S-008 | Session expiry and re-auth | [s008_session_expiry.md](s008_session_expiry.md) | No |

## Scenario Template

See [TEMPLATE.md](TEMPLATE.md) for the full scenario spec template with
field descriptions and conventions. Each scenario file must follow this
structure:

```
# S-XXX: <Title>
## Preconditions
## Steps
## Expected Signals (API + UI)
## Evidence Artifacts
## Failure Modes
```

### Conventions

- **File naming**: `sNNN_short_name.md` where NNN is the scenario ID zero-padded.
- **Metadata**: HTML comment block at top with machine-parseable YAML fields.
- **Steps**: Numbered, atomic, observable, and reproducible.
- **API signals**: Markdown table with Step, Endpoint, Status, Key Fields columns.
- **Evidence**: Concrete artifacts collectible by the scenario runner (K3).
- **Failure modes**: Each row must include a specific error code or HTTP status.
