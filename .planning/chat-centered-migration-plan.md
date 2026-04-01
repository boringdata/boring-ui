# Migration Plan: Frontend Layout Restructuring

**Design doc**: `.planning/chat-centered-ux-redesign.md` (UX spec — still valid)
**Scope**: Frontend directory structure only. Agent interface cleanup is handled separately.
**Reviewed by**: Gemini 2.5 Flash — feedback incorporated below.

---

## Goal

Structure the frontend so that each layout mode is a **self-contained folder**.
Shared infrastructure (design system, UI primitives, providers, config, and
cross-layout building blocks) lives in `shared/`.
Each layout owns only its orchestration and layout-specific code internally.

```
src/front/
  layouts/                     ← ONE FOLDER PER LAYOUT
    chat/                      ← chat-centered layout (self-contained)
      components/              ← ChatComposer, EnhancedComposer, ModelSelector, FileAttachment
      hooks/                   ← useSessionState, useArtifactController, useToolBridge
      utils/                   ← toolArtifactBridge, shellPersistence, shellStateReporter
      ChatCenteredWorkspace.jsx
      NavRail.jsx
      ChatStage.jsx
      BrowseDrawer.jsx
      SurfaceShell.jsx
      SurfaceDockview.jsx
      layout.css
      ...
    ide/                       ← IDE layout (future: extract from App.jsx)
      ...

  shared/                      ← CROSS-LAYOUT SHARED LAYER
    design-system/             ← design tokens, base styles, scrollbars
      tokens.css               ← canonical CSS custom properties (colors, type, spacing, shadows)
      scrollbars.css           ← scrollbar styles
      base.css                 ← resets, fonts, theme transitions
    components/                ← shared UI components
      ui/                      ← shadcn primitives (button, input, dialog, tooltip, etc.)
      FileTree.jsx             ← file browser tree
      UserMenu.jsx             ← user/workspace menu
      Tooltip.jsx              ← tooltip wrapper
      DockTab.jsx              ← DockView tab component
      CapabilityGate.jsx       ← capability context + gating
      Editor.jsx, CodeEditor.jsx, GitDiff.jsx  ← editor components
      chat/                    ← shared chat rendering (used by BOTH layouts)
        ChatMessage.jsx        ← message renderer (parts, reasoning, tool dedup) [from shell/]
        ArtifactCard.jsx       ← clickable artifact card [from shell/]
        ToolCallCard.jsx       ← tool execution card [from shell/]
        TextBlock.jsx          ← markdown text renderer
        toolRenderers.jsx      ← tool-specific renderers (read, write, bash, grep, etc.)
        ToolUseBlock.jsx       ← legacy tool block
        styles.css             ← shared chat styles
      ...
    providers/                 ← data layer, PI agent adapters
    hooks/                     ← shared hooks
      useCapabilities.js, useWorkspaceAuth.js, etc.  ← existing
      useReducedMotion.js      ← prefers-reduced-motion [from shell/]
      useBlobUrl.js            ← blob URL lifecycle [from shell/]
      useFileStorage.js        ← file storage [from shell/]
      useChatMetrics.js        ← chat performance tracking [from shell/]
    utils/                     ← shared utilities
      transport.js, routes.js, debounce.js, apiBase.js, etc.  ← existing
      sanitize.js              ← DOMPurify XSS wrappers [from shell/]
      a11y.js                  ← ARIA live-region helpers [from shell/]
    config/                    ← appConfig
    panels/                    ← DockView panel wrappers (shared — IDE uses directly,
                                  chat uses EditorPanel in SurfaceDockview)

  pages/                       ← full-page views (auth, settings, workspace setup)
  App.jsx                      ← thin shell: feature flag → pick layout → pass context
```

---

## Core Principle: Maximum Shared Component Reuse

**Layouts are arrangements, not reimplementations.** The chat layout does NOT rebuild
any component that already exists. It imports the exact same shared components as the
IDE layout and arranges them differently.

### Shared Component Reuse Map

Every building block the chat layout uses, and where it comes from:

| Chat layout area | Shared component used | Same as IDE? |
|-------------------|----------------------|--------------|
| **File browser** (SurfaceShell sidebar) | `@shared/components/FileTree` | Yes — identical component, same tree rendering |
| **Code editor** (Surface workbench tabs) | `@shared/panels/EditorPanel` → `@shared/components/CodeEditor` | Yes — same Monaco/CodeMirror editor |
| **Markdown editor** (Surface workbench) | `@shared/panels/EditorPanel` → `@shared/components/Editor` | Yes — same TipTap editor |
| **Git diff viewer** (Surface workbench) | `@shared/components/GitDiff` | Yes — same diff component |
| **Chat messages** (ChatStage center) | `@shared/components/chat/ChatMessage` | Yes — shared message renderer |
| **Chat text blocks** (inside messages) | `@shared/components/chat/TextBlock` | Yes — same markdown renderer |
| **Tool use rendering** (inside messages) | `@shared/components/chat/toolRenderers` | Yes — same read/write/bash/grep renderers |
| **Tool call cards** (inside messages) | `@shared/components/chat/ToolCallCard` | Yes — shared tool card |
| **Artifact cards** (inside messages) | `@shared/components/chat/ArtifactCard` | Yes — shared artifact card |
| **User menu** (NavRail footer) | `@shared/components/UserMenu` | Yes — same menu, workspace switcher, logout |
| **Tooltips** (everywhere) | `@shared/components/Tooltip` | Yes — same tooltip |
| **DockView tabs** (Surface workbench) | `@shared/components/DockTab` | Yes — same tab component |
| **Capability gating** | `@shared/components/CapabilityGate` | Yes — same context + gating |
| **Sidebar activity bar** (Surface collapsed) | `@shared/components/SidebarSectionHeader` | Yes — same collapsed sidebar icons |
| **UI primitives** (buttons, inputs, etc.) | `@shared/components/ui/*` | Yes — same shadcn components |
| **Data layer** (file search, git, fs) | `@shared/providers/data` | Yes — same hooks, same API |
| **PI agent** (chat transport, tools) | `@shared/providers/pi/*` | Yes — same agent runtime |
| **Design tokens** (colors, fonts, spacing) | `@shared/design-system/tokens.css` | Yes — same CSS variables |
| **Scrollbars** | `@shared/design-system/scrollbars.css` | Yes — same styling |
| **Theme** (light/dark) | `@shared/design-system/base.css` + ThemeProvider | Yes — same theme system |

### What the chat layout adds (layout-specific only)

These are the ONLY things unique to `layouts/chat/` — purely structural/positional:

| Component | What it does | Why it's layout-specific |
|-----------|-------------|-------------------------|
| `ChatCenteredWorkspace` | Arranges NavRail + BrowseDrawer + ChatStage + SurfaceShell in a flex grid | Layout-specific arrangement |
| `NavRail` | 48px vertical icon strip | Unique to chat layout (IDE uses sidebar headers) |
| `BrowseDrawer` | Sessions drawer sliding from left | Unique to chat layout (IDE has no session drawer) |
| `ChatStage` | Center area: composes ChatMessage + ChatComposer | Arranges shared components in center column |
| `SurfaceShell` | Right workbench: composes FileTree + SurfaceDockview | Arranges shared components in right panel |
| `SurfaceDockview` | DockView instance for artifact tabs | Thin wrapper around DockView + shared EditorPanel |
| `ChatComposer` | Pill-shaped input | Unique presentation (IDE has inline chat input) |
| `layout.css` | Grid positioning, responsive breakpoints | Layout-specific CSS |

**If a component renders content (text, code, files, diffs, tools) → it's shared.**
**If a component only positions/arranges other components → it's layout-specific.**

---

## What Goes Where

### Rule: if ONLY one layout uses it → it lives inside that layout's folder.

### Rule: if BOTH layouts use it (or it's a general-purpose utility) → `shared/`.

### Chat layout internals (`layouts/chat/`)

**Orchestration** (top-level in `layouts/chat/`):
| File | Role |
|------|------|
| `ChatCenteredWorkspace.jsx` | Root — wires NavRail + BrowseDrawer + ChatStage + SurfaceShell |
| `NavRail.jsx` | 48px icon strip |
| `BrowseDrawer.jsx` | Left sessions drawer |
| `ChatStage.jsx` | Center chat area (header + messages + composer) |
| `SurfaceShell.jsx` | Right workbench (sidebar + dockview) |
| `SurfaceDockview.jsx` | DockView instance for artifact tabs |
| `layout.css` | Layout-specific positioning (grid, responsive, transitions) |
| `useChatCenteredShell.js` | Feature flag hook |

**`layouts/chat/components/`** — layout-specific orchestration components only:
| File | Role |
|------|------|
| `ChatComposer.jsx` | Pill-shaped text input with send/stop (chat layout presentation) |
| `EnhancedComposer.jsx` | Extended composer (stub) |
| `ModelSelector.jsx` | Model picker (stub) |
| `FileAttachment.jsx` | Attachment UI (stub) |

**`layouts/chat/hooks/`** — chat-layout-specific state:
| File | Role |
|------|------|
| `useSessionState.js` | Session CRUD + localStorage persistence |
| `useArtifactController.js` | Artifact open/close/focus state |
| `useToolBridge.js` | Window bridge: PI tools → artifact controller |
| `useArtifactRouting.js` | Artifact opening logic |
| `useShellPersistence.js` | Layout state persistence |
| `useShellStatePublisher.js` | State reporting to backend |

**`layouts/chat/utils/`** — chat-layout-specific helpers:
| File | Role |
|------|------|
| `toolArtifactBridge.js` | Tool name+args → SurfaceArtifact descriptor |
| `shellPersistence.js` | localStorage save/load for layout state |
| `shellStateReporter.js` | Flat state snapshot producer |

**Layout-specific CSS** (alongside components or top-level):
| File | Role |
|------|------|
| `layout.css` | Stage+Wings grid, nav rail, browse drawer, surface positioning, responsive |
| `components/chat-stage.css` | Composer + stage-specific styles |
| `components/enhanced-composer.css` | Enhanced composer styles |

### Shared layer (`shared/`)

Everything both layouts depend on, plus general-purpose utilities:

| Directory | Contains | Used by |
|-----------|----------|---------|
| `shared/design-system/` | `tokens.css` (CSS custom properties), `scrollbars.css`, `base.css` (resets, fonts) | Both layouts + all components |
| `shared/components/` | FileTree, UserMenu, Tooltip, SidebarSectionHeader, DockTab, CapabilityGate, Editor, GitDiff, CodeEditor, AppErrorBoundary | Both |
| `shared/components/ui/` | button, input, dropdown-menu, dialog, tabs, tooltip, etc. (shadcn primitives) | Both |
| `shared/components/chat/` | **ChatMessage, ArtifactCard, ToolCallCard**, TextBlock, toolRenderers, ToolUseBlock, MessageList, AiChat, ChatPanel | Both (message rendering is a shared concern) |
| `shared/providers/` | PI agent (native/backend adapters, tools, config), data layer (git, fs, http) | Both |
| `shared/hooks/` | useCapabilities, useWorkspaceAuth, **useReducedMotion, useBlobUrl, useFileStorage, useChatMetrics** | Both |
| `shared/utils/` | transport, routes, debounce, dockHelpers, apiBase, **sanitize, a11y** | Both |
| `shared/config/` | appConfig | Both |
| `shared/panels/` | EditorPanel, AgentPanel, FileTreePanel, etc. (DockView wrappers) | Both (IDE directly, chat via SurfaceDockview) |

### Design system (`shared/design-system/`)

Currently lives in `styles/` and `styles.css`. Contains:
- **`tokens.css`** — canonical CSS custom properties: colors (light + dark), typography, spacing, shadows, radii, z-index, animation, semantic aliases, shadcn bridge tokens, syntax highlighting, terminal colors
- **`scrollbars.css`** — thin scrollbar styling (Firefox + WebKit)
- **`base.css`** — box-sizing reset, html/body/root setup, font imports, theme transitions, placeholder styles

Both layouts consume tokens via CSS custom properties. No JS imports needed — just `@import` in the entry CSS.

### Cross-layout imports from `layouts/chat/`

The chat layout imports from `shared/`:
- `shared/components/FileTree` — SurfaceShell sidebar
- `shared/components/UserMenu` — NavRail footer
- `shared/components/Tooltip` — SurfaceShell
- `shared/components/SidebarSectionHeader` — CollapsedSidebarActivityBar in SurfaceShell
- `shared/components/DockTab` — UnifiedDockTab in SurfaceDockview
- `shared/components/CapabilityGate` — CapabilitiesContext in ChatCenteredWorkspace
- `shared/components/chat/ChatMessage` — ChatStage message rendering
- `shared/components/chat/ArtifactCard` — ChatMessage artifact links
- `shared/components/chat/ToolCallCard` — ChatMessage tool display
- `shared/components/chat/TextBlock` — ChatMessage text parts
- `shared/components/chat/toolRenderers` — ChatMessage tool renderers
- `shared/components/ui/button`, `shared/components/ui/input` — SurfaceShell
- `shared/providers/data` — useFileSearch in SurfaceShell
- `shared/providers/pi/useChatTransport` — ChatCenteredWorkspace
- `shared/providers/pi/uiBridge` — bridge constants in useToolBridge
- `shared/hooks/useReducedMotion` — ChatCenteredWorkspace
- `shared/hooks/useChatMetrics` — ChatCenteredWorkspace
- `shared/utils/sanitize` — ChatMessage (if needed)
- `shared/utils/a11y` — accessibility helpers
- `shared/config/appConfig` — useChatCenteredShell
- `shared/panels/EditorPanel` — SurfaceDockview

All clean, stable APIs. No circular dependencies.

---

## Path Aliases (Gemini recommendation)

Configure Vite + jsconfig to avoid brittle deep relative paths:

**`jsconfig.json`** (or `tsconfig.json`):
```json
{
  "compilerOptions": {
    "baseUrl": "src/front",
    "paths": {
      "@shared/*": ["shared/*"],
      "@layouts/*": ["layouts/*"]
    }
  }
}
```

**`vite.config.ts`**:
```js
resolve: {
  alias: {
    '@shared': path.resolve(__dirname, 'src/front/shared'),
    '@layouts': path.resolve(__dirname, 'src/front/layouts'),
  }
}
```

This turns `../../shared/components/FileTree` into `@shared/components/FileTree`.

---

## CSS Isolation

The project already uses scoped class naming conventions:
- `vc-*` — chat stage / composer classes (e.g., `vc-stage`, `vc-composer`, `vc-msg`)
- `sf-*` — surface shell classes (e.g., `sf-sidebar`, `sf-main`, `sf-empty`)
- `nav-rail*` — nav rail classes
- `browse-drawer*` — browse drawer classes
- Layout root: `.chat-centered-workspace`

This convention-based scoping is sufficient. No additional CSS methodology needed, but layout-specific styles MUST be scoped under the layout root class (e.g., `.chat-centered-workspace .rail-icon-btn`) to prevent leakage into the IDE layout. The existing CSS already follows this pattern.

---

## Phases

### Phase 1: Create `shared/` + `layouts/chat/` Structure

**Goal**: Restructure the frontend into the target layout. One atomic PR — the change is purely mechanical (file moves + import path updates), not logical. Breaking into smaller PRs creates confusing intermediate states.

#### Step 1a: Create `shared/` from existing top-level dirs

Move existing shared infrastructure into `shared/`:

```
components/      → shared/components/
hooks/           → shared/hooks/
providers/       → shared/providers/
utils/           → shared/utils/
config/          → shared/config/
styles/          → shared/design-system/
styles.css       → shared/design-system/base.css
panels/          → shared/panels/
```

Update **all imports** across the entire codebase. This is the largest part of the change but fully mechanical.

#### Step 1b: Move shared building blocks from `shell/` to `shared/`

Before creating the chat layout folder, move the shared components identified by Gemini review:

**To `shared/components/chat/`**:
```
shell/ChatMessage.jsx        → shared/components/chat/ChatMessage.jsx
shell/ArtifactCard.jsx       → shared/components/chat/ArtifactCard.jsx
shell/ToolCallCard.jsx       → shared/components/chat/ToolCallCard.jsx
shell/chat-stage.css         → shared/components/chat/chat-stage.css
```

**To `shared/hooks/`**:
```
shell/useReducedMotion.js    → shared/hooks/useReducedMotion.js
shell/useBlobUrl.js          → shared/hooks/useBlobUrl.js
shell/useFileStorage.js      → shared/hooks/useFileStorage.js
shell/useChatMetrics.js      → shared/hooks/useChatMetrics.js
```

**To `shared/utils/`**:
```
shell/sanitize.js            → shared/utils/sanitize.js
shell/a11y.js                → shared/utils/a11y.js
```

Move corresponding test files alongside their source files.

#### Step 1c: Create `layouts/chat/` from remaining `shell/` files

Move the layout-specific remainder into the structured `layouts/chat/` folder:

**Top-level orchestration** → `layouts/chat/`:
```
shell/ChatCenteredWorkspace.jsx  → layouts/chat/ChatCenteredWorkspace.jsx
shell/NavRail.jsx                → layouts/chat/NavRail.jsx
shell/BrowseDrawer.jsx           → layouts/chat/BrowseDrawer.jsx
shell/ChatStage.jsx              → layouts/chat/ChatStage.jsx
shell/SurfaceShell.jsx           → layouts/chat/SurfaceShell.jsx
shell/SurfaceDockview.jsx        → layouts/chat/SurfaceDockview.jsx
shell/shell.css                  → layouts/chat/layout.css
shell/useChatCenteredShell.js    → layouts/chat/useChatCenteredShell.js
```

**Components** → `layouts/chat/components/`:
```
shell/ChatComposer.jsx           → layouts/chat/components/ChatComposer.jsx
shell/EnhancedComposer.jsx       → layouts/chat/components/EnhancedComposer.jsx
shell/ModelSelector.jsx          → layouts/chat/components/ModelSelector.jsx
shell/FileAttachment.jsx         → layouts/chat/components/FileAttachment.jsx
shell/enhanced-composer.css      → layouts/chat/components/enhanced-composer.css
```

**Hooks** → `layouts/chat/hooks/`:
```
shell/useSessionState.js         → layouts/chat/hooks/useSessionState.js
shell/useArtifactController.js   → layouts/chat/hooks/useArtifactController.js
shell/useToolBridge.js           → layouts/chat/hooks/useToolBridge.js
shell/useArtifactRouting.js      → layouts/chat/hooks/useArtifactRouting.js
shell/useShellPersistence.js     → layouts/chat/hooks/useShellPersistence.js
shell/useShellStatePublisher.js  → layouts/chat/hooks/useShellStatePublisher.js
```

**Utils** → `layouts/chat/utils/`:
```
shell/toolArtifactBridge.js      → layouts/chat/utils/toolArtifactBridge.js
shell/shellPersistence.js        → layouts/chat/utils/shellPersistence.js
shell/shellStateReporter.js      → layouts/chat/utils/shellStateReporter.js
```

**Tests** → `layouts/chat/__tests__/` + `shared/` test dirs:
```
Tests for shared components  → shared/components/chat/__tests__/
Tests for shared hooks       → shared/hooks/__tests__/
Tests for shared utils       → shared/utils/__tests__/
Tests for layout components  → layouts/chat/__tests__/
```

#### Step 1d: Configure path aliases

Add `@shared` and `@layouts` aliases to `vite.config.ts` and `jsconfig.json`.
Update imports to use aliases where it improves readability (especially deep cross-boundary imports).

#### Step 1e: Update `App.jsx` + delete `shell/`

Update `App.jsx`:
```
shell/useChatCenteredShell  → @layouts/chat/useChatCenteredShell
shell/ChatCenteredWorkspace → @layouts/chat/ChatCenteredWorkspace
```

Delete `shell/` — everything has been moved.

**Verification**:
- `npm run test:run` — all tests pass
- `npm run build` — no import errors
- `?shell=chat-centered` — chat layout renders
- `?shell=legacy` — IDE layout renders

---

### Phase 2: Verify Cross-Layout Compatibility

**Goal**: Confirm the structure is clean. No code changes — just verification.

| Check | How |
|-------|-----|
| No circular deps | `grep -r "layouts/" src/front/shared/` should return nothing |
| Shared panels work in both layouts | `SurfaceDockview` imports `EditorPanel` from `@shared/panels/` — verify it renders |
| Design system tokens load in both layouts | Both layouts' CSS uses `var(--color-*)` — verify light/dark themes work |
| useToolBridge no conflicts | Only one layout active at a time, so no bridge key collision |
| Chat layout end-to-end | Send message → tool call → artifact opens in Surface |
| ChatMessage works with PI web format | Verify message normalizers handle PiNativeAdapter output |
| CSS isolation | Verify no style leakage between layouts (chat classes don't affect IDE) |

**Output**: Fill "Integration Gaps" section below if anything is found.

---

### Phase 3: IDE Layout Extraction (future, optional)

Extract IDE DockView orchestration from `App.jsx` into `layouts/ide/`:

```
layouts/ide/
  IdeWorkspace.jsx          ← extracted from App.jsx (~2000 lines of DockView logic)
  components/               ← IDE-specific UI (header, capability warnings)
  hooks/                    ← useDockLayout, usePanelActions, useResponsiveSidebarCollapse
```

`App.jsx` becomes a thin shell: feature flag → pick layout → pass shared context.

Not blocking. Only do when `App.jsx` needs major changes anyway.

---

## Summary

| Phase | What | Scope | Risk |
|-------|------|-------|------|
| 1a | Create `shared/` from top-level dirs | ~100+ import rewrites | Low — mechanical |
| 1b | Move shared blocks from `shell/` to `shared/` | ~10 files + tests | Low — pure moves |
| 1c | Create `layouts/chat/` from remaining `shell/` | ~20 files + tests | Low — pure moves |
| 1d | Configure path aliases | vite.config.ts + jsconfig.json | Low |
| 1e | Update App.jsx, delete `shell/` | 2 import changes + dir delete | Low |
| 2 | Verify cross-layout compat | Read-only | None |
| 3 | Extract IDE layout (future) | App.jsx split | Medium |

**All of Phase 1 ships as one atomic PR.** The change is mechanical — no logic changes, no new features.

---

## Integration Gaps

(To be filled after Phase 2 verification)
