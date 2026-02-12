# Frontend Behaviours to Validate

This document lists all user-facing frontend behaviours that should be validated with E2E/browser agent testing.

## Status Legend
- [ ] Not tested
- [x] Tested with browser agent

---

## 1. Layout & Panel Management

### Panel Collapse/Expand
- [x] File tree collapses to 48px when clicking collapse button
- [x] File tree collapses via keyboard shortcut (Cmd+B / Ctrl+B)
- [x] File tree restores previous width when expanded
- [x] Terminal panel collapses via keyboard shortcut (Cmd+`)
- [x] Shell panel collapses via keyboard shortcut (Cmd+J)
- [x] Collapse state persists across page reloads

### Panel Resizing
- [x] Drag dividers to resize panels
- [x] Minimum width constraints enforced (filetree: 180px, terminal: 250px)
- [x] Minimum height constraints enforced (shell: 100px)
- [x] Panel sizes persist across page reloads (collapse state verified)

### Layout Persistence
- [x] Layout persists after reload (panel arrangement, tab positions)
- [x] Invalid layouts fall back to defaults gracefully
- [x] Corrupted layout JSON recovers without crash

---

## 2. File Tree Panel

### View Modes
- [x] Click "Files" icon shows file tree view
- [x] Click "Git Branch" icon shows git changes view
- [x] Active view mode is visually indicated

### File Operations
- [x] Click folder expands/collapses it
- [x] Click file opens it in editor
- [x] File opens as new tab in center panel
- [x] Empty-center placeholder hides when file opens
- [x] File path appears in URL query param (?doc=...)

### File Creation/Modification
- [x] Click "+" button shows inline input for new file
- [x] Type filename and press Enter creates file
- [x] New file opens in editor after creation
- [x] Right-click > Rename shows inline input
- [x] Right-click > Delete removes file

### File Search
- [x] Type in search box filters file list
- [x] Search has 200ms debounce
- [x] Clearing search shows full tree

### Context Menu
- [x] Right-click file shows context menu
- [x] "Copy Path" copies relative path to clipboard (UI label: "Copy Relative Path")
- [x] "Copy Absolute Path" copies full path to clipboard (UI label: "Copy Path")

### Git Status Indicators
- [x] Modified files show "M" indicator
- [x] Untracked files show "U" indicator
- [x] Added files show "A" indicator
- [ ] Deleted files show "D" indicator (BUG: bd-zf4 - fix applied to wrong file, service.py needs priority logic)

### Auto-Refresh
- [x] External file creation appears in tree (3s poll)
- [x] External file deletion removes from tree

---

## 3. Editor Panel

### File Display
- [x] Markdown files (.md) open in TipTap editor
- [x] Code files open in syntax-highlighted code editor
- [x] Language detection works based on file extension

### Editing & Saving
- [ ] Tab shows "*" when file has unsaved changes (needs investigation - auto-save too fast to observe)
- [x] Auto-save triggers after 2s of inactivity
- [ ] "*" disappears after save completes (needs investigation - auto-save too fast to observe)

### External Changes
- [x] "File changed on disk" notice appears for external edits
- [x] Click "Reload" refreshes content from disk

### Mode Toggle
- [x] Click "Code" shows code view
- [x] Click "Diff" shows git diff view

### Tab Management
- [x] Click tab switches active file
- [ ] Click close button closes tab (button not accessible via automation)
- [x] Last tab closing shows empty-center placeholder
- [x] Open tabs persist across page reload

### Breadcrumbs
- [x] Breadcrumbs show folder path for nested files

---

## 4. Git Changes View

- [x] Shows changed files grouped by status (M, A, U, D)
- [x] Click changed file opens diff view
- [x] "No changes" message shows when all committed
- [x] Auto-refreshes every 5 seconds
- [x] Shows error when not a git repository

---

## 5. Terminal / Agent Sessions Panel

### Session Management
- [x] Click "+" creates new session
- [x] New session becomes active
- [x] Session appears in dropdown
- [x] Select different session switches view
- [x] Close button removes session
- [x] Sessions persist across page reload

### Session Display
- [x] First message renames session (truncated at 28 chars)
- [x] Copy button copies session UUID to clipboard
- [x] Terminal colors match current theme

### Approval List
- [ ] Pending approvals appear in "Pending Reviews" section (requires bypass_permissions off)
- [ ] Shows file name and path (requires bypass_permissions off)
- [ ] "Allow" button approves immediately (requires bypass_permissions off)
- [ ] "Deny" button denies immediately (requires bypass_permissions off)
- [ ] Click approval item opens Review panel (requires bypass_permissions off)

---

## 6. Shell Terminal Panel

- [x] Click "+" creates new shell session
- [x] Shell appears in dropdown
- [x] Select shell switches view
- [x] Close button removes shell
- [x] Shell output displays in xterm.js terminal
- [x] Shell history persists across reload

---

## 7. Chat / Claude Interaction

### Message Sending
- [x] Type message and click send
- [x] Message appears as user message
- [x] Claude response streams in real-time
- [x] Cmd+Enter sends message

### Tool Use Blocks
- [x] Bash tool shows command with syntax highlighting
- [x] Read tool shows file path and contents
- [ ] Write tool shows file path and new content (untested - needs tool execution)
- [ ] Edit tool shows diff with old/new strings (untested - needs tool execution)
- [ ] Glob tool shows pattern and matching files (untested - needs tool execution)
- [ ] Grep tool shows pattern and matching lines (untested - needs tool execution)

### Slash Commands
- [x] Type "/" shows command menu
- [ ] /clear clears conversation (BUG: bd-34u - command recognized but UI not cleared)
- [x] /model shows model selection submenu
- [ ] /thinking toggles thinking mode (command not found in menu)

### Auto-Scroll
- [ ] Chat auto-scrolls to latest message
- [ ] Scrolling up disables auto-scroll
- [ ] "Scroll to bottom" button appears when scrolled up

---

## 8. Approval / Review Panel

- [ ] Review panel opens when clicking approval
- [ ] Shows file path and metadata
- [ ] Shows diff preview with syntax highlighting
- [ ] "Open file" button opens file in editor
- [ ] Feedback textarea captures input
- [ ] "Allow" button sends approval with feedback
- [ ] "Deny" button sends denial with feedback
- [ ] Panel closes after decision

---

## 9. Keyboard Shortcuts

- [x] Cmd+B / Ctrl+B toggles file tree
- [x] Cmd+` / Ctrl+` toggles terminal
- [x] Cmd+J / Ctrl+J toggles shell
- [x] Cmd+W / Ctrl+W closes active tab
- [x] Cmd+Shift+D / Ctrl+Shift+D toggles theme
- [x] Shortcuts don't trigger when typing in input fields

---

## 10. Theme & Appearance

- [x] Click moon/sun icon toggles theme
- [x] Theme persists across page reload
- [x] First visit matches system preference
- [x] Terminal colors update with theme change
- [x] Smooth color transition (no jarring flash)

---

## 11. Capability Gating

- [ ] App fetches capabilities on load
- [ ] Missing features show error state in pane
- [ ] No blank panels or crashes for missing capabilities

---

## 12. Critical E2E Flows (from PLAN.md)

These are the specific flows called out in the original plan:

### Chat Flow
- [x] Launch app
- [x] Open chat
- [x] Send message
- [x] Verify response renders

### File Tree Flow
- [x] Create file on disk (external process)
- [x] Wait/refresh
- [x] Verify file appears in tree

### Layout Persistence Flow
- [x] Resize panes (collapse tested)
- [x] Reload page
- [x] Verify sizes persist (collapse state persisted)
- [x] Verify open panes persist

---

## Summary

| Category | Total Behaviours |
|----------|------------------|
| Layout & Panel Management | 12 |
| File Tree Panel | 21 |
| Editor Panel | 14 |
| Git Changes View | 5 |
| Terminal/Agent Sessions | 12 |
| Shell Terminal | 6 |
| Chat/Claude Interaction | 14 |
| Approval/Review Panel | 8 |
| Keyboard Shortcuts | 6 |
| Theme & Appearance | 5 |
| Capability Gating | 3 |
| Critical E2E Flows | 3 |
| **Total** | **109** |
