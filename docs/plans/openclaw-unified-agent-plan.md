# Plan: Unified Agent via OpenClaw

## Status

**Draft v5** — 2026-03-23 (Round 1 architectural refinement)
**Supersedes**: `~/.claude/plans/giggly-watching-raven.md` (OpenClaw-Style Messaging Gateway, 5-phase plan)
**Builds on**: PI agent integration (`src/pi_service/`), messaging module (`modules/messaging/`), `AgentRegistry` + `PiHarness` pattern, Fly.io deployment

---

## Executive Summary

boring-ui has two separate agent runtimes with incompatible tools doing the same thing. Rather than building a third (the 5-phase messaging gateway plan), we **embed OpenClaw as a library** inside the existing PI service Node.js process — one sidecar, one V8 heap. OpenClaw provides memory, channels, and skills; boring-ui provides tools and workspace integration. Tools are organized by execution context, not by runtime.

---

## Part 1: Current State — Three Runtimes, Siloed Tools

| Runtime | Location | Tools | Problem |
|---|---|---|---|
| Frontend PI (browser) | `src/front/providers/pi/defaultTools.js` | 22 tools (file, git, exec, UI) | Browser-only, can't share to server |
| Server PI | `src/pi_service/server.mjs` + `tools.mjs` | 1 tool (exec_bash) + 4 shared UI tools | Correct for server, but isolated |
| Messaging module | `src/back/boring_ui/api/modules/messaging/` | 6 tools (Python, raw Anthropic API) | Duplicate of PI, stateless, single-channel |

The `AgentHarness` protocol (`harness.py`) defines session lifecycle but has **no concept of tools**. Each runtime brings its own tools internally. Adding OpenClaw as a separate process would create a 4th runtime.

---

## Part 2: Tool Architecture — Three Categories

Tools are organized by **where they can run**, not by which harness uses them.

### 2.1 Frontend-Agent Mode Tools (Browser PI Only)

These exist because the browser has **no shell**. The agent interacts with LightningFS (IndexedDB) and isomorphic-git via JavaScript APIs.

**Stay in `src/front/providers/pi/defaultTools.js` — not shared.**

| Category | Tools |
|---|---|
| File ops | `read_file`, `write_file`, `list_dir`, `delete`, `rename_file`, `move_file`, `search_files` |
| Git ops | `git_status`, `git_diff`, `git_show`, `git_add`, `git_commit`, `git_push`, `git_pull`, `git_init`, `git_branches`, `git_create_branch`, `git_checkout`, `git_merge` |
| Exec | `python_exec` (if runtime available) |

These tools call `provider.files.*` and `provider.git.*` — browser-side JavaScript APIs. They only make sense in the browser context where there is no shell. **19 tools.** Note: `open_file` and `list_tabs` also exist here via window bridges (`PI_OPEN_FILE_BRIDGE`, `PI_LIST_TABS_BRIDGE`) but those are the browser-local transport — the shared versions below cover all modes.

### 2.2 Lite + Backend Mode Tools (Server-Side)

On the server there's a real filesystem and shell. The agent does everything via bash.

| Tool | Description |
|---|---|
| `exec_bash` | Execute shell command in workspace. Agent uses it for file ops, git, python, everything. |

This is what `pi_service/server.mjs` already does — one tool, and it works. The messaging module's 6 structured Python tools were unnecessary duplication.

### 2.3 Shared Tools (All Modes, All Harnesses)

UI state awareness — the agent knows what the user sees regardless of surface (browser, Telegram, Slack). In backend-agent mode these call the **backend ui_state API**. In frontend-agent mode the same tool names exist via window bridges in `defaultTools.js`.

**Already implemented in `src/pi_service/tools.mjs`** (loaded when `backendUrl` is set, i.e. backend-agent mode).

| Tool | Backend endpoint | Description |
|---|---|---|
| `list_panes` | `GET /api/v1/ui/panes` | What panels are open, which is active |
| `get_ui_state` | `GET /api/v1/ui/state/latest` | Full UI snapshot (panels, active file, project root) |
| `open_file` | `POST /api/v1/ui/commands` | Open file in editor (enqueues `open_panel` command, frontend polls at 750ms) |
| `list_tabs` | `GET /api/v1/ui/panes` | Editor tabs only + active file marker |

**How it works end-to-end:**
1. Frontend publishes UI state to backend via `PUT /api/v1/ui/state` (already wired in `App.jsx`, debounced on layout change)
2. Agent calls `list_panes` / `get_ui_state` / `list_tabs` → reads from backend store
3. Agent calls `open_file` → enqueues `open_panel` command via `POST /api/v1/ui/commands`
4. Frontend polls `GET /api/v1/ui/commands/next` every 750ms (already wired in `App.jsx`) → executes command → opens file in editor

**Note**: These tools require a browser client to have published state. A Telegram-only agent (no browser open) will get "No browser client is connected" errors. These are "browser-present" tools callable from any runtime, not universally functional.

### 2.4 Child App Custom Tools

Child apps add tools to whichever category fits:

```toml
# boring-doctor/boring.app.toml
[agents.tools]
extra = ["src/tools/medical.mjs"]   # adds patient_lookup, knowledge_search
```

Custom tools follow the same pi-agent-core TypeBox format and are loaded by the server-side agent process.

### 2.5 System Prompt Composition

Each mode manages its own system prompt, but boring-ui provides context:

| Source | Who provides | When |
|---|---|---|
| Base persona | Server process (PI or PI+OpenClaw) | Always |
| Workspace context | `buildSessionSystemPrompt()` in tools.mjs | Session creation |
| Tool availability | Auto-generated from registered tools | Session creation |
| Memory context | OpenClaw only (daily logs, MEMORY.md) | Session creation + compaction |
| Child app instructions | `boring.app.toml` `[agents.system_prompt]` | Session creation |

**Key rule**: boring-ui provides workspace context and child app instructions. OpenClaw decides how to compose them with its memory management.

### 2.6 Summary

```
┌─────────────────────────────────────────────────────┐
│                                                       │
│  FRONTEND-AGENT MODE (browser PI only)                │
│    defaultTools.js                                    │
│    7 file + 10 git + python_exec + open_file +        │
│    list_tabs                                          │
│    → provider.files.*, provider.git.*, window bridges │
│                                                       │
│  LITE + BACKEND MODE (server-side)                    │
│    exec_bash                                          │
│    → child_process.exec / shell                       │
│                                                       │
│  SHARED (all modes, browser-present)                  │
│    list_panes, get_ui_state, open_file, list_tabs     │
│    → backend /api/v1/ui/* endpoints                   │
│    → already implemented in tools.mjs                 │
│                                                       │
│  CHILD APP TOOLS (any mode)                           │
│    boring.app.toml [agents.tools] extra               │
│    → custom per child app                             │
│                                                       │
├─────────────────────────────────────────────────────┤
│                                                       │
│  Single server-side process: server.mjs               │
│    PI agent (always) + OpenClaw (opt-in, embedded)    │
│                                                       │
└─────────────────────────────────────────────────────┘
```

---

## Part 3: Why OpenClaw

OpenClaw (`openclaw@2026.3.13` on npm) is built on `@mariozechner/pi-agent-core@0.58.0` — same ecosystem as boring-ui (`^0.52.12`). It's not just another harness. What OpenClaw adds **inside** is what matters.

### 3.1 Replaces Code We'd Otherwise Build

| Feature | Current state | OpenClaw provides |
|---|---|---|
| Session memory | PI: in-memory Map (lost on restart). Messaging: stateless | Persistent markdown files + vector search (LanceDB). Auto-flush before compaction |
| Multi-turn conversations | PI: in-memory only. Messaging: none | Persistent with auto-compaction |
| Messaging channels | 1 (Telegram, custom Python, stateless) | 22+ via plugin SDK (activate when credentials present) |
| Channel abstraction | Telegram hardcoded | Self-registering plugin pattern |
| Bot token security | Plaintext JSON | DM pairing, webhook replay protection, credential proxy |

### 3.2 Interesting for Future Use

| Feature | Use case |
|---|---|
| Skills system (50+ bundled, ClawHub) | Child apps compose capabilities |
| Browser automation (CDP) | Web scraping, signed-in automation |
| Subagent orchestration | Multi-task delegation with session hierarchy |
| Workflow engine (Lobster) | Cron, scheduled automation, approval workflows |
| Voice calls (Twilio/Telnyx) | boring-doctor patient interaction |
| Canvas (A2UI) | Agent-driven panel rendering |
| OpenTelemetry | Production observability |

### 3.3 What boring-ui Owns (Not OpenClaw)

- Workspace provisioning (Fly.io machines)
- Multi-tenancy and auth (Neon Auth, session cookies)
- Frontend (React, DockView panels)
- File/git/exec backend services (FastAPI)
- Tool definitions — boring-ui and child apps define tools, OpenClaw consumes them
- Deploy (Fly.io, bui CLI)
- System prompt composition for workspace context

---

## Part 4: Integration Architecture — Embedded, Not Sidecar

### 4.1 The Key Insight: One Process

`PiHarness` already spawns `node src/pi_service/server.mjs` — that's one Node.js process. Spawning a **second** process for OpenClaw would double Node.js memory (~60-80MB V8 overhead alone) and add IPC complexity.

Instead: **import OpenClaw as a library into the existing `server.mjs`**.

```
Current:     Python (FastAPI) → spawns Node.js (server.mjs)     = 1 Node process
Plan (bad):  Python (FastAPI) → spawns Node.js (server.mjs)
                              → spawns Node.js (openclaw)        = 2 Node processes

This plan:   Python (FastAPI) → spawns Node.js (server.mjs
                                  + import openclaw)             = 1 Node process
```

`PiHarness` stays as-is — same spawn, health check, proxy pattern. `server.mjs` gains OpenClaw capabilities internally when `OPENCLAW_ENABLED=true`.

### 4.2 Process Architecture

```
Fly Firecracker VM (per workspace)           ← OS-level isolation (separate kernel)
  ├── Python (FastAPI + uvicorn)             ← workspace APIs, auth, control plane
  │     └── PiHarness                        ← spawns + health-checks the Node.js sidecar
  └── Node.js (server.mjs)                  ← ONE process, always
        ├── PI agent sessions                ← existing: create, stream, history, stop
        ├── exec_bash + shared UI tools      ← existing: tool contract
        ├── OpenClaw gateway (embedded)      ← NEW: import('openclaw'), opt-in
        │     ├── Memory (markdown + vector) ← persistent sessions, auto-compaction
        │     ├── Channels (Telegram, Slack) ← self-registering plugins
        │     └── Skills                     ← composable per child app
        └── bwrap (exec_bash sandboxing)     ← existing defense-in-depth
```

### 4.3 What Changes in server.mjs

```javascript
// server.mjs — conceptual change
import { Agent } from '@mariozechner/pi-agent-core'
import { createWorkspaceTools } from './tools.mjs'

// NEW: conditionally import OpenClaw
const OPENCLAW_ENABLED = process.env.OPENCLAW_ENABLED === 'true'
let gateway = null
if (OPENCLAW_ENABLED) {
  const { Gateway } = await import('openclaw')
  gateway = new Gateway({
    sandbox: 'off',
    plugins: (process.env.OPENCLAW_PLUGINS || 'memory').split(','),
    // OpenClaw consumes the same tools as PI
    tools: createWorkspaceTools(context),
  })
  await gateway.start()
}

// Existing PI session handling stays identical
// OpenClaw handles channels (Telegram webhooks) internally
// Both use the same tool definitions
```

### 4.4 No New Harness Needed

The `OpenClawHarness` from earlier drafts is eliminated. Instead:
- `PiHarness` spawns `server.mjs` (unchanged)
- `server.mjs` conditionally loads OpenClaw (new, behind env flag)
- `boring.app.toml` `[agents.openclaw]` config → translated to env vars by `PiHarness`

---

## Part 5: Trade-off Analysis

### Option A: OpenClaw Embedded in server.mjs (Recommended)

`npm install openclaw`, import in `server.mjs`, one process.

| Pro | Con |
|---|---|
| 22+ channels, memory, skills — free | 94.8MB package, 55 deps |
| Same pi-agent-core ecosystem | pi-agent-core 0.52→0.58 version bump |
| ONE Node.js process — saves ~60-80MB RAM | Must verify OpenClaw works as library (not just CLI) |
| No new harness, no new sidecar, no IPC | Two config systems (env vars mitigate) |
| `PiHarness` unchanged — zero risk to existing flow | Must understand OpenClaw internals for debugging |
| Tools are mode-agnostic — no lock-in | 512MB RAM still tight (but better than 2 processes) |
| Rollback = remove `OPENCLAW_ENABLED=true` env var | External dependency |

### Option B: Cherry-Pick Features

Extract memory + channel registry from OpenClaw/NanoClaw, adapt.

| Pro | Con |
|---|---|
| Minimal footprint | Maintenance fork — diverges from upstream |
| Full architectural control | Reimplementing tested code |
| Only ships what we use | No skills, browser, voice, canvas without re-extracting |
| Simpler config | Each new feature = manual extraction |

**Risk**: Becomes a maintenance fork. Features we'd want later require starting over.

### Recommendation

**Option A.** Embedding OpenClaw in the existing `server.mjs` keeps the one-process model, saves RAM, and avoids a new harness. Rollback is `OPENCLAW_ENABLED=false` — existing PI behavior is completely untouched.

---

## Part 6: Deployment on Fly.io

**Constraint**: No Docker-in-Docker. Fly machines are Firecracker microVMs.

**Solution**: `sandbox: "off"`, embedded in existing Node.js process.

**Memory budget** (512MB machine):

| Component | Estimated RSS | Source |
|---|---|---|
| Linux kernel + OS | ~30MB | Firecracker baseline |
| Python (FastAPI + uvicorn) | ~80-120MB | Measured on current deploy |
| Node.js (server.mjs + OpenClaw embedded) | ~120-200MB | Single V8 heap, depends on plugins |
| LanceDB (if vector memory enabled) | ~50-100MB | Memory-mapped, grows with index |
| Headroom for agent workload | ~50MB | Tool execution, session state |
| **Total** | **~330-500MB** | |

**Decision**: If Phase 1 measurements exceed 450MB, bump to 1GB machines. Cost impact: ~$3/mo per workspace machine (Fly shared-cpu-1x 1GB).

---

## Part 7: Dependency Isolation Strategy

`boring-ui` depends on `pi-agent-core ^0.52.12`. OpenClaw pins `0.58.0`. Three mitigation paths:

1. **Best case**: 0.58 is backward-compatible. Bump boring-ui to `^0.58`. One version.
2. **Moderate**: Frontend needs 0.52, server needs 0.58. Use `npm overrides` to pin frontend bundle to 0.52 (Vite tree-shakes server-only code).
3. **Worst case**: Incompatible. Install OpenClaw in `vendor/openclaw/` with its own `package.json`. Dynamic `import()` from server.mjs. ~50MB disk but full isolation.

**Phase 1 determines which path.**

---

## Part 8: Implementation Plan

### Phase 0: Clean Up + Verify Shared Tools (1-2 days)

**Goal**: Eliminate redundant tool implementations. Confirm shared tools work.

- [ ] Mark as deprecated (do NOT delete yet — Telegram must keep working until Phase 3):
  - `src/back/boring_ui/api/modules/messaging/agent.py`
  - `src/back/boring_ui/api/modules/messaging/tool_executor.py`
  - `src/back/boring_ui/api/modules/messaging/tools.py`
- [ ] Confirm `pi_service/server.mjs` uses `exec_bash` + shared UI tools (already the case)
- [ ] Confirm `defaultTools.js` frontend tools stay in place (already correct)
- [x] ~~Create shared UI tools~~ — **DONE**: `list_panes`, `get_ui_state`, `open_file`, `list_tabs` in `tools.mjs`
- [ ] Verify: server PI agent can report open panels and open files in the editor

### Phase 1: OpenClaw Compatibility Check (2-3 days)

**Goal**: Confirm OpenClaw works as an embedded library in server.mjs.

- [ ] `npm install openclaw` on dev VM
- [ ] Verify pi-agent-core 0.52→0.58 — check breaking changes in `src/front/providers/pi/` (`Agent` constructor, `subscribe`, `state.isStreaming`, `prompt()`, `abort()`, `setTools()`, `setSystemPrompt()`)
- [ ] Also bump `@mariozechner/pi-ai` 0.52→0.58 — verify `registerBuiltInApiProviders()`, `getModel()`
- [ ] Determine dependency isolation path (see Part 7)
- [ ] Test embedded import: `const { Gateway } = await import('openclaw')` in server.mjs
- [ ] Boot OpenClaw gateway with `sandbox: "off"` — confirm no mandatory container initialization
- [ ] Register `exec_bash` + shared UI tools into OpenClaw — verify tools are callable
- [ ] Measure memory footprint (single process, minimal plugins: memory only). **Target: ≤ 450MB.**
- [ ] Verify OpenClaw health status is queryable (for PiHarness health checks)

### Gate: Phase 1 → Phase 2 Decision

**Phase 2 proceeds ONLY if all pass:**

| Criterion | Pass | Fail action |
|---|---|---|
| pi-agent-core 0.58 works with browser PI | Frontend tests pass | Isolate deps (Part 7 path 2 or 3) |
| OpenClaw boots with `sandbox: "off"` | Clean startup, no container errors | Investigate upstream; may block adoption |
| Memory ≤ 450MB (Python + Node.js + OpenClaw) | Measured on Fly-equivalent VM | Plan for 1GB machines, re-cost |
| OpenClaw accepts external tools | `exec_bash` registered and callable | File upstream issue or wrap injection |
| OpenClaw works as embedded import | `import('openclaw')` in server.mjs | Fall back to sidecar (2-process model) |

**If 2+ criteria fail**: Pivot to Option B (cherry-pick memory + channel registry).

### Phase 2: Embed OpenClaw in server.mjs (2-3 days)

**Goal**: server.mjs gains OpenClaw capabilities behind `OPENCLAW_ENABLED` flag.

- [ ] Add OpenClaw initialization to `server.mjs`:
  - Conditional `import('openclaw')` when `OPENCLAW_ENABLED=true`
  - Pass workspace tools (exec_bash + shared UI tools) to OpenClaw gateway
  - Start OpenClaw gateway in-process
  - Expose OpenClaw health in existing `/health` endpoint
- [ ] Add config translation in `PiHarness._process_env()`:
  - `boring.app.toml` `[agents.openclaw]` → env vars (`OPENCLAW_ENABLED`, `OPENCLAW_PLUGINS`, etc.)
  - No separate `openclaw.json` needed — env vars are simpler
- [ ] Update `boring.app.toml` schema:
  ```toml
  [agents]
  default = "pi"

  [agents.openclaw]
  enabled = false             # sets OPENCLAW_ENABLED=true
  plugins = ["memory"]        # sets OPENCLAW_PLUGINS=memory
  sandbox = "off"

  [agents.tools]
  extra = []                  # child apps add custom tools here

  [agents.system_prompt]
  append = ""                 # child app instructions appended to base prompt
  ```
- [ ] Add health + metrics to PiHarness health check:
  - OpenClaw process alive, session count, memory RSS
  - Last successful agent turn timestamp
  - Channel connection status (if Telegram enabled)
- [ ] Verify: CompanionPanel works identically with and without `OPENCLAW_ENABLED`

### Phase 3: Memory + Channels (2-3 days)

**Goal**: Persistent multi-turn conversations, Telegram via OpenClaw.

- [ ] Configure OpenClaw memory (markdown daily logs + MEMORY.md per workspace)
- [ ] Verify memory persists across restarts, auto-compaction works
- [ ] Enable OpenClaw Telegram plugin (`OPENCLAW_PLUGINS=memory,telegram`)
- [ ] Shrink `modules/messaging/router.py` to thin proxy (~50 lines):
  - Connect/disconnect → configure OpenClaw Telegram plugin
  - Webhook → forward to OpenClaw (in-process, not HTTP)
  - List channels → query OpenClaw
- [ ] Delete deprecated files: `agent.py`, `tool_executor.py`, `tools.py`, `telegram.py`
- [ ] Test: Telegram → multi-turn conversation with memory recall

### Phase 4: Child App Tools (1-2 days)

**Goal**: Child apps can define custom tools loaded by server.mjs.

- [ ] Document tool authoring format (pi-agent-core TypeBox schema + execute function)
- [ ] Implement `boring.app.toml` `[agents.tools]` extra loading in server.mjs
- [ ] Prototype: boring-doctor adds `patient_lookup` tool, works with and without OpenClaw
- [ ] Update `deploy/shared/Dockerfile.backend` — install OpenClaw when enabled
- [ ] Verify: deploy to Fly staging with OpenClaw enabled

### Post-MVP

- Add Slack, Discord channels (plugin toggle)
- Enable LanceDB vector memory for semantic search
- Enable browser automation plugin
- Enable voice-call plugin for boring-doctor
- Enable Lobster workflow engine
- Explore Canvas (A2UI) ↔ DockView integration
- Add integration tests in `tests/smoke/` for agent tool → backend → frontend flow

---

## Part 9: What Changes, What Stays

### Deleted (Phase 3)

| File | Reason |
|---|---|
| `modules/messaging/agent.py` | OpenClaw handles agent loop |
| `modules/messaging/tool_executor.py` | exec_bash covers server-side |
| `modules/messaging/tools.py` | Duplicate tool definitions |
| `modules/messaging/telegram.py` | OpenClaw Telegram plugin replaces it |

### New

No new files. OpenClaw is embedded in existing `server.mjs`.

### Modified

| File | Change |
|---|---|
| `pi_service/server.mjs` | Conditional `import('openclaw')` + gateway init behind `OPENCLAW_ENABLED` |
| `pi_service/tools.mjs` | **DONE** — shared UI tools + path traversal fix + auth forwarding |
| `modules/messaging/router.py` | Shrink to thin proxy (in-process calls to OpenClaw, not HTTP) |
| `agents/pi_harness.py` | Add OpenClaw env vars to `_process_env()`, extend health check |
| `package.json` | Add `openclaw`, bump `pi-agent-core` |
| `boring.app.toml` | Add `[agents.openclaw]`, `[agents.tools]`, `[agents.system_prompt]` |
| `Dockerfile.backend` | Conditionally install OpenClaw |

### Unchanged

| File | Reason |
|---|---|
| `agents/harness.py` | Abstract interface — unchanged |
| `agents/registry.py` | Harness-agnostic — unchanged |
| `front/providers/pi/defaultTools.js` | Browser-only tools, correct as-is |
| `front/providers/pi/*` | Browser PI agent stays for offline/lightweight |
| `front/components/CompanionPanel` | Same HTTP/SSE interface |

---

## Part 10: Decision Summary

| Question | Answer |
|---|---|
| Where do tools live? | Three categories: frontend-agent (`defaultTools.js`), server-side (`exec_bash`), shared (`list_panes`, `get_ui_state`, `open_file`, `list_tabs`). |
| Who owns tools? | boring-ui + child apps. Runtimes consume them. |
| Why `exec_bash` only on server? | Real shell covers everything. Structured tools exist for browser where there's no shell. |
| How does OpenClaw integrate? | Embedded in `server.mjs` via `import('openclaw')`. One Node.js process. No new harness. |
| Why not a separate process? | PiHarness already spawns one Node.js process. A second would waste ~60-80MB RAM and add IPC complexity. |
| Why OpenClaw? | Memory, 22+ channels, skills, auto-compaction. Same pi-agent-core. |
| Can we roll back? | `OPENCLAW_ENABLED=false`. PI behavior completely untouched. |
| What about Fly.io? | `sandbox: "off"`. Single process. Target ≤ 450MB. Bump to 1GB if needed. |
| What if OpenClaw can't embed? | Gate after Phase 1. Fall back to 2-process sidecar or Option B (cherry-pick). |

---

## Part 11: Review Findings (2026-03-22)

### Fixed (code changes in `tools.mjs`)

- **Auth tokens not forwarded** — `fetchBackendJson` now forwards `authToken` via `Authorization: Bearer` header.
- **Network errors not caught** — `fetchBackendJson` wraps `fetch()` in try/catch.
- **Path traversal in exec_bash** — `cwd` uses `path.resolve()` + validates result within `wsRoot`.
- **No-browser-connected error** — 404 returns `"No browser client is connected"` not internal text.
- **Content-Type on GETs** — Only set on requests with body.
- **Dead uppercase header lookups** — Removed; Node.js lowercases all headers.

### Acknowledged Risks

- **pi-agent-core 0.52→0.58** — 6-minor-version jump. Phase 1 bumped to 2-3 days. Must also bump `pi-ai`.
- **npm semver conflict** — Three mitigation paths defined in Part 7. Phase 1 determines which.
- **512MB RAM** — Target ≤ 450MB with single process. Phase 1 produces actual measurements. 1GB fallback costed.
- **Phase 3 rollback** — Not free after Telegram code deleted. Git revert required. Zero-cost only through Phase 2.
- **Messaging module timing** — Files deprecated in Phase 0, deleted in Phase 3 only when OpenClaw replaces them.
- **Shared UI tools require browser** — Return clean error when no browser client connected. Not universal.
- **SSRF via `backend_url`** — `resolveSessionContext` accepts from payload. Add URL allowlist for hosted mode (post-MVP).

### Accepted

- `list_tabs` / `list_panes` overlap — intentional convenience.
- Tool name collision in dual-mode — browser and server never in same process.
- `exec_bash` timeout → exit code 1 — acceptable, documented.
- `editor` component name contract — stable, set in `panes.jsx`.

### Deferred

- OpenClaw version coupling — monitor upstream.
- Config translation — use env vars, not generated JSON.
- Testing — extend `tests/smoke/` with agent tool integration tests.
- CompanionPanel SSE contract — verify event names match if OpenClaw handles sessions directly.
- `AgentHarness` protocol extension — may need `handle_channel_event` for Telegram webhooks.

---

## Appendix A: OpenClaw Plugin SDK

`import { ... } from 'openclaw/plugin-sdk/{name}'`:

**Channels**: telegram, slack, discord, whatsapp, signal, imessage, bluebubbles, irc, matrix, msteams, googlechat, feishu, line, mattermost, nostr, synology-chat, tlon, twitch, zalo, acpx

**Capabilities**: core, llm-task, thread-ownership, diffs, open-prose, lobster, copilot-proxy

**Infrastructure**: device-pair, phone-control, talk-voice, voice-call, diagnostics-otel

**Testing**: test-utils, compat

## Appendix B: Dependency Overlap

```
boring-ui:                           OpenClaw:
  @mariozechner/pi-agent-core ^0.52    @mariozechner/pi-agent-core 0.58
  @mariozechner/pi-ai ^0.52            @mariozechner/pi-ai 0.58
  @sinclair/typebox ^0.34              @sinclair/typebox 0.34
```
