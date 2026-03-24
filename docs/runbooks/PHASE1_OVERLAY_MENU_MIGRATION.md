# Phase 1 Overlay and Menu Migration

This runbook tracks `bd-hlx1.2.2.2` (dialogs, dropdowns, menus).

## Migrated In This Slice

- `CreateWorkspaceModal` now uses shared dialog primitives:
  - `Dialog`
  - `DialogContent`
  - `DialogHeader`
  - `DialogTitle`
  - `DialogFooter`
- `EditorPanel` code-mode selector now uses shared dropdown primitives:
  - `DropdownMenu`
  - `DropdownMenuTrigger`
  - `DropdownMenuContent`
  - `DropdownMenuItem`

## Intentionally Custom Overlay/Menu Behavior (Not Migrated Yet)

- `SyncStatusFooter` multi-step sync menu remains custom.
  - Reason: nested branch flyout with inline branch creation input and agent actions is not a drop-in primitive swap.
- `UserMenu` workspace switch submenu remains custom.
  - Reason: portal-positioned workspace flyout and route-aware control-plane behavior need dedicated migration coverage.
- `FileTree` context menu remains custom.
  - Reason: right-click semantics and path-specific destructive actions need focused context-menu migration work.

## Migration Guardrail

- Prefer shared primitives for dialog/dropdown/menu behaviors.
- Keep intentionally custom overlays only where behavior is materially beyond a thin wrapper.
- Document remaining custom behavior here before adding new one-off overlay logic.
