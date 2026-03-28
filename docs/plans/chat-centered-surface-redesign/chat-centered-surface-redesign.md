# Chat-Centered Surface Redesign

## Intent

Transform boring-ui from an IDE-first layout into a chat-first AI agent workspace.

**Today**: File tree (left) | Editor tabs (center) | Agent chat (right sidebar)

**Target**: Nav rail (48px icon strip, left) | Chat (center stage, always visible) | The Surface (floating artifact display island, right, collapsible)

## Core Principles

1. **Chat is the command center.** Always visible, centered, locked. Everything flows from conversation.
2. **The Surface is the agent's display.** A floating island that renders anything: code diffs, charts, tables, PDFs, dashboards, images. Type-agnostic. Hidden until needed — appears when the agent produces an artifact or user clicks one.
3. **The nav rail is minimal.** 48px icon strip: brand, new chat, session history toggle, settings. No file tree. No data catalog. Those live inside the Surface explorer.
4. **Two independent workbenches.** Chat (session-scoped — switches with conversations) and Surface (persistent — your open artifacts stay across session switches).
5. **Everything is an artifact.** Code files, data tables, charts, documents — they all render in the Surface through a polymorphic renderer. The Surface has an explorer sidebar (toggled, collapsed by default) to browse artifacts, and a viewer to display the active one.
6. **Stripe/Linear quality.** Floating island with backdrop blur + inner highlight. Pill-shaped chat input. White send button. Gradient artifact cards. Spring animations. Mac-style scrollbars. No hard borders.

## The Layout

```
DEFAULT (clean):
┌──┐┌──────────────────────────────────┐
│🕐││          Chat (680px max)        │
│ B││     centered, breathing room     │
└──┘└──────────────────────────────────┘

WITH SURFACE (artifact opened):
┌──┐┌──────────────────┐┌─ floating island ──────────────┐
│🕐││                  ││ [📂 Artifacts] [tab1] [tab2]  ✕│
│ B││  Chat            ││ ┌explorer┐┌───────────────────┐│
│  ││  (still centered)││ │DATA  3 ││ 📊 Q3 vs Q4 Rev  ││
│  ││                  ││ │ chart ●││ [chart rendering] ││
│  ││                  ││ │ table  ││                   ││
│  ││                  ││ │DOCS  1 ││                   ││
│  ││                  ││ │ deck   ││ [export]          ││
│  ││                  ││ └────────┘└───────────────────┘│
└──┘└──────────────────┘└────────────────────────────────┘
```

## Three Zones

### 1. Nav Rail (48px, left)
- Icon strip, always visible
- Brand icon at top
- `[+]` New chat (accent button)
- `[🕐]` Session history (toggles expandable panel)
- `[⚙]` Settings, `[👤]` Profile (bottom-pinned)
- Expandable 220px panel slides out for session history
- Sessions grouped by date (Today / Yesterday), colored status dots (active / paused / idle)

### 2. Chat (center, flex)
- Always visible, locked, uncloseable
- Messages with `max-width: 680px`, centered
- Artifact cards in chat: clickable, icon + title + type + chevron
- Active artifact highlighted when viewing in Surface
- Pill-shaped input bar centered, ⌘K keyboard hints
- White send button (high contrast primary action)
- User/agent avatars on messages

### 3. The Surface (right, floating island)
- Hidden by default, appears when first artifact is opened
- Floating rounded island: `border-radius: 16px`, `backdrop-filter: blur(16px)`, layered shadows
- Top bar: `[📂 Artifacts N]` explorer toggle + pill tabs + close button
- **Explorer sidebar** (190px, collapsed by default): artifacts grouped by category (Data, Documents, Code), dot on active
- **Viewer**: polymorphic renderer — charts, tables, documents, code diffs, images, dashboards
- Each artifact type has its own renderer, wrapped in standard card chrome (title, type, export)
- Collapsible to 36px handle, resizable via drag handle
- Persistent across session switches
- ⌘2 toggles

## Keyboard Shortcuts
- `⌘K` — Command palette (search anything)
- `⌘2` — Toggle Surface
- `⌘N` — New chat session
- `Esc` — Focus chat input

## Artifact Types
- **Code**: diff view with accept/reject per hunk
- **Chart**: bar, line, pie charts with legends and notes
- **Table**: interactive grid with sortable headers
- **Document**: PDF viewer or styled rich text
- **Image**: viewer with zoom
- **Dashboard**: live data visualization
- Agent pushes artifacts proactively — chat is control channel, Surface is data channel

## Session Model
- Session list in nav rail expandable panel
- Click session → center chat switches, Surface stays (artifacts persist)
- `●` active / `◐` paused / `○` idle status indicators
- No multi-chat panes — fast session switching instead

## Design Language (from POC)
- Dark theme: `#0a0a0a` canvas, `rgba(17,17,19,.85)` surface with blur
- No hard borders — `rgba(255,255,255,0.06)` subtle borders only
- Surface island: multi-layer shadow + inner top-highlight
- Typography: Inter 14px body, -0.01em letter-spacing, JetBrains Mono for code
- Transitions: `cubic-bezier(0.16,1,0.3,1)` (emerge), `cubic-bezier(0.25,1,0.5,1)` (spring)
- Gradient artifact cards, Mac-style floating scrollbars, scroll fade masks

## POC

Working prototype at `poc-stage-wings/` — validated full design with mock data and all interactions. Design iterated through 8 rounds of Gemini 3.1 Pro + OpenAI o3 feedback.

## Validated By
- **Gemini 3.1 Pro** (8 rounds): layout architecture, spatial UX, nav rail progressive disclosure, polish
- **OpenAI o3**: layout selection from 12 candidates, pixel math, keyboard shortcuts
- Both independently picked "Stage + Wings" from 12 layout variations
- Both validated "Everything is an Artifact" over IDE-centric file tree approach
