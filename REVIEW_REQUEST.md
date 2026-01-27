# Review Request: boring-ui Framework Stories

**Repo:** https://github.com/boringdata/boring-ui
**Reviewer:** cortex
**Date:** 2026-01-27

---

## Context

We're extracting reusable UI components from kurt-core to create `boring-ui` - a configurable, copy-paste friendly UI framework for Boring Data apps (kurt-core, boring-bi, future apps).

### Current State
- Copied kurt-core web client (36K lines) to boring-ui repo
- Components have hardcoded values (app name "Kurt", file tree sections, storage keys)
- Need to make everything configurable via props/config file

### Goal
Apps can copy boring-ui folder and customize via `app.config.js`:
```javascript
export default {
  branding: { name: 'Boring BI', logo: 'B' },
  fileTree: { sections: ['dashboards', 'models', 'profiles'] },
  storage: { prefix: 'bbi' },
}
```

---

## Topic

### TOPIC-001: Create Generic Reusable UI Framework
Extract and genericize UI components from kurt-core to create boring-ui - a configurable, copy-paste friendly UI framework for Boring Data apps. Components should be configurable via props and a config file, not hardcoded.

---

## Stories for Review

### Wave 1: Foundation (No Dependencies)

#### STORY-001: Create app.config.js schema and types [S]
Define the configuration schema for boring-ui apps:
- branding: { name, logo, titleFormat }
- fileTree: { sections, icons, configFiles }
- storage: { prefix }
- panels: { essential, optional }

Create TypeScript types and a config.example.js template.

**Questions:**
- Is the schema comprehensive enough?
- Should we use Zod for runtime validation?

---

#### STORY-007: Extract ThemeToggle as standalone component [XS]
Ensure ThemeToggle is fully standalone:
- No app-specific dependencies
- Uses only design tokens from CSS
- Export from components/index.js
- Add props for custom icons if needed

---

#### STORY-008: Extract UserMenu as standalone component [S]
Make UserMenu reusable:
- Accept user data via props (email, workspace, avatar)
- Remove any app-specific API calls
- Handle cloud vs local mode via props
- Export from components/index.js

---

#### STORY-009: Extract ChatPanel as standalone component [M]
Make ChatPanel/ClaudeStreamChat reusable:
- Accept API endpoint as prop
- Accept session management callbacks
- Remove app-specific hardcoding
- Keep all Claude Code UI patterns
- Export from components/index.js

**Questions:**
- Should ChatPanel have its own context provider?
- How to handle WebSocket URL configuration?

---

#### STORY-010: Extract Terminal component as standalone [M]
Make Terminal component reusable:
- Accept WebSocket URL as prop
- Accept session ID/management callbacks
- Remove app-specific API calls
- Keep xterm.js integration intact
- Export from components/index.js

---

#### STORY-013: Split styles.css into modular files [M]
Break up the 99KB styles.css into modules:
- tokens.css - Design tokens only
- base.css - Reset, typography, global styles
- layout.css - DockView, panels, app structure
- filetree.css - FileTree component styles
- chat.css - Chat panel styles
- terminal.css - Terminal styles
- components.css - Buttons, inputs, etc.

Create index.css that imports all.

**Questions:**
- Should we use CSS modules instead?
- Keep single file option for simplicity?

---

#### STORY-014: Create components/index.js export barrel [S]
Create clean exports for all reusable components:
- Named exports for each component
- Group by category (layout, filetree, chat, terminal, common)
- Include hooks exports
- Document which components are 'core' vs 'optional'

---

#### STORY-015: Remove kurt-core specific components [M]
Identify and move app-specific components to examples/:
- WorkflowList.jsx -> examples/kurt/
- WorkflowRow.jsx -> examples/kurt/
- WorkflowsPanel -> examples/kurt/
- WorkflowTerminalPanel -> examples/kurt/

Keep generic versions or stubs in main src/

**Questions:**
- Should we keep workflow components as optional imports?
- Or completely separate them?

---

#### STORY-017: Create GitStatus component/hook [S]
Extract git status functionality:
- useGitStatus(path) hook
- GitStatusBadge component
- GitChangesView component
- Accept API endpoint as prop
- Make polling interval configurable

---

#### STORY-024: Create .gitignore and clean repo [XS]
Set up proper .gitignore:
- node_modules/
- dist/
- .env
- *.log
- Remove any copied files that shouldn't be committed

---

### Wave 2: Config System (Depends on STORY-001)

#### STORY-002: Create ConfigProvider context [S]
Create a React context that provides app configuration to all components:
- ConfigProvider wrapper component
- useConfig() hook
- Default values for optional config
- Validation of required config fields

**Blocked by:** STORY-001

---

#### STORY-018: Create example app: boring-bi config [S]
Create examples/boring-bi/ with:
- app.config.js for Boring BI
- Sections: dashboards, models, profiles
- Config files: pyproject.toml, bbi.config
- Storage prefix: bbi
- Branding: Boring BI, B logo

**Blocked by:** STORY-001

---

### Wave 3: Component Refactoring (Depends on STORY-002)

#### STORY-003: Extract Header component with configurable branding [S]
Make Header component accept branding from config:
- Logo (string character or React component)
- App name
- Title format function for document.title
- Remove hardcoded 'Kurt' references

**Blocked by:** STORY-002

---

#### STORY-004: Make FileTree sections configurable [M]
Refactor FileTree to accept sections from config:
- Remove hardcoded sectionOrder ['projects', 'workflows', 'sources']
- Accept sections array from config
- Map section keys to icons dynamically
- Support custom section labels

**Blocked by:** STORY-002

**Questions:**
- Should icons be Lucide icon names or React components?
- How to handle missing/invalid section keys?

---

#### STORY-006: Make storage key prefix configurable [S]
Replace hardcoded storage key prefixes:
- Remove hardcoded 'kurt-web-' prefix
- Use config.storage.prefix
- Update all localStorage keys: layout, tabs, collapsed states, panel sizes
- Ensure backward compatibility option

**Blocked by:** STORY-002

---

### Wave 4: Advanced Features (Various Dependencies)

#### STORY-005: Make FileTree config files configurable [S]
Allow customization of which files appear as 'config' at top of tree:
- Remove hardcoded 'kurt.config' check
- Accept configFiles array from config
- Support glob patterns (e.g., '*.config', 'pyproject.toml')

**Blocked by:** STORY-004

---

#### STORY-011: Extract ShellTerminal as standalone [S]
Make ShellTerminal reusable:
- Inherit from Terminal base
- Accept shell type/command as prop
- Remove app-specific defaults
- Export from components/index.js

**Blocked by:** STORY-010

---

#### STORY-012: Create DockLayout wrapper component [L]
Create a configurable DockLayout component:
- Wraps dockview-react
- Accepts panel configuration
- Handles layout persistence with configurable storage key
- Provides sensible defaults
- Exposes layout API for parent components

**Blocked by:** STORY-006

**Questions:**
- How much of the layout logic should be abstracted?
- Should panel registration be declarative or imperative?

---

#### STORY-016: Create Editor component with configurable extensions [M]
Make Editor/TipTap component configurable:
- Accept extensions list as prop
- Accept toolbar configuration
- Remove app-specific extensions by default
- Provide extension presets (markdown, code, rich-text)

---

#### STORY-019: Create example app: kurt-core config [S]
Create examples/kurt-core/ with:
- app.config.js for Kurt
- Sections: projects, workflows, sources
- Config files: kurt.config
- Storage prefix: kurt-web
- Branding: Kurt, K logo
- Include workflow components

**Blocked by:** STORY-001, STORY-015

---

### Wave 5: Integration (Final)

#### STORY-020: Update boring-bi to use boring-ui [L]
Integrate boring-ui into boring-bi project:
- Copy boring-ui/src to boring-bi client
- Create boring-bi app.config.js
- Update imports
- Remove duplicate components
- Test all functionality

**Blocked by:** STORY-003, STORY-004, STORY-009, STORY-018

---

### Wave 6: Polish (Lower Priority)

#### STORY-021: Add TypeScript support [M]
Add TypeScript definitions:
- Convert key components to .tsx
- Create types/index.d.ts for config
- Add JSDoc comments for JS files
- Update tsconfig.json

---

#### STORY-022: Create documentation site/README [M]
Document the framework:
- Component API reference
- Configuration options
- Usage examples
- Copy/integration guide
- Customization patterns

---

#### STORY-023: Add unit tests for core components [L]
Add tests for reusable components:
- ConfigProvider context
- FileTree with mock config
- Header branding
- Storage utilities
- Use vitest (already configured)

---

## Review Questions

1. **Scope:** Are there missing stories? Anything we should remove?

2. **Dependencies:** Are the dependency chains correct? Any that should be parallelized?

3. **Estimates:** Do the estimates (XS/S/M/L) seem reasonable?

4. **Architecture:**
   - Config file approach vs props-only?
   - Keep styles in single file or split?
   - How to handle app-specific components (workflows)?

5. **Priority:** Should we reorder any stories? Critical path looks right?

6. **Risk:** What could go wrong? Any stories need spike/research first?

---

## Requested Feedback Format

For each concern, please provide:
```
STORY-XXX: [approve/modify/reject]
- Feedback: ...
- Suggested changes: ...
```

Or general feedback on architecture/approach.
