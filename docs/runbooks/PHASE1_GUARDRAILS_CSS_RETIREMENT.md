# Phase 1 Guardrails and CSS Retirement

This runbook tracks `bd-hlx1.2.2.3` (guardrails and phased legacy CSS retirement).

## Guardrails Added

- Fast backstop scan: `scripts/check-phase1-guardrails.mjs`
  - fails on retired primitive class tokens in JSX (`btn`, `btn-primary`, `btn-secondary`, `btn-ghost`, `btn-icon`)
  - fails when retired CSS selectors are reintroduced in `src/front/styles.css` (`.btn*`, `.modal-overlay`)
  - fails on page-local primitive wrapper declarations in `src/front/pages/**` (for primitive-named wrappers such as `*Button`, `*Input`, `*Dialog`, `*Tooltip`, etc.)
- Wired into lint gate:
  - `npm run lint:phase1`
  - included in `npm run lint`

## Phased CSS Retirement In This Slice

Retired from `src/front/styles.css`:

- `.btn`
- `.btn-primary`
- `.btn-secondary`
- `.btn-ghost`
- `.btn-icon`
- `.modal-overlay`

These selectors were no longer used by host surfaces after Phase 1 migration slices moved to shared primitive/button/dialog paths.

## Intentionally Retained CSS (Domain-Specific Or In-Use)

- `.settings-btn*` family for settings-page action styling
- `.modal-dialog` and create-workspace dialog shell classes (still in-use with shared dialog primitives)
- `.context-menu*`, `.menu-separator`, and other FileTree/Editor domain menu styling
- DockView, TipTap, xterm, diff, and chat-specific styling blocks

## Evidence Checklist

- Guardrail script passes with current tree
- Guardrail contract test confirms lint wiring and retired selector bans
- Targeted lint and unit tests cover changed surfaces
