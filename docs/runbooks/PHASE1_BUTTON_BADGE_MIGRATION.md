# Phase 1 Buttons and Badges Migration

This runbook records the `bd-hlx1.2.2.1` migration slice.

## Scope Covered

- migrated high-frequency generic button patterns to shared `Button`
- migrated high-frequency status/count badges to shared `Badge`
- preserved host behavior and shell-specific visuals by keeping existing host class hooks

## Migrated Surfaces

- `src/front/components/UserMenu.jsx`
- `src/front/components/ThemeToggle.jsx`
- `src/front/components/SidebarSectionHeader.jsx`
- `src/front/providers/pi/backendAdapter.jsx`
- `src/front/providers/pi/PiSessionToolbar.jsx`
- `src/front/components/FileTree.jsx`
- `src/front/components/GitChangesView.jsx`
- `src/front/panels/TerminalPanel.jsx`

## Wrapper Exceptions (Intentional)

No new bespoke host-only primitive components were introduced in this slice.

Instead, we used a className-bridge pattern:

- keep existing host classes (for example `sidebar-action-btn`, `review-list-allow`, `git-status-badge`)
- switch the rendered primitive to shared `Button` or `Badge`

This avoids migration churn in visual-system CSS while still moving interaction semantics and primitive contracts onto shared shadcn-native foundations.

## Guardrails

- continue removing legacy `.btn*` usage from host component code
- allow host class hooks on top of shared primitives while migration is in progress
- avoid adding new ad hoc button/badge primitives outside `src/front/components/ui/`
