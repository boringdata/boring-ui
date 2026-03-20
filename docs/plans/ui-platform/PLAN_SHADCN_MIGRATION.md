# Plan: shadcn/ui Migration + Agent Panel Pipeline

## Context

boring-ui's generic UI (buttons, cards, inputs, menus, badges, dialogs, tooltips) is
implemented as ~91 hand-written CSS classes in a 6400-line `styles.css`. These classes
have no React component abstraction — panels use raw `<button className="btn btn-primary">`.

We want agents to generate workspace panels at runtime. The agent needs a component
vocabulary it already knows. shadcn/ui is that vocabulary — every LLM has been trained
on it extensively. Adopting shadcn also consolidates 5 duplicate menu implementations,
gives us accessible Radix primitives, and makes every panel (built-in or agent-generated)
modifiable by the agent.

**Goal**: Replace the ~91 generic CSS classes with shadcn/ui components, expose them as
`@boring/ui` for child apps and workspace panels, then wire up the runtime panel pipeline.

---

## Pre-Migration: Visual Baseline Screenshots

Before any code changes, capture pixel-level baselines of every view using Playwright.
These screenshots become the QA reference for the entire migration.

### Screenshot Script: `tests/visual/capture-baseline.spec.ts`

```ts
import { test } from '@playwright/test'

const VIEWS = [
  // Core app states
  { name: '01-app-empty',        url: '/',             wait: '[data-testid="dockview"]' },
  { name: '02-app-with-file',    url: '/',             action: 'open-file' },
  { name: '03-app-dark-mode',    url: '/',             action: 'toggle-dark' },

  // Auth pages
  { name: '10-auth-login',       url: '/auth/login' },
  { name: '11-auth-signup',      url: '/auth/signup' },

  // Settings pages
  { name: '20-user-settings',    url: '/auth/settings' },
  { name: '21-ws-settings',      url: '/w/test/settings' },
  { name: '22-ws-setup',         url: '/w/test/setup' },
]

for (const view of VIEWS) {
  test(`baseline: ${view.name}`, async ({ page }) => {
    await page.goto(view.url)
    if (view.wait) await page.waitForSelector(view.wait, { timeout: 15000 })
    // actions (open-file, toggle-dark) implemented as helpers
    await page.screenshot({ path: `tests/visual/baseline/${view.name}.png`, fullPage: true })
  })
}
```

**Interactive elements** (menus, modals, tooltips) captured separately:

```
30-user-menu-open.png         — click avatar, screenshot dropdown
31-context-menu-filetree.png  — right-click file, screenshot menu
32-modal-create-workspace.png — trigger modal, screenshot
33-tooltip-hover.png          — hover toolbar button, screenshot
34-editor-mode-dropdown.png   — click code/patch toggle, screenshot
```

**Post-migration QA**: Re-run the same script, diff with baselines using
`playwright-visual-regression` or manual side-by-side. Intentional changes
(sizing adjustments to match shadcn defaults) are documented as expected diffs.

---

## Phase 1: Foundation (shadcn init + Tailwind v4 bridge)

### 1.1 Install shadcn

```bash
npx shadcn@latest init
```

Expected prompts / `components.json` output:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "",
    "css": "src/front/styles.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

Key: `"config": ""` signals Tailwind v4 mode. `"rsc": false` for Vite/SPA.

### 1.2 Create `cn()` utility

**File**: `src/front/lib/utils.js`

```js
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

Already have `clsx` and `tailwind-merge` in `package.json`.

### 1.3 Token Bridge CSS

Add to `src/front/styles.css` (at the top, after imports):

```css
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme inline {
  /* shadcn semantic colors → boring-ui tokens */
  --color-background: var(--color-background-primary);
  --color-foreground: var(--color-text-primary);
  --color-card: var(--color-background-elevated);
  --color-card-foreground: var(--color-text-primary);
  --color-popover: var(--color-background-elevated);
  --color-popover-foreground: var(--color-text-primary);
  --color-primary: var(--color-accent-default);
  --color-primary-foreground: var(--color-text-on-accent);
  --color-secondary: var(--color-background-tertiary);
  --color-secondary-foreground: var(--color-text-primary);
  --color-muted: var(--color-background-secondary);
  --color-muted-foreground: var(--color-text-secondary);
  --color-accent: var(--color-background-tertiary);
  --color-accent-foreground: var(--color-text-primary);
  --color-destructive: var(--color-error);
  --color-destructive-foreground: #ffffff;
  --color-border: var(--color-border-primary);
  --color-input: var(--color-border-primary);
  --color-ring: var(--color-focus-ring);

  /* Radii */
  --radius-sm: var(--radius-sm);
  --radius-md: var(--radius-md);
  --radius-lg: var(--radius-lg);

  /* Fonts */
  --font-sans: var(--font-sans);
  --font-mono: var(--font-mono);
}
```

Dark mode works automatically — `tokens.css` already swaps all `--color-*` values
under `[data-theme="dark"]`, so the `var()` references resolve to dark values.

### 1.4 Delete `tailwind.config.js`

With Tailwind v4 + `@theme inline`, the config file is replaced by the CSS directives.
The `@tailwindcss/vite` plugin auto-scans imported files (no `content` array needed).

**Caveat**: Verify that all existing Tailwind utility classes in the codebase still
resolve after removing the config. The config currently extends `colors`, `spacing`,
`borderRadius` etc. with `var()` references. These need equivalent `@theme inline`
entries. Do this incrementally — grep for `className=` usage of Tailwind utilities
and ensure each has a `@theme inline` mapping.

### 1.5 Verify Foundation

```bash
npm run dev   # Vite starts, no CSS errors
# Open app, verify all existing styles still render correctly
# Run: npx playwright test tests/visual/capture-baseline.spec.ts
# Diff: no visual changes (foundation is additive, not destructive)
```

**Files modified in Phase 1:**
- `components.json` (new)
- `src/front/lib/utils.js` (new)
- `src/front/styles.css` (add @theme inline + @custom-variant)
- `tailwind.config.js` (delete — or keep as stub during transition)

---

## Phase 2: Add shadcn Components

Install components one category at a time. Each `npx shadcn@latest add` generates
files into `src/front/components/ui/`.

### 2.1 Component Install Order

**Batch 1 — Primitives** (no dependencies between them):
```bash
npx shadcn@latest add button
npx shadcn@latest add badge
npx shadcn@latest add separator
npx shadcn@latest add input
npx shadcn@latest add textarea
npx shadcn@latest add label
npx shadcn@latest add switch
npx shadcn@latest add avatar
npx shadcn@latest add kbd
```

**Batch 2 — Composite** (depend on primitives):
```bash
npx shadcn@latest add card
npx shadcn@latest add alert
npx shadcn@latest add tabs
npx shadcn@latest add toggle
npx shadcn@latest add toggle-group
npx shadcn@latest add select
```

**Batch 3 — Overlay** (portals, positioning):
```bash
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add context-menu
npx shadcn@latest add tooltip
npx shadcn@latest add popover
```

**Batch 4 — Data** (optional, for agent panels):
```bash
npx shadcn@latest add table
npx shadcn@latest add scroll-area
```

### 2.2 Post-Install Adjustments

Each generated component may need minor tweaks:

1. **File extension**: shadcn generates `.tsx`. Since the project is `.jsx`,
   either rename to `.jsx` or configure `components.json` with `"tsx": false`.

2. **Import paths**: shadcn uses `@/lib/utils` for `cn()`. Verify the `@/` alias
   in `vite.config.ts` resolves correctly (already configured:
   `{ find: /^@\//, replacement: '${path.resolve(__dirname, './src/front')}/' }`).

3. **Radix packages**: shadcn will add new `@radix-ui/*` deps. Some are already
   installed (`dialog`, `tooltip`, `avatar`, `slot`). The CLI handles deduplication.

---

## Phase 3: Migrate Existing Components

Replace CSS class usage with shadcn components, one category at a time.
Each sub-phase is a single commit that can be QA'd independently.

### 3.1 Buttons (10 classes → `<Button>`)

| Old Pattern | New Pattern |
|---|---|
| `<button className="btn btn-primary">` | `<Button>` |
| `<button className="btn btn-secondary">` | `<Button variant="outline">` |
| `<button className="btn btn-ghost">` | `<Button variant="ghost">` |
| `<button className="btn btn-icon">` | `<Button variant="ghost" size="icon">` |
| `<button className="settings-btn-danger">` | `<Button variant="destructive">` |

**Files to modify** (grep for `className.*btn`):
- `src/front/components/SyncStatusFooter.jsx`
- `src/front/components/UserMenu.jsx`
- `src/front/components/FileTree.jsx`
- `src/front/panels/EditorPanel.jsx`
- `src/front/panels/EmptyPanel.jsx`
- `src/front/panels/TerminalPanel.jsx`
- `src/front/pages/UserSettingsPage.jsx`
- `src/front/pages/WorkspaceSettingsPage.jsx`
- `src/front/pages/AuthPage.jsx`

**After**: Remove `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`,
`.btn-icon`, `.settings-btn*` from `styles.css`.

### 3.2 Menus (5 implementations → `<DropdownMenu>` / `<ContextMenu>`)

Currently 5 separate hand-written menu implementations:
1. `.context-menu` (FileTree right-click)
2. `.sync-menu` (SyncStatusFooter)
3. `.editor-mode-menu` (EditorPanel)
4. `.user-menu-dropdown` (UserMenu)
5. `.ws-switcher-dropdown` (WorkspaceSettingsPage)

All become `<DropdownMenu>` or `<ContextMenu>` (Radix-based, keyboard accessible,
portal-rendered, auto-positioned).

**Files to modify**:
- `src/front/components/FileTree.jsx` → `<ContextMenu>`
- `src/front/components/SyncStatusFooter.jsx` → `<DropdownMenu>`
- `src/front/components/UserMenu.jsx` → `<DropdownMenu>`
- `src/front/panels/EditorPanel.jsx` → `<DropdownMenu>`
- `src/front/pages/WorkspaceSettingsPage.jsx` → `<DropdownMenu>`

**After**: Remove all 5 menu CSS blocks (~200 lines) from `styles.css`.

### 3.3 Dialogs (modals → `<Dialog>`)

| Old | New |
|---|---|
| `.modal-overlay` + `.modal-dialog` | `<Dialog>` + `<DialogContent>` |
| `.modal-header` / `.modal-title` | `<DialogHeader>` / `<DialogTitle>` |
| `.modal-body` | `<DialogDescription>` or content area |
| `.modal-footer` | `<DialogFooter>` |
| `.modal-close` | `<DialogClose>` (built-in X button) |

**Files to modify**:
- `src/front/pages/CreateWorkspaceModal.jsx`
- Any confirmation dialogs in settings pages

**After**: Remove `.modal-*` CSS (~80 lines).

### 3.4 Inputs & Forms

| Old | New |
|---|---|
| `<input className="settings-input">` | `<Input>` |
| `<input className="auth-input">` | `<Input>` |
| `<input className="search-input">` wrapped in `.search-box` | `<Input>` with icon |
| `<textarea className="pi-backend-input">` | `<Textarea>` |
| `<select className="settings-select">` | `<Select>` (Radix) |
| `<select className="terminal-select">` | `<Select>` (Radix) |

**Files to modify**:
- `src/front/pages/AuthPage.jsx`
- `src/front/pages/UserSettingsPage.jsx`
- `src/front/pages/WorkspaceSettingsPage.jsx`
- `src/front/components/FileTree.jsx` (search box, rename input)
- `src/front/panels/TerminalPanel.jsx`

**After**: Remove `.settings-input`, `.auth-input`, `.search-box`, `.search-input`,
`.rename-input`, `.settings-select`, `.terminal-select` from `styles.css`.

### 3.5 Cards, Badges, Alerts, Tabs, Tooltips, Switches, Avatars, Separators

Follow the same pattern as above. For each:
1. Identify all usages via grep
2. Replace with shadcn component
3. Remove old CSS classes
4. Screenshot-diff QA

**Priority order** (by usage frequency):
1. `<Badge>` — git status badges, review badges, settings badges
2. `<Card>` — settings sections, panel cards
3. `<Tooltip>` — replace custom `Tooltip.jsx` with shadcn `<Tooltip>`
4. `<Tabs>` — editor tabs, auth tabs, view mode toggles
5. `<Switch>` — settings toggle switches
6. `<Alert>` — capability warnings, error notices
7. `<Avatar>` — user menu avatar
8. `<Separator>` — menu dividers (already exact match)

### 3.6 CSS Cleanup

After all components are migrated, audit `styles.css`:
- Remove all replaced class definitions (~800-1000 lines)
- Keep all domain-specific classes (file tree, terminal, editor, diff, chat, git, DockView, auth layout)
- Keep `tokens.css` unchanged (source of truth)
- Keep `scrollbars.css` unchanged
- Keep `chat/styles.css` unchanged (1800 lines, entirely domain-specific)

**Expected reduction**: `styles.css` goes from ~6400 lines to ~5000-5400 lines.

---

## Phase 4: Expose `@boring/ui` SDK

### 4.1 Create UI barrel export

**File**: `src/front/components/ui/index.js`

```js
// Re-export all shadcn components as @boring/ui
export { Button } from './button'
export { Badge } from './badge'
export { Card, CardHeader, CardTitle, CardContent, CardFooter } from './card'
export { Input } from './input'
export { Textarea } from './textarea'
export { Label } from './label'
export { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from './select'
export { Switch } from './switch'
export { Tabs, TabsList, TabsTrigger, TabsContent } from './tabs'
export { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from './dialog'
export {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel
} from './dropdown-menu'
export { ContextMenu, ContextMenuTrigger, ContextMenuContent, ContextMenuItem } from './context-menu'
export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from './tooltip'
export { Alert, AlertTitle, AlertDescription } from './alert'
export { Avatar, AvatarImage, AvatarFallback } from './avatar'
export { Separator } from './separator'
export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './table'
export { ScrollArea } from './scroll-area'
export { Toggle } from './toggle'
export { ToggleGroup, ToggleGroupItem } from './toggle-group'
export { Popover, PopoverTrigger, PopoverContent } from './popover'
```

### 4.2 Update boring-ui public API

**File**: `src/front/index.js` — add export:

```js
// UI Components (shadcn)
export * from './components/ui'
```

### 4.3 Update package.json exports

```json
"exports": {
  ".": { "import": "./dist/boring-ui.js", "require": "./dist/boring-ui.cjs" },
  "./style.css": "./dist/style.css",
  "./ui": { "import": "./dist/boring-ui.js", "require": "./dist/boring-ui.cjs" }
}
```

### 4.4 Child app consumption (boring-macro)

boring-macro already uses `@boring-ui` alias → `boring-ui/src/front/`.
After migration, boring-macro can do:

```js
import { Button, Card, Badge } from '@boring-ui/components/ui'
```

Or via the barrel:
```js
import { Button, Card, Badge } from '@boring-ui'
```

---

## Phase 5: Workspace Panel Runtime Pipeline

This is the agent-generated panel system from our earlier architecture discussion.

### 5.1 Host Bridge

**File**: `src/front/workspace/hostBridge.js`

```js
import * as React from 'react'
import * as ReactDOM from 'react-dom'
import * as jsxRuntime from 'react/jsx-runtime'
import * as boringUI from '../components/ui'
import { useFileContent, useFileWrite, useGitStatus } from '../providers/data'
import { buildApiUrl } from '../utils/apiBase'
import { apiFetch } from '../utils/transport'

window.__BORING__ = {
  React,
  ReactDOM,
  jsxRuntime,
  ui: boringUI,
  sdk: { useFileContent, useFileWrite, useGitStatus, buildApiUrl, apiFetch },
}
```

Import in `App.jsx` before workspace panel loading.

### 5.2 esbuild Shim Files

**Directory**: `src/back/boring_ui/shims/`

```js
// react.js
const R = window.__BORING__.React; export default R;
export const { useState, useEffect, useRef, useCallback, useMemo, useContext,
  useReducer, createContext, createElement, Fragment, forwardRef, memo } = R;

// jsx-runtime.js
export const { jsx, jsxs, Fragment, jsxDEV } = window.__BORING__.jsxRuntime;

// boring-ui.js
const UI = window.__BORING__.ui; export default UI;
// Re-export every component
export const { Button, Badge, Card, CardHeader, CardTitle, CardContent,
  Input, Select, Dialog, DropdownMenu, Table, Tabs, Alert, Tooltip,
  Separator, Avatar, Switch, ScrollArea } = UI;

// boring-sdk.js
export const { useFileContent, useFileWrite, useGitStatus,
  buildApiUrl, apiFetch } = window.__BORING__.sdk;
```

### 5.3 Backend Panel Bundler

**File**: `src/back/boring_ui/api/panel_bundler.py`

New FastAPI router:
- `GET /api/panels` — list discovered panels (reads `panel.json` manifests)
- `GET /api/panels/{id}/module.js` — esbuild-bundled ESM

esbuild invocation:
```python
subprocess.run([
    "esbuild", str(entry_file),
    "--bundle", "--format=esm",
    "--jsx=automatic",
    "--loader:.jsx=jsx", "--loader:.tsx=tsx",
    "--loader:.css=css", "--loader:.json=json",
    f"--alias:react={shims}/react.js",
    f"--alias:react-dom={shims}/react-dom.js",
    f"--alias:react/jsx-runtime={shims}/jsx-runtime.js",
    f"--alias:@boring/ui={shims}/boring-ui.js",
    f"--alias:@boring/sdk={shims}/boring-sdk.js",
], capture_output=True, text=True)
```

Cache bundles in memory, invalidate on `watchfiles` change (existing watcher).

### 5.4 Update Frontend Loader

**File**: `src/front/workspace/loader.js`

Change from `@workspace` Vite alias to backend-served ESM:

```js
export async function loadWorkspacePanes(workspacePanes) {
  const loaded = {}
  for (const pane of workspacePanes) {
    try {
      const url = `/api/panels/${encodeURIComponent(pane.id)}/module.js?v=${pane.version || ''}`
      const mod = await import(/* @vite-ignore */ url)
      loaded[pane.id] = mod.default
    } catch (err) {
      console.warn(`[Workspace] Failed to load panel ${pane.id}:`, err)
    }
  }
  return loaded
}
```

### 5.5 Update `list_workspace_panes`

**File**: `src/back/boring_ui/api/workspace_plugins.py`

Read `panel.json` for richer metadata:
```python
def list_workspace_panes(self):
    panes = []
    for panel_dir in sorted(self.panels_dir.iterdir()):
        entry = self._find_entry(panel_dir)  # index.jsx, index.tsx, Panel.jsx
        if not entry:
            continue
        manifest = self._read_manifest(panel_dir)  # panel.json or defaults
        panes.append({
            "id": f"ws-{panel_dir.name}",
            "name": manifest.get("title", panel_dir.name),
            "path": str(entry.relative_to(self.panels_dir)),
            "placement": manifest.get("placement", "center"),
            "icon": manifest.get("icon"),
            "version": str(entry.stat().st_mtime_ns),
        })
    return panes
```

---

## Phase 6: Post-Migration QA

### 6.1 Automated Visual Regression

```bash
# Re-run the same baseline script
npx playwright test tests/visual/capture-baseline.spec.ts

# Compare screenshots
# Expected differences (intentional):
#   - Button heights: 28px → 36px (shadcn default)
#   - Select dropdowns: native → Radix-styled
#   - Menu animations: custom → Radix transitions
#   - Tooltip rendering: custom → Radix portal
# All color/spacing/font values should be identical (same tokens)
```

### 6.2 Manual QA Checklist

- [ ] Light mode: all pages render correctly
- [ ] Dark mode: all pages render correctly, toggle works
- [ ] Auth pages: login, signup forms functional
- [ ] Settings pages: inputs, selects, switches, buttons work
- [ ] FileTree: context menu, rename, create, drag-and-drop
- [ ] Editor: code/patch toggle, dirty indicator, toolbar
- [ ] Terminal: session tabs, xterm renders
- [ ] Shell: header, session bar
- [ ] User menu: dropdown opens, workspace switcher submenu
- [ ] Create workspace modal: opens, form works
- [ ] Sync status footer: menu, branch switching
- [ ] Keyboard navigation: Tab through menus/dialogs, Escape closes
- [ ] DockView: panel dragging, resizing, tab closing

### 6.3 Existing Test Suites

```bash
# Unit tests
npm run test:run

# E2E tests
npm run test:e2e

# Specific layout tests (most likely to catch regressions)
npx playwright test src/front/__tests__/e2e/layout.spec.ts
npx playwright test src/front/__tests__/e2e/user-menu-flows.spec.ts
```

### 6.4 Child App Verification

```bash
# boring-macro should still build and render correctly
cd /home/ubuntu/projects/boring-macro
npm run dev
# Verify: DataCatalog, ChartCanvas, Deck panels render
```

---

## File Inventory

### New Files
| File | Purpose |
|---|---|
| `components.json` | shadcn configuration |
| `src/front/lib/utils.js` | `cn()` utility |
| `src/front/components/ui/*.jsx` | ~20 shadcn components |
| `src/front/components/ui/index.js` | Barrel export |
| `src/front/workspace/hostBridge.js` | `window.__BORING__` for runtime panels |
| `src/back/boring_ui/shims/*.js` | esbuild alias shims (4 files) |
| `src/back/boring_ui/api/panel_bundler.py` | Panel bundling endpoint |
| `tests/visual/capture-baseline.spec.ts` | Visual regression screenshots |

### Modified Files
| File | Change |
|---|---|
| `src/front/styles.css` | Add `@theme inline` + `@custom-variant`, remove ~800 lines of replaced CSS |
| `src/front/index.js` | Add UI component exports |
| `src/front/App.jsx` | Import hostBridge, use panel metadata from capabilities |
| `src/front/workspace/loader.js` | Load from `/api/panels/` instead of `@workspace` |
| `src/front/components/FileTree.jsx` | Replace context-menu CSS with `<ContextMenu>` |
| `src/front/components/SyncStatusFooter.jsx` | Replace sync-menu with `<DropdownMenu>` |
| `src/front/components/UserMenu.jsx` | Replace user-menu with `<DropdownMenu>` + `<Avatar>` |
| `src/front/components/Tooltip.jsx` | Replace custom impl with shadcn `<Tooltip>` |
| `src/front/panels/EditorPanel.jsx` | Replace editor-mode-menu with `<DropdownMenu>` |
| `src/front/panels/EmptyPanel.jsx` | Replace buttons + cards |
| `src/front/panels/TerminalPanel.jsx` | Replace buttons + selects |
| `src/front/pages/AuthPage.jsx` | Replace inputs + buttons |
| `src/front/pages/UserSettingsPage.jsx` | Replace inputs + buttons + switches + cards |
| `src/front/pages/WorkspaceSettingsPage.jsx` | Replace inputs + selects + buttons + dropdown |
| `src/front/pages/CreateWorkspaceModal.jsx` | Replace modal with `<Dialog>` |
| `src/back/boring_ui/api/workspace_plugins.py` | Add `panel.json` reading, entry point detection |
| `src/back/boring_ui/api/app.py` | Mount panel bundler router |
| `package.json` | Update exports, add any missing Radix deps |
| `vite.config.ts` | Remove `@workspace` alias (no longer needed) |

### Deleted Files
| File | Reason |
|---|---|
| `tailwind.config.js` | Replaced by `@theme inline` CSS directives |

### Untouched (domain-specific, no shadcn equivalent)
| File/Area | Lines | Reason |
|---|---|---|
| `src/front/styles/tokens.css` | 400+ | Source of truth, unchanged |
| `src/front/styles/scrollbars.css` | 30 | Browser-specific, no shadcn equiv |
| `src/front/components/chat/styles.css` | 1838 | Entirely domain-specific |
| `src/front/pages/auth.css` | 361 | Page layout, not component styling |
| File tree classes | ~200 | Domain-specific tree/git styling |
| Terminal/xterm classes | ~100 | xterm overrides |
| Editor/TipTap classes | ~300 | Rich text overrides |
| Diff viewer classes | ~150 | react-diff-view overrides |
| DockView theme classes | ~100 | Panel chrome overrides |
| Git changes classes | ~80 | Git status UI |

---

## Execution Order Summary

```
1. Capture baseline screenshots (QA reference)
2. Phase 1: shadcn init + token bridge + cn() utility
   → Commit: "chore: init shadcn/ui with Tailwind v4 token bridge"
   → QA: visual diff (expect zero changes)

3. Phase 2: Install shadcn components (batches 1-4)
   → Commit: "chore: add shadcn/ui components"
   → QA: no visual changes yet (components exist but aren't used)

4. Phase 3: Migrate existing code (one commit per category)
   → Commit: "refactor: replace button CSS classes with shadcn Button"
   → Commit: "refactor: replace 5 menu implementations with shadcn DropdownMenu/ContextMenu"
   → Commit: "refactor: replace modal CSS with shadcn Dialog"
   → Commit: "refactor: replace input/select CSS with shadcn Input/Select"
   → Commit: "refactor: replace badge/card/alert/tabs/tooltip/switch/avatar CSS with shadcn"
   → Commit: "chore: remove replaced CSS classes from styles.css"
   → QA: visual diff after each commit (expect intentional sizing changes only)

5. Phase 4: Expose @boring/ui SDK
   → Commit: "feat: export shadcn components as @boring/ui SDK"
   → QA: boring-macro builds + renders correctly

6. Phase 5: Workspace panel runtime pipeline
   → Commit: "feat: esbuild panel bundler + host bridge + runtime loading"
   → QA: create test workspace panel, verify it loads and renders with shadcn components

7. Final visual regression pass
   → Compare all screenshots baseline vs current
   → Document intentional diffs
```
