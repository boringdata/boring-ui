# App.jsx Split - Comprehensive Refactoring Plan

## Epic: bd-1qk

**Status**: In Progress
**Priority**: P2 (High - Technical Debt)
**Type**: Epic
**Owner**: ubuntu

---

## Executive Summary

App.jsx is currently a 1,459-line monolithic React component that manages the entire IDE-like interface. It handles layout persistence, panel management, file operations, approvals workflow, keyboard shortcuts, drag-and-drop, URL synchronization, and more. This refactoring effort will decompose App.jsx into focused, maintainable, and testable modules while preserving all existing functionality.

---

## Background & Motivation

### Current State Analysis

**File**: `src/front/App.jsx`
**Lines**: 1,459
**Responsibilities**: 22+ distinct concerns
**useEffect hooks**: 13+ major effects
**useCallback hooks**: 15+ callbacks
**useRef hooks**: 10+ refs
**Nesting depth**: 4+ levels in some places

### Problems with Current Architecture

1. **Cognitive Load**: Developers must understand 1,459 lines to make even small changes
2. **Testing Difficulty**: Tightly coupled logic makes unit testing nearly impossible
3. **Risk of Regressions**: Changes in one area can inadvertently affect unrelated functionality
4. **Code Duplication**: Similar patterns repeated (e.g., three nearly identical toggle functions)
5. **Onboarding Friction**: New contributors face steep learning curve
6. **Merge Conflicts**: Large file increases probability of conflicts in team settings

### Goals of This Refactoring

1. **Separation of Concerns**: Each module handles one responsibility
2. **Testability**: Individual hooks/utilities can be unit tested in isolation
3. **Maintainability**: Smaller files are easier to understand and modify
4. **Reusability**: Extracted hooks can be reused in other contexts
5. **Performance**: Opportunity to optimize re-renders with focused hooks
6. **Documentation**: Self-documenting code through clear module boundaries

---

## Architecture Overview

### Target Structure

```
src/front/
├── App.jsx                    # ~200 lines (orchestration only)
├── hooks/
│   ├── useAppState.js         # Core application state
│   ├── usePanelToggle.js      # Panel collapse/expand logic
│   ├── useCollapsedState.js   # Collapsed state management
│   ├── usePanelConstraints.js # Size constraints application
│   ├── useApprovals.js        # Approval polling and state
│   ├── useApprovalPanels.js   # Approval panel synchronization
│   ├── useFileOperations.js   # File opening operations
│   ├── useTabManager.js       # Tab state management
│   ├── useLayoutInit.js       # Dockview initialization
│   ├── useLayoutRestore.js    # Layout restoration logic
│   ├── useSavedTabs.js        # Tab persistence
│   ├── useUrlSync.js          # URL query parameter sync
│   ├── useDragDrop.js         # Drag and drop handling
│   └── useActivePanel.js      # Active panel tracking
├── utils/
│   ├── panelToggleUtils.js    # Toggle helper functions
│   ├── filePositioning.js     # Smart file positioning
│   ├── approvalUtils.js       # Path normalization, titles
│   └── layoutUtils.js         # Layout initialization helpers
└── components/
    ├── AppHeader.jsx          # Header with logo and title
    └── CapabilityWarning.jsx  # Capability warning banner
```

### Dependency Flow

```
App.jsx (orchestrator)
    ├── useAppState (foundation)
    │   └── config, capabilities, refs
    ├── usePanelToggle (uses useCollapsedState)
    │   └── panelToggleUtils
    ├── useApprovals
    │   └── approvalUtils
    ├── useApprovalPanels (uses useApprovals)
    ├── useFileOperations (uses useTabManager)
    │   └── filePositioning
    ├── useLayoutInit
    │   └── layoutUtils
    ├── useLayoutRestore (uses useLayoutInit)
    └── useSavedTabs
```

---

## Risk Assessment

### Low Risk (Phase 1-2)
- Utility extraction: Pure functions, no side effects
- Ref management: Internal to hooks

### Medium Risk (Phase 3-5)
- Hook extraction: Need to preserve render timing
- State lifting: May affect component re-renders

### Higher Risk (Phase 6-7)
- Layout initialization: Core functionality, complex timing
- Layout restoration: Multiple interdependencies

### Mitigation Strategies
1. **Incremental commits**: Each story = one atomic, revertible commit
2. **Test coverage**: Add tests before and after each extraction
3. **Feature flags**: Optional rollback path if needed
4. **Regression testing**: Manual verification after each phase
5. **Canary deployment**: Test in staging before production

---

## Phase Breakdown

### Phase 1: Foundation & Utilities
Extract pure utility functions with no side effects. These are the safest changes.

### Phase 2: State Management Hooks
Extract state initialization and management into focused hooks.

### Phase 3: Panel Operations Hooks
Extract panel toggle and constraint logic.

### Phase 4: Approvals Workflow Hooks
Extract the entire approvals subsystem.

### Phase 5: File Operations Hooks
Extract file opening and tab management.

### Phase 6: Layout Management Hooks
Extract Dockview initialization and restoration.

### Phase 7: Miscellaneous Hooks
Extract remaining concerns (URL sync, drag-drop, active panel).

### Phase 8: Component Extraction
Extract reusable UI components.

### Phase 9: Integration & Validation
Final integration testing and documentation.

---

## Success Metrics

1. **App.jsx reduced to < 300 lines** (from 1,459)
2. **Zero functional regressions** verified by tests
3. **100% of extracted hooks have unit tests**
4. **All existing tests continue to pass**
5. **No new Playwright E2E failures**
6. **Clean module dependency graph** (no cycles)

---

## Non-Goals

1. **Feature changes**: This is a refactor, not a feature addition
2. **Performance optimization**: Focus on correctness first
3. **API changes**: External behavior remains identical
4. **Design system updates**: No visual changes
5. **Backend changes**: Frontend-only refactoring

---

## Dependencies

- **bd-1ce**: Normalize frontend folder boundaries (CLOSED - prerequisite complete)
- Existing test coverage must be maintained
- No new external dependencies

---

## Timeline Considerations

This is a multi-phase effort designed to be interruptible. Each phase and story can be:
- Paused and resumed later
- Completed in isolation
- Validated independently

Stories are ordered to minimize risk and maximize early wins.

---

## Complete Story Breakdown (26 Stories)

### Phase 1: Foundation & Utilities (4 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.1 | Extract panelToggleUtils.js - Collapse/expand helper functions | None |
| bd-1qk.2 | Extract filePositioning.js - Smart file panel placement logic | None |
| bd-1qk.3 | Extract approvalUtils.js - Path normalization and title generation | None |
| bd-1qk.4 | Extract layoutUtils.js - Panel initialization and constraint helpers | None |

### Phase 2: State Management Hooks (3 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.5 | Create useAppState hook - Core application state initialization | bd-1qk.1,2,3,4 |
| bd-1qk.6 | Create useProjectRoot hook - Project metadata fetching | None |
| bd-1qk.7 | Create useBrowserTitle hook - Document title management | None |

### Phase 3: Panel Operations Hooks (2 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.8 | Create usePanelToggle hook - Panel collapse/expand logic | bd-1qk.1, bd-1qk.5 |
| bd-1qk.9 | Create useCollapsedState hook - Collapsed panel state with effects | bd-1qk.8 |

### Phase 4: Approvals Workflow Hooks (2 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.10 | Create useApprovals hook - Approval polling and state management | bd-1qk.3 |
| bd-1qk.11 | Create useApprovalPanels hook - Sync review panels with approvals | bd-1qk.10 |

### Phase 5: File Operations Hooks (2 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.12 | Create useTabManager hook - Tab state and persistence | bd-1qk.5 |
| bd-1qk.13 | Create useFileOperations hook - File opening and positioning logic | bd-1qk.2, bd-1qk.12 |

### Phase 6: Layout Management Hooks (2 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.14 | Create useLayoutInit hook - Dockview initialization and onReady handling | bd-1qk.4 |
| bd-1qk.15 | Create useLayoutRestore hook - Layout restoration and validation | bd-1qk.14 |

### Phase 7: Miscellaneous Hooks (4 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.16 | Create useUrlSync hook - URL query parameter synchronization | bd-1qk.13 |
| bd-1qk.17 | Create useDragDrop hook - Drag and drop file handling | bd-1qk.13 |
| bd-1qk.18 | Create useActivePanel hook - Active panel tracking for UI sync | bd-1qk.12 |
| bd-1qk.19 | Create usePanelParams hook - Panel parameter updates | bd-1qk.5 |

### Phase 8: Component Extraction (2 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.20 | Extract AppHeader component - Logo, title, and header actions | bd-1qk.8 |
| bd-1qk.21 | Extract CapabilityWarning component - Backend capability warnings | bd-1qk.5 |

### Phase 9: Integration & Validation (5 stories)
| ID | Title | Dependencies |
|----|-------|--------------|
| bd-1qk.22 | Integrate all hooks into App.jsx - Wire extracted modules together | All Phase 1-8 |
| bd-1qk.23 | Add comprehensive tests for all extracted modules | bd-1qk.22 |
| bd-1qk.24 | Run full regression testing and E2E validation | bd-1qk.22, bd-1qk.23 |
| bd-1qk.25 | Update documentation and add module architecture diagram | bd-1qk.24 |
| bd-1qk.26 | Cleanup and remove dead code from refactoring | bd-1qk.24 |

---

## Execution Order

Based on dependencies, work can proceed in this order:

**Can start immediately (no blockers):**
- bd-1qk.1, bd-1qk.2, bd-1qk.3, bd-1qk.4 (Phase 1 utilities)
- bd-1qk.6, bd-1qk.7 (standalone hooks)

**After Phase 1 utilities:**
- bd-1qk.5 (useAppState)

**After useAppState:**
- bd-1qk.8 (usePanelToggle)
- bd-1qk.12 (useTabManager)
- bd-1qk.19 (usePanelParams)
- bd-1qk.21 (CapabilityWarning)

**After approvalUtils:**
- bd-1qk.10 (useApprovals)

**Parallel tracks can proceed independently after their specific dependencies are met.**

---

## Commands for Working with This Epic

```bash
# View epic and all children
bd show bd-1qk

# See what's ready to work on
bd ready

# See blocked items
bd blocked

# Start working on a story
bd update bd-1qk.1 --status in_progress --claim

# Close a story
bd close bd-1qk.1 --reason "Implemented panelToggleUtils with tests"

# View dependency tree
bd dep tree bd-1qk

# Check epic completion status
bd epic status
```
