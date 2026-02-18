# Architecture Decision Records (ADRs)

Use `ADR-NNN-title.md` format. See `docs/workflow-symlinked/` for template.

## Decisions Recorded Informally (to be formalized)

These decisions are documented in plan files and should be extracted into proper ADRs:

| # | Decision | Source | Date |
|---|---|---|---|
| 1 | Use `src/front` and `src/back/boring_ui` src-layout | `exec-plans/active/PLAN.md` | Feb 2026 |
| 2 | Keep `stream` as alias for `chat_claude_code` for backward compat | `exec-plans/active/PLAN.md` | Feb 2026 |
| 3 | Gate only essential panes by default (error-first for others) | `exec-plans/active/PLAN.md` | Feb 2026 |
| 4 | CSS variables as source of truth for styling tokens | `exec-plans/active/PLAN.md` | Feb 2026 |
| 5 | Feature code must not hardcode control-plane URL patterns | `SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md` | Feb 2026 |
| 6 | Agent services delegate file/git to workspace-core | `SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md` | Feb 2026 |
| 7 | Two operating modes: LOCAL (in-process) and HOSTED (control plane) | `bd-1pwb` epic | Feb 2026 |
| 8 | Capability tokens for privileged ops in hosted mode | `bd-1pwb` epic | Feb 2026 |
| 9 | Workspace plugins disabled by default, allowlist-guarded | `app.py` | Feb 2026 |
| 10 | In-memory signing keys (tokens invalid on restart, by design) | `bd-1pwb` epic | Feb 2026 |
