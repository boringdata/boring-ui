# PLAN_SHADCN_MIGRATION.md

## Status

Revised execution plan for migrating boring-ui's generic primitive surface to shadcn/ui,
publishing that surface as `@boring/ui`, and replacing the Vite-only workspace panel loader
with a production-safe backend-bundled runtime panel pipeline.

This document intentionally merges the strongest parts of earlier drafts:

- the migration-first concreteness, file-by-file mapping, and visual QA discipline
- the architecture-first contract work, package/import strategy, runtime status model,
  and rollout safety work
- additional fixes for real-world issues those drafts only partially covered, especially:
  - Tailwind v4 browser-support and migration-risk gating
  - runtime-panel utility-class generation
  - visible compile/runtime error handling
  - security/trust-boundary clarity
  - phased rollout with a temporary fallback path
  - CI guardrails to prevent legacy generic classes from creeping back in

---

## Why This Work Exists

boring-ui currently has two related problems:

1. A large generic-UI surface lives in hand-written CSS and raw HTML elements rather than
   reusable React primitives.
2. Runtime workspace panels currently depend on a dev-oriented loading path that assumes the
   frontend build tool can see workspace source files directly.

That combination makes the codebase harder to maintain for humans and much harder for agents
to extend reliably. Agents are already fluent in shadcn/ui's component vocabulary. If the
host app and runtime panels share that vocabulary, agent-authored panels become much more
predictable, child apps gain a stable SDK, and the host app loses a large amount of duplicated
generic CSS and repeated primitive implementations.

---

## Goals

1. Replace the generic primitive layer (buttons, menus, dialogs, inputs, badges, tabs,
   avatars, tooltips, alerts, simple cards, separators) with shadcn/ui-backed primitives.
2. Keep boring-ui's design tokens as the visual source of truth. This is a migration, not a redesign.
3. Expose the shared primitive surface as `@boring/ui` for the host app, child apps, and
   runtime panels.
4. Replace the current Vite-only runtime panel loading path with a backend-bundled ESM pipeline
   that works the same way in development and production.
5. Ensure runtime panel failures are isolated, visible, and diagnosable instead of becoming
   silent broken imports or blank tabs.
6. Preserve accessibility, keyboard navigation, theming, and existing user flows.
7. Remove dead generic CSS only after the new primitives are proven by visual and functional QA.

---

## Target End State

By the end of this project:

- common primitives come from `@boring/ui`
- the host app uses those primitives instead of ad hoc class bundles
- boring-ui tokens still define color, typography, radii, spacing semantics, and dark mode
- child apps can import `@boring/ui` directly
- runtime workspace panels can import:
  - `react`
  - `react/jsx-runtime`
  - `react-dom`
  - `@boring/ui`
  - `@boring/sdk`
- the backend discovers, validates, bundles, caches, and serves runtime panels as ESM
- the frontend hot-loads those ESM bundles into DockView
- compile failures surface as explicit panel errors
- runtime render failures are caught by per-panel error boundaries
- the old `@workspace` alias path can be removed after the new path soaks safely

---

## Non-Goals

- Re-skin DockView tab chrome or other domain-specific layout surfaces.
- Replace xterm, TipTap, diff-viewer, or chat transcript rendering with shadcn primitives.
- Allow arbitrary npm imports in runtime panels in v1.
- Treat runtime panels as a hardened sandbox. They are an extensibility mechanism, not a
  security boundary.
- Introduce arbitrary CSS theming for runtime panels in v1.
- Collapse all CSS into Tailwind utilities. Domain-specific CSS remains where it is the best tool.

---

## Decisions To Lock Before Code Churn

### 1. Visual system: boring-ui tokens remain the source of truth

Adopt shadcn/ui as the component vocabulary, not as a new visual brand. The host app keeps
existing CSS tokens and maps shadcn semantic variables to those tokens.

### 2. Canonical package/import strategy

Use `@boring/ui` as the canonical SDK import path. Keep the current package/import story as a
compatibility alias during migration so existing consumers do not break all at once.

Practical rule:

- new code uses `@boring/ui`
- existing imports remain supported for at least one release cycle or one full internal soak
- runtime panels only document `@boring/ui`, not internal source paths

### 3. Runtime import contract for v1

Version 1 of runtime panels supports only:

- `react`
- `react/jsx-runtime`
- `react-dom`
- `@boring/ui`
- `@boring/sdk`

No host-private imports. No `@workspace` filesystem alias. No arbitrary third-party packages.

### 4. Stable host-module mapping

Do not couple runtime panels to Vite chunk names or hashed application artifacts.

Use stable shim modules such as:

- `/__bui/runtime/react.js`
- `/__bui/runtime/react-dom.js`
- `/__bui/runtime/jsx-runtime.js`
- `/__bui/runtime/boring-ui.js`
- `/__bui/runtime/boring-sdk.js`

Those modules can be backed by a boot-time global such as `window.__BORING_RUNTIME__`, but the
runtime-panel import contract must point at stable module URLs, not directly at globals.

### 5. Runtime panel manifest/status contract

Every discovered panel gets manifest metadata and a status:

- `ready`
- `building`
- `error`
- `disabled` (optional, if discovery/validation chooses to suppress a panel)

Capabilities and/or a dedicated panel endpoint must expose:

- `id`
- `name`
- `entry`
- `module_url`
- `hash`
- `status`
- `error`
- `updated_at`
- `placement`
- `icon`
- optional manifest-derived metadata

### 6. Tailwind v4 migration safety

Do **not** delete `tailwind.config.js` immediately. Keep it as a compatibility bridge until the
existing Tailwind usage audit is complete and the CSS-driven theme mapping is proven. Remove it
only in the cleanup phase, not on day one.

### 7. Runtime-panel styling contract

This is a critical real-world fix:

Backend-served runtime panel files are not part of the normal host-app Tailwind source scan, so
arbitrary utility classes typed into a runtime `Panel.jsx` will not reliably exist in the final
CSS bundle unless they are already present somewhere in scanned host sources.

Therefore v1 must explicitly choose one of these paths and document it:

1. support only `@boring/ui` plus a curated allowlisted utility subset that is always generated, or
2. add a separate runtime CSS compilation story

Recommendation for v1: choose option 1. Ship a small, curated runtime utility subset for common
layout and spacing classes, and treat arbitrary Tailwind utilities as unsupported in runtime panels.

### 8. Trust boundary

Runtime panels run in the same browser realm as the host app. Import restrictions reduce accidental
coupling, but they do not create a true security sandbox. Only trusted local/agent-authored panels
should run in this system until a stronger isolation model exists.

---

## Pre-Flight Gate: Browser / Platform Support

Before committing to Tailwind v4 migration, confirm boring-ui's browser support matrix is compatible
with Tailwind v4's platform requirements. Tailwind v4 is designed for Safari 16.4+, Chrome 111+,
and Firefox 128+, and the Tailwind team recommends staying on v3.4 if older browsers must be
supported. Also verify Node/tooling versions before migration work begins.

If boring-ui must support older browsers, stop here and either:

- postpone Tailwind v4-specific work, or
- split the project into:
  - shadcn adoption on the current supported Tailwind path, and
  - a later v4 upgrade after browser requirements are renegotiated

---

## Phase 0: Baseline, Inventory, And Contract Lock

### 0.1 Capture deterministic visual baselines

Before any code changes, capture pixel-level baselines of every important view using Playwright.

Use stable fixtures and deterministic rendering rules:

- fixed viewport(s)
- fixed test data / seeded workspace state
- reduced motion
- stable theme toggle state
- stable date/time where practical
- stable font-loading and async waits
- baseline images committed to the repo

### Screenshot Script: `tests/visual/capture-baseline.spec.ts`

```ts
import { test, expect } from '@playwright/test'

const VIEWS = [
  { name: '01-app-empty',     url: '/',              wait: '[data-testid="dockview"]' },
  { name: '02-app-with-file', url: '/',              action: 'open-file' },
  { name: '03-app-dark-mode', url: '/',              action: 'toggle-dark' },
  { name: '10-auth-login',    url: '/auth/login' },
  { name: '11-auth-signup',   url: '/auth/signup' },
  { name: '20-user-settings', url: '/auth/settings' },
  { name: '21-ws-settings',   url: '/w/test/settings' },
  { name: '22-ws-setup',      url: '/w/test/setup' },
]

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  // seed app state here so screenshots are deterministic
})

for (const view of VIEWS) {
  test(`baseline: ${view.name}`, async ({ page }) => {
    await page.goto(view.url)
    if (view.wait) await page.waitForSelector(view.wait, { timeout: 15000 })
    // action helpers implemented separately
    await expect(page).toHaveScreenshot(`${view.name}.png`, { fullPage: true })
  })
}
```

Capture interactive states separately:

- user menu open
- file-tree context menu open
- create-workspace dialog open
- tooltip visible
- editor mode dropdown open
- destructive confirm dialog open (if present)

### 0.2 Inventory the migration surface

Produce a concrete inventory of all generic primitive usage:

- buttons
- icon buttons
- badges
- menus / dropdowns / context menus
- dialogs / modals / confirms
- inputs / textareas / selects
- tabs / toggles / segmented controls
- avatar / tooltip / separator / alert / card

Also explicitly mark what is **not** part of the migration:

- DockView shell geometry and tab layout
- terminal/xterm surface
- editor/TipTap content surface
- diff viewer overrides
- chat transcript/tool rendering
- file-tree domain styling
- custom auth/layout page CSS that is not a generic primitive

### 0.3 Lock the runtime panel authoring contract

Document the v1 authoring contract before implementing the pipeline.

Recommended directory shape:

```text
kurt/panels/<panel-name>/
  Panel.jsx
  panel.json
```

Recommended runtime-panel authoring shape:

```jsx
import { Card, CardContent, CardHeader, CardTitle, Button } from '@boring/ui'
import { useFileContent } from '@boring/sdk'

export const meta = {
  minSize: { width: 320, height: 220 },
}

export default function ExamplePanel() {
  const file = useFileContent?.('README.md')

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Example</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-sm">{file?.slice?.(0, 80) ?? 'No file loaded'}</div>
        <Button size="sm">Action</Button>
      </CardContent>
    </Card>
  )
}
```

Rules:

- default export must be a React component
- optional named export `meta` is allowed
- allowed imports are limited to the runtime contract above
- no host-private imports
- no arbitrary npm imports
- no arbitrary CSS imports in v1
- supported Tailwind utilities are limited to the documented allowlist

### 0.4 Define manifest schema and defaults

Add a minimal `panel.json` schema up front so discovery, metadata, and loader logic are not
invented ad hoc later.

Suggested v1 fields:

```json
{
  "title": "Git Insights",
  "entry": "Panel.jsx",
  "placement": "right",
  "icon": "git-branch",
  "description": "Workspace git metrics and status",
  "minSize": { "width": 320, "height": 220 }
}
```

Validation rules:

- unknown fields warn but do not fail the whole panel
- invalid `entry` paths fail that panel only
- path traversal is rejected
- missing file -> `error` status
- omitted fields get sane defaults

### 0.5 Exit criteria

- baseline screenshots exist
- migration surface inventory is written down
- runtime import contract is approved
- manifest schema is approved
- browser support decision is explicitly made

---

## Phase 1: Build The shadcn / `@boring/ui` Foundation

### 1.1 Initialize shadcn for Vite + Tailwind v4 mode

shadcn's CLI supports initialization for Vite, supports Tailwind v4 projects, and uses
`components.json` to control output paths, aliases, CSS variables, and whether generated
components are `.tsx` or `.jsx`. For Tailwind v4 projects, the Tailwind config path is left
blank, `new-york` is the preferred style, and `tsx: false` allows JavaScript `.jsx` output.

Suggested command:

```bash
npx shadcn@latest init -t vite
```

Target `components.json`:

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

### 1.2 Add `cn()` utility

**File**: `src/front/lib/utils.js`

```js
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

### 1.3 Bridge shadcn semantic tokens to boring-ui tokens

Tailwind v4 supports CSS-driven theme variables with `@theme`, and shadcn supports Tailwind v4
and `@theme inline`. Keep boring-ui tokens as the source of truth and map shadcn semantics onto
them at the top of `src/front/styles.css`. Tailwind v4 also supports `@custom-variant` for custom
dark-mode selectors.

```css
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme inline {
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
  --radius-sm: var(--radius-sm);
  --radius-md: var(--radius-md);
  --radius-lg: var(--radius-lg);
  --font-sans: var(--font-sans);
  --font-mono: var(--font-mono);
}
```

### 1.4 Keep `tailwind.config.js` as a transition bridge

Do **not** delete `tailwind.config.js` in the first foundation commit.

Tailwind v4 supports CSS-first configuration with `@theme`, but it also supports incrementally
bridging legacy JavaScript config via `@config` during migration. Safelisting is no longer handled
by the JS config in v4, so if a safelist is needed it must move to `@source inline()`.

Plan:

1. keep the existing JS config while auditing current Tailwind usage
2. move design-token mappings and custom utilities into CSS deliberately
3. only delete `tailwind.config.js` after:
   - the host app builds cleanly
   - screenshot diffs are acceptable
   - the runtime utility allowlist is in place
   - no remaining dependency on JS-only config behavior exists

### 1.5 Add a runtime utility allowlist stylesheet

Because Tailwind generates CSS by scanning project sources, backend-served runtime panel files are
not automatically part of that scan. Tailwind v4 provides `@source` and `@source inline()` for
explicit source registration and safelisting.

To keep runtime panels practical without adding a full second Tailwind compiler in v1:

- create `src/front/styles/runtime-panel-utilities.css`
- import it from the main stylesheet
- safelist a curated subset of common agent-authored layout classes using `@source inline()`

Recommended v1 allowlist:

- layout: `flex`, `grid`, `block`, `hidden`, `contents`
- sizing: `w-full`, `h-full`, `min-w-0`, `min-h-0`, `max-w-full`
- spacing: `gap-1`..`gap-6`, `p-1`..`p-6`, `px-*`, `py-*`, `m-*`, `space-y-*`
- alignment: `items-center`, `items-start`, `justify-between`, `justify-center`
- overflow: `overflow-hidden`, `overflow-auto`
- typography: `text-xs`, `text-sm`, `text-base`, `font-medium`, `font-semibold`, `truncate`
- borders/background helpers that map to semantic tokens only if truly needed

Important rule:

- runtime panels may use `@boring/ui` freely
- runtime panels may use only the documented utility subset outside `@boring/ui`
- arbitrary values and arbitrary utilities are unsupported in v1

### 1.6 Install initial shadcn component set

Install components in batches.

**Batch 1 — Primitives**

```bash
npx shadcn@latest add button badge separator input textarea label switch avatar kbd
```

**Batch 2 — Composite**

```bash
npx shadcn@latest add card alert tabs toggle toggle-group select
```

**Batch 3 — Overlay**

```bash
npx shadcn@latest add dialog dropdown-menu context-menu tooltip popover
```

**Batch 4 — Data / panel-friendly**

```bash
npx shadcn@latest add table scroll-area
```

### 1.7 Add thin boring-specific wrappers only where justified

Default rule: export the shadcn components directly.

Exception rule: if boring-ui needs consistent boring-specific behavior that will otherwise be
re-implemented over and over (for example a menu-content offset, standard icon-button defaults,
or a destructive-confirm dialog composition), create a thin wrapper in `@boring/ui` instead of
re-creating local CSS or one-off component forks.

### 1.8 Verify foundation before migration

Checklist:

- app builds
- no CSS errors
- light/dark mode still work
- baseline visual diff is either zero-change or intentionally documented
- `@boring/ui` can be imported from local consumers
- runtime utility allowlist stylesheet is present and documented

---

## Phase 2: Migrate The Host App To The Shared Vocabulary

Migration principle: move generic primitives first, leave domain/layout CSS alone.

### 2.1 Buttons and icon buttons

Mapping:

| Old Pattern | New Pattern |
|---|---|
| `<button className="btn btn-primary">` | `<Button>` |
| `<button className="btn btn-secondary">` | `<Button variant="secondary">` |
| `<button className="btn btn-ghost">` | `<Button variant="ghost">` |
| `<button className="btn btn-icon">` | `<Button variant="ghost" size="icon">` |
| `<button className="settings-btn-danger">` | `<Button variant="destructive">` |

Targets:

- `src/front/components/SyncStatusFooter.jsx`
- `src/front/components/UserMenu.jsx`
- `src/front/components/FileTree.jsx`
- `src/front/components/GitHubConnect.jsx`
- `src/front/panels/EditorPanel.jsx`
- `src/front/panels/TerminalPanel.jsx`
- `src/front/pages/UserSettingsPage.jsx`
- `src/front/pages/WorkspaceSettingsPage.jsx`
- `src/front/pages/AuthPage.jsx`

After migration:

- remove `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-icon`,
  and settings-button generic classes
- re-run visual + interaction QA

### 2.2 Menus and context menus

Current duplicated menu surfaces:

1. file-tree context menu
2. sync-status menu
3. editor-mode menu
4. user menu dropdown
5. workspace switcher dropdown

All migrate to Radix-backed shadcn menu primitives.

Targets:

- `src/front/components/FileTree.jsx` → `ContextMenu`
- `src/front/components/SyncStatusFooter.jsx` → `DropdownMenu`
- `src/front/components/UserMenu.jsx` → `DropdownMenu`
- `src/front/panels/EditorPanel.jsx` → `DropdownMenu`
- `src/front/pages/WorkspaceSettingsPage.jsx` → `DropdownMenu`

Requirements:

- preserve keyboard navigation
- preserve focus return
- preserve portal behavior
- preserve submenu behavior if present
- preserve all aria labels and command semantics

### 2.3 Dialogs / modals / confirms

Mapping:

| Old | New |
|---|---|
| `.modal-overlay` + `.modal-dialog` | `<Dialog>` + `<DialogContent>` |
| `.modal-header` / `.modal-title` | `<DialogHeader>` / `<DialogTitle>` |
| `.modal-body` | content area or `<DialogDescription>` |
| `.modal-footer` | `<DialogFooter>` |
| `.modal-close` | shadcn/Radix close controls |

Targets:

- `src/front/pages/CreateWorkspaceModal.jsx`
- settings-page confirmations
- destructive confirm surfaces, if any

Requirements:

- focus trap
- Escape closes when appropriate
- destructive actions remain clearly signposted
- any async submit state remains intact

### 2.4 Inputs, textareas, selects, and small form primitives

Mapping:

| Old | New |
|---|---|
| `settings-input` / `auth-input` | `<Input>` |
| `pi-backend-input` | `<Textarea>` |
| search input + icon wrapper | `<Input>` plus wrapper |
| settings/native select | `<Select>` where custom behavior is needed |
| terminal select | `<Select>` if behavior is compatible; keep native if required for edge cases |

Targets:

- `src/front/pages/AuthPage.jsx`
- `src/front/pages/UserSettingsPage.jsx`
- `src/front/pages/WorkspaceSettingsPage.jsx`
- `src/front/components/FileTree.jsx`
- `src/front/panels/TerminalPanel.jsx`

Caution:

Do not replace a native `<select>` with Radix `Select` where browser-native behavior is materially
better or where implementation complexity outweighs the benefit. Use the shared vocabulary, but not
dogmatically.

### 2.5 Cards, badges, alerts, tabs, tooltip, switch, avatar, separator

Priority order:

1. `Badge`
2. `Card`
3. `Tooltip`
4. `Tabs`
5. `Switch`
6. `Alert`
7. `Avatar`
8. `Separator`

Rules:

- replace only the generic primitive layer
- preserve layout wrappers
- preserve keyboard shortcuts and focus behavior
- if behavior differs, solve it in `@boring/ui`, not by reintroducing page-local primitive CSS

### 2.6 CSS cleanup and guardrails

After each category lands:

- delete the replaced CSS blocks
- screenshot diff the affected views
- run targeted interaction tests

After all categories land:

- remove the replaced generic CSS from `styles.css`
- keep domain-specific CSS unchanged
- keep `tokens.css`, `scrollbars.css`, chat CSS, and other domain overrides

Add a CI guardrail:

- create `scripts/check-no-legacy-generic-ui.mjs`
- fail CI if banned legacy generic classes reappear in JSX or CSS:
  - `btn`
  - `btn-primary`
  - `btn-secondary`
  - `btn-ghost`
  - `modal-*`
  - old menu classnames
  - other explicitly retired generic primitive classes

### 2.7 Exit criteria

- host app generic primitives use `@boring/ui`
- legacy generic primitive CSS is mostly gone
- screenshot and interaction regressions are understood and acceptable
- no one is adding new legacy primitive classes

---

## Phase 3: Publish `@boring/ui` As A Real SDK

### 3.1 Create the public barrel

**File**: `src/front/components/ui/index.js`

Export:

- primitives
- `cn`
- any approved thin boring wrappers
- no host-private components by default

### 3.2 Update the library entrypoint

**File**: `src/front/index.js`

```js
export * from './components/ui'
```

### 3.3 Update package exports

Support:

- main SDK import path
- CSS entrypoint
- optional subpath exports if needed

Example target direction:

```json
{
  "exports": {
    ".": {
      "import": "./dist/boring-ui.js",
      "require": "./dist/boring-ui.cjs"
    },
    "./style.css": "./dist/style.css",
    "./ui": {
      "import": "./dist/boring-ui.js",
      "require": "./dist/boring-ui.cjs"
    }
  }
}
```

### 3.4 Canonicalize import examples

Document only these styles for new consumers:

```js
import { Button, Card, Badge } from '@boring/ui'
```

If compatibility aliases remain during migration, document them as temporary compatibility only.

### 3.5 Verify in at least one child app

Use `boring-macro` as the canary child app.

Verification:

- it builds against the new exports
- panels render correctly
- no consumer must import from boring-ui internal source paths
- CSS import expectations are documented and actually work

### 3.6 Documentation updates

Update:

- `README.md`
- `docs/EXTENSION_GUIDE.md`
- any child-app integration notes

Document:

- allowed SDK imports
- CSS import expectations
- migration path from compatibility imports to `@boring/ui`

---

## Phase 4: Build The Runtime Panel Pipeline

## Current Path

1. backend reports relative source paths
2. frontend receives `workspace_panes`
3. frontend imports via `@workspace/<path>`
4. it works only when the frontend build tool can see workspace files directly

## Target Path

1. backend discovers panel directories and manifests
2. backend validates and compiles each panel to ESM
3. backend reports `module_url`, `hash`, `status`, and `error`
4. frontend imports `module_url`
5. file-watch invalidation updates manifest state and refreshes affected panels

### 4.1 Host runtime bridge

**File**: `src/front/workspace/hostBridge.js`

```js
import * as React from 'react'
import * as ReactDOM from 'react-dom'
import * as jsxRuntime from 'react/jsx-runtime'
import * as boringUI from '../components/ui'
import {
  useFileContent,
  useFileWrite,
  useGitStatus,
} from '../providers/data'
import { buildApiUrl } from '../utils/apiBase'
import { apiFetch } from '../utils/transport'

window.__BORING_RUNTIME__ = {
  version: 'v1',
  React,
  ReactDOM,
  jsxRuntime,
  ui: boringUI,
  sdk: {
    useFileContent,
    useFileWrite,
    useGitStatus,
    buildApiUrl,
    apiFetch,
  },
}
```

Import this before workspace panel loading.

### 4.2 Stable runtime shim modules

Serve stable modules from predictable URLs.

Suggested files or generated responses:

- `/__bui/runtime/react.js`
- `/__bui/runtime/react-dom.js`
- `/__bui/runtime/jsx-runtime.js`
- `/__bui/runtime/boring-ui.js`
- `/__bui/runtime/boring-sdk.js`

Each shim re-exports from `window.__BORING_RUNTIME__`.

Why this design:

- stable import contract
- no dependency on Vite chunk filenames
- no browser import-map dependency in v1
- easier debugging and backward compatibility

### 4.3 Define `@boring/sdk`

Keep the runtime SDK intentionally small in v1.

Initial recommended exports:

- `useFileContent`
- `useFileWrite`
- `useGitStatus`
- `buildApiUrl`
- `apiFetch`

Possible later additions after real usage proves the need:

- theme helpers
- toast/notification helpers
- workspace context helpers
- selection/navigation helpers

Do not expose host internals casually. Every addition increases long-term compatibility burden.

### 4.4 Backend compiler service

**New module**: `src/back/boring_ui/api/panel_bundler.py` (or similarly named service module)

Responsibilities:

- discover panels
- validate manifest + entry
- compile panels
- cache outputs
- serve bundles and source maps
- track status/error metadata
- invalidate on changes

Recommended implementation details:

- use the project-local `esbuild` install, not a global binary
- bundle as ESM
- emit source maps
- platform: browser
- externalization/aliasing only for the approved runtime imports
- reject unsupported bare imports explicitly
- store build artifacts outside tracked source paths, e.g. `.boring/panel-builds/`
- use content-hash invalidation based on:
  - entry source
  - manifest
  - relevant SDK/UI version marker

esbuild supports build-time aliasing, loaders, ESM output format, and source maps, which makes it a
good fit for this controlled bundling layer.

Recommended esbuild direction:

```python
subprocess.run([
    "node_modules/.bin/esbuild",
    str(entry_file),
    "--bundle",
    "--format=esm",
    "--platform=browser",
    "--jsx=automatic",
    "--sourcemap=external",
    "--loader:.jsx=jsx",
    "--loader:.tsx=tsx",
    "--loader:.json=json",
    "--alias:react=/__bui/runtime/react.js",
    "--alias:react-dom=/__bui/runtime/react-dom.js",
    "--alias:react/jsx-runtime=/__bui/runtime/jsx-runtime.js",
    "--alias:@boring/ui=/__bui/runtime/boring-ui.js",
    "--alias:@boring/sdk=/__bui/runtime/boring-sdk.js",
], capture_output=True, text=True)
```

Important v1 restriction:

- do **not** enable arbitrary CSS importing for runtime panels yet
- reject `.css` imports in v1 to avoid global style injection and styling inconsistency

### 4.5 Manifest state and validation

Per panel, track:

- `id`
- `name`
- `source_path`
- `entry_path`
- `module_url`
- `source_map_url`
- `hash`
- `status`
- `error`
- `updated_at`
- `placement`
- `icon`
- optional manifest metadata

Validation behavior:

- one broken panel must not break discovery for other panels
- compile failure -> panel status `error`
- validation error -> panel status `error`
- unchanged panels reuse cached build output
- rebuilds are debounced on rapid saves

### 4.6 Update workspace discovery

**File**: `src/back/boring_ui/api/workspace_plugins.py`

Discovery should:

- find panel directories
- locate default entry (`Panel.jsx`, `index.jsx`, `index.tsx`, or manifest entry)
- read `panel.json`
- validate safe paths
- attach status/build metadata
- return loader-friendly `module_url` instead of raw relative source paths

Suggested response shape:

```python
{
    "id": "ws-git-insights",
    "name": "Git Insights",
    "placement": "right",
    "icon": "git-branch",
    "module_url": "/api/panels/ws-git-insights/module.js?v=<hash>",
    "hash": "<hash>",
    "status": "ready",
    "error": None,
    "updated_at": "...",
}
```

### 4.7 Update capabilities and app bootstrap

Make `workspace_panes` include runtime bundle metadata:

- `module_url`
- `hash`
- `status`
- `error`

The frontend should not have to reverse-engineer source paths anymore.

### 4.8 Replace the frontend loader

**File**: `src/front/workspace/loader.js`

New behavior:

- if `status === "ready"`, import `module_url`
- if `status === "building"`, render a building placeholder panel
- if `status === "error"`, render a visible error panel
- if dynamic import itself fails, render a visible load error

Example direction:

```js
export async function loadWorkspacePanes(workspacePanes) {
  const loaded = {}

  for (const pane of workspacePanes) {
    if (pane.status === 'building') {
      loaded[pane.id] = () => <PanelBuildPending pane={pane} />
      continue
    }

    if (pane.status === 'error') {
      loaded[pane.id] = () => <PanelBuildError pane={pane} />
      continue
    }

    try {
      const mod = await import(/* @vite-ignore */ pane.module_url)
      loaded[pane.id] = mod.default
    } catch (error) {
      loaded[pane.id] = () => <PanelLoadError pane={pane} error={error} />
    }
  }

  return loaded
}
```

### 4.9 Add per-panel React error boundaries

Compile success is not the same as runtime success.

Wrap runtime panels in a small error boundary so a bad render/effect does not take down DockView
or break sibling panels.

### 4.10 Preserve websocket invalidation

When a panel file changes:

- backend invalidates cached artifact
- capabilities/panel manifest refresh occurs
- frontend updates that panel
- unaffected panels remain untouched

### 4.11 Temporary rollout flag

For safe rollout, keep the old loader path behind a temporary feature flag or capability switch:

- `runtime_panel_mode: "vite-alias" | "backend-esm"`

Rollout sequence:

1. implement backend ESM path
2. verify it in dev
3. verify it in production-like env
4. switch default to backend ESM
5. remove the old alias path only after soak

---

## Phase 5: Tests, QA, And Rollout

### 5.1 Automated visual regression

Re-run the same screenshot suite after each major migration category.

Expected intentional changes may include:

- button heights / padding
- native select -> Radix select
- menu animation / portal behavior
- tooltip rendering strategy

Unexpected changes in spacing, typography, or color must be investigated because the visual tokens
should still come from the same boring-ui variables.

### 5.2 Accessibility regression checks

Add focused checks for:

- menu keyboard navigation
- dialog focus trap and escape behavior
- tab order on settings/auth pages
- tooltip labeling
- switch labels
- context menu keyboard operability where applicable

Where practical, add automated accessibility assertions on the highest-risk screens.

### 5.3 Backend tests

Add tests for:

- panel discovery
- manifest defaulting
- path traversal rejection
- compile success
- compile failure
- unsupported import rejection
- cache invalidation
- source map serving
- one bad panel not poisoning all panels

### 5.4 Frontend tests

Add tests for:

- shared wrapper rendering
- loader behavior for `ready`, `building`, and `error`
- panel error boundary behavior
- websocket-driven refresh
- runtime-panel error UI

### 5.5 End-to-end runtime panel tests

Create fixture panels:

1. `hello-panel` -> valid panel that imports `@boring/ui`
2. `build-error-panel` -> invalid JSX/import to exercise compile error state
3. `runtime-error-panel` -> throws during render to exercise error boundary
4. `utility-allowlist-panel` -> uses supported runtime utility subset

Verify:

- discovery works
- compilation happens
- DockView renders the panel
- editing the file updates the panel
- bad panels fail visibly and locally

### 5.6 Child-app verification

Use `boring-macro` as the canary consumer.

Verify:

- build succeeds
- imports come from `@boring/ui`
- panels/components render correctly
- no consumer relies on internal source paths

### 5.7 Manual QA checklist

- light mode works
- dark mode works
- auth pages function
- settings pages function
- file tree rename/create/context menu work
- editor mode toggle works
- terminal session controls work
- user menu works
- create workspace dialog works
- sync footer menu works
- DockView drag/resize/tab close still work
- runtime panel load/build/error states are understandable

### 5.8 Documentation rollout

Update docs so runtime panel authors know exactly what is supported.

Must document:

- allowed imports
- example `Panel.jsx`
- example `panel.json`
- supported runtime utility subset
- unsupported patterns
- error-debugging workflow
- compatibility alias deprecation plan

---

## Risks And Mitigations

### Risk: visual churn during migration

Mitigation:

- deterministic baselines
- migrate by primitive category
- token bridge keeps existing visual language
- no redesign work mixed into this project

### Risk: Tailwind v4 breaks older browser support

Mitigation:

- explicit pre-flight browser gate
- do not start the migration without agreeing on support matrix
- keep old path or postpone v4 if required

### Risk: runtime panels render without expected utility classes

Mitigation:

- explicitly ship a runtime utility allowlist
- document the supported subset
- reject unsupported styling patterns in v1

### Risk: runtime bundles accidentally couple to internal app chunks

Mitigation:

- stable shim modules
- no references to hashed frontend assets
- no import-map dependency in v1

### Risk: compile failures create blank tabs or silent no-ops

Mitigation:

- expose build status in capabilities
- render explicit build and load error panels
- store source maps and normalized diagnostics

### Risk: one bad panel breaks all panel discovery

Mitigation:

- per-panel validation and compile isolation
- status/error tracked per panel
- continue serving healthy panels

### Risk: package rename / import migration breaks consumers

Mitigation:

- compatibility alias during migration
- canary child-app verification
- documented deprecation path

### Risk: runtime panels are mistaken for a security sandbox

Mitigation:

- document the trust boundary explicitly
- keep the import surface small
- treat panels as trusted extensions until a real isolation model exists

---

## File Inventory

### New Files

- `components.json`
- `src/front/lib/utils.js`
- `src/front/components/ui/*.jsx`
- `src/front/components/ui/index.js`
- `src/front/styles/runtime-panel-utilities.css`
- `src/front/workspace/hostBridge.js`
- runtime placeholder/error components for panel states
- `src/back/boring_ui/api/panel_bundler.py`
- runtime shim module files or route handlers
- `tests/visual/capture-baseline.spec.ts`
- backend and frontend tests for runtime panels
- `scripts/check-no-legacy-generic-ui.mjs`

### Modified Files

- `src/front/styles.css`
- `src/front/index.js`
- `src/front/App.jsx`
- `src/front/workspace/loader.js`
- migrated host components/pages/panels
- `src/back/boring_ui/api/workspace_plugins.py`
- `src/back/boring_ui/api/capabilities.py`
- `src/back/boring_ui/api/app.py`
- `package.json`
- `vite.config.ts`
- docs files (`README.md`, `docs/EXTENSION_GUIDE.md`, migration docs)

### Deleted Files (late cleanup only)

- `tailwind.config.js` (only after transition audit is complete)
- dead generic primitive CSS blocks
- dead Vite-only runtime panel loading path

### Explicitly Untouched / Mostly Untouched

- `src/front/styles/tokens.css`
- `src/front/styles/scrollbars.css`
- domain-specific chat CSS
- DockView-specific layout/theme CSS
- terminal/xterm overrides
- editor/TipTap overrides
- diff-viewer overrides
- file-tree domain styling
- other domain-specific surfaces with no shadcn equivalent

---

## Suggested Commit Sequence

```text
1. chore: add deterministic visual baselines and migration inventory
2. chore: initialize shadcn foundation and token bridge
3. chore: add runtime utility allowlist stylesheet
4. chore: add shadcn component primitives
5. refactor: migrate buttons and badges to @boring/ui
6. refactor: migrate menus and context menus to @boring/ui
7. refactor: migrate dialogs to @boring/ui
8. refactor: migrate inputs, textareas, and selects to @boring/ui
9. refactor: migrate tooltip, tabs, switch, avatar, alert, card, separator
10. chore: remove retired generic primitive CSS and add CI guardrail
11. feat: publish @boring/ui exports and compatibility alias
12. feat: add runtime host bridge, shim modules, and @boring/sdk
13. feat: add backend panel compiler, manifest state, and serving routes
14. feat: switch frontend loader to backend ESM with error states
15. test: add runtime panel integration fixtures and loader tests
16. docs: update extension guide and SDK docs
17. chore: remove old @workspace loader path after soak
18. chore: delete transition-only tailwind config if no longer needed
```

---

## Definition Of Done

This project is done when all of the following are true:

- boring-ui's generic primitive layer is implemented through `@boring/ui`
- the host app uses the shared vocabulary instead of local generic primitive CSS
- boring-ui tokens still control the visual system
- at least one child app imports `@boring/ui` without reaching into internal source paths
- runtime panels load from backend-served ESM instead of the Vite filesystem alias
- runtime panels can import only the approved v1 SDK surface
- panel compile failures are visible in the UI
- panel runtime failures are isolated by error boundaries
- a valid panel hot-reloads within seconds without restarting the app
- dead generic primitive CSS and the old loader path are removed after soak
- documentation accurately describes the supported authoring contract

---

## Final Execution Summary

```text
Phase 0  Baseline + inventory + contract lock
Phase 1  shadcn/@boring/ui foundation + token bridge + runtime utility allowlist
Phase 2  host app migration by primitive category + CSS cleanup + CI guardrail
Phase 3  publish/verify @boring/ui for child apps
Phase 4  backend-bundled runtime panel pipeline + stable shim modules + visible statuses/errors
Phase 5  test, soak, document, and remove old paths
```
