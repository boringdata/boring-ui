# Phase 1 Form Primitive Migration

This runbook tracks `bd-hlx1.2.2.5` (inputs, textareas, selects, labels, and related form controls).

## Migrated In This Slice

- Shared text-entry and label primitives now back core host forms:
  - `CreateWorkspaceModal`: `Input`, `Label`
  - `UserSettingsPage`: `Input`
  - `WorkspaceSettingsPage`: `Input`, `Select` primitives for sync interval
  - `AuthPage`: `Input`, `Label`
  - `PiBackendAdapter` composer: `Textarea`
  - `ApprovalPanel` feedback: `Textarea`, `Label`
  - `PageShell` settings field label: shared `Label`

## Intentionally Native/Custom Controls (For Now)

- `TerminalPanel`, `ShellTerminalPanel`, and `PiSessionToolbar` session pickers still use native `<select>`.
  - Reason: these are compact, high-frequency toolbar controls with keyboard flow and width behavior tightly coupled to panel layout.
- `FileTree` inline rename/create controls still use native `<input>`.
  - Reason: inline tree editing and blur/submit semantics need a dedicated migration pass to avoid rename-flow regressions.

## Migration Guardrail

- Use shared form primitives for reusable host form controls.
- Keep intentionally native controls only when behavior/layout coupling would make a thin wrapper unsafe in this slice.
- Document remaining exceptions here before introducing new ad hoc form controls.
