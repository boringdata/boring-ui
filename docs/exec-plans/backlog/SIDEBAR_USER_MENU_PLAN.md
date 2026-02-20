# Sidebar User Menu Plan (Below FileTree)

## Goal

Add a persistent user menu at the bottom of the left sidebar (below FileTree / Changes view) with:

- Avatar button
- Switch workspace
- Create workspace
- User settings
- Logout

## Ownership Boundary

Yes, this is primarily owned by `boring-ui`.

- `boring-ui` owns: UI layout, menu behavior, routing/navigation, local user settings UX.
- `boring-sandbox` owns: auth/session endpoints and workspace APIs used by actions.

## Product Behavior

1. User menu is always visible in expanded filetree sidebar.
2. In collapsed sidebar, show compact avatar-only control.
3. Menu opens as anchored dropdown/popup with keyboard and click-outside support.
4. Actions:
   - `Switch workspace`: show workspace list, navigate to selected `/w/{id}/`.
   - `Create workspace`: call create API and navigate to new workspace.
   - `User settings`: open frontend-owned user settings surface (local prefs in v1).
   - `Logout`: call `/auth/logout` then redirect to login.

## Backend Readiness (Current)

Implemented and usable now:

- `GET /api/v1/me`
- `GET /api/v1/workspaces`
- `POST /api/v1/workspaces`
- `GET /auth/logout`

Not implemented yet:

- No user-level settings endpoint (for example `/api/v1/me/settings`).
- Existing settings endpoints are workspace-scoped, not user-scoped.

## Existing Assets To Reuse

- `src/front/components/UserMenu.jsx` (already exists; currently minimal).
- Existing menu styles in `src/front/styles.css` (`.user-menu*`).
- Workspace endpoints already used elsewhere:
  - `GET /api/v1/workspaces`
  - `POST /api/v1/workspaces`

## Implementation Phases

### Phase 1: Sidebar Placement

1. Update `src/front/panels/FileTreePanel.jsx` structure:
   - content area for FileTree/GitChanges
   - footer slot for user menu
2. Add CSS for sidebar footer docking:
   - sticky/fixed inside panel bottom
   - no overlap with tree scroll
3. Collapsed mode: show compact avatar trigger.

### Phase 2: Menu Data + Actions

1. Extend `UserMenu` props/contracts:
   - `email`, `workspaceId`, `workspaceName`
   - callbacks: `onSwitchWorkspace`, `onCreateWorkspace`, `onOpenUserSettings`, `onLogout`
2. Add workspace list loader for menu:
   - fetch workspaces on open (or cached preload)
3. Wire actions:
   - switch: `window.location.assign('/w/{id}/')`
   - create: POST then navigate to new workspace
   - me: GET `/api/v1/me` for avatar/email identity
   - logout: `window.location.assign('/auth/logout')`

### Phase 3: User Settings Surface

1. Add user settings entrypoint in `boring-ui` (frontend-owned):
   - initial scope: theme/editor prefs/session defaults
2. Ship v1 as local-state/local-storage backed (no new backend dependency).
3. Add route or modal pattern and close/open behavior.
4. Optional v2: add dedicated user settings API later (`/api/v1/me/settings`).

### Phase 4: Hardening + Accessibility

1. Keyboard navigation:
   - `Enter/Space` to open
   - `Arrow` navigation in menu
   - `Esc` closes
2. ARIA:
   - `aria-expanded`, `role="menu"`, `role="menuitem"`
3. Error UX:
   - workspace fetch/create failure toast/banner
   - disable repeated submits while pending

## API Contract Expectations

- `GET /api/v1/workspaces` returns list including workspace ids/names.
- `POST /api/v1/workspaces` returns created workspace id.
- `GET /api/v1/me` provides user email for avatar/menu identity.
- `GET /auth/logout` clears session cookie.
- User-level settings API is currently unavailable; user settings v1 must be local frontend state.

If schema differs, adapt in one mapper function inside `UserMenu` data layer.

## Acceptance Criteria

1. User menu is visible below FileTree in expanded sidebar.
2. Avatar + dropdown works with mouse and keyboard.
3. Switch workspace changes active workspace successfully.
4. Create workspace works from menu and redirects correctly.
5. Logout always returns to login and clears session.
6. User settings entry opens reliably using frontend-local settings in v1.
7. Tests cover rendering, actions, and failure states.

## Test Plan

1. Unit tests:
   - `UserMenu` rendering and action dispatch
   - workspace list mapping
2. Integration tests:
   - sidebar placement + scroll behavior
   - switch/create/logout end-to-end mocks
3. E2E smoke:
   - login -> open menu -> switch workspace -> open files
   - login -> create workspace -> lands in new workspace
   - logout path works from sidebar menu

## Risks / Mitigations

1. Risk: Sidebar layout regressions with DockView sizing.
   - Mitigation: snapshot/integration tests with collapsed/expanded states.
2. Risk: Workspace list latency impacts menu responsiveness.
   - Mitigation: lazy fetch + loading state + cache.
3. Risk: API response shape drift.
   - Mitigation: centralized response mapper + defensive parsing.
