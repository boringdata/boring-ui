# Chat-Centered Surface Redesign Plan

## Objective
Transform boring-ui from an IDE-first layout into a chat-first AI agent workspace.

## Current vs. Target Layout
- **Current (IDE-first)**: Left sidebar (file tree) | Center (editor tabs) | Right (agent chat).
- **Target (Chat-first / Stage + Wings)**: Nav Rail (left) | Left Wing (browser) | Center Stage (chat) | Right Wing (artifact workbench).

## Core Concepts
1. **Nav Rail (48px)**: Choose what to browse (Files, Git, Search, Sessions).
2. **Left Wing**: Browse/list items (File tree, search results, session history).
3. **Center Stage**: Active chat session. This is the primary focal point of the application.
4. **Right Wing**: Artifact workbench (Editors, Diffs, Terminal). Persistent across sessions.

## Implementation Steps
1. **Layout Restructuring**:
   - Create the new three-zone layout components.
   - Implement the thin navigation rail on the far left.
2. **Chat Migration**:
   - Move the chat component to the Center Stage.
   - Ensure the chat is always visible and central to the user experience.
3. **Left Wing Setup**:
   - Move the file tree from the main left sidebar to the Left Wing.
   - Implement dynamic switching of Left Wing content based on Nav Rail selection.
4. **Right Wing Setup**:
   - Move the editor tabs and terminal to the Right Wing.
   - Ensure the Right Wing state (open files, terminal sessions) persists independently of the active chat session.
5. **State Management**:
   - Update global layout state to manage the visibility and widths of the Left and Right wings.
   - Implement responsive collapsing/expanding logic.