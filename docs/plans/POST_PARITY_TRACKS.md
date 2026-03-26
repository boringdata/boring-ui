# Post-Parity Tracks

After the TypeScript migration reaches parity (Phase 7 complete), three extension tracks are available. These are **not** part of the migration — they are new capabilities that the TS architecture enables.

## Track 1: JustBash Browser Backend (Tier 3)

**Status:** Experimental / Not started

Add a browser-only workspace backend using JustBash WASM:
- File operations via in-memory filesystem (RAM, lost on reload)
- Shell execution via JustBash WASM (100+ builtins: grep, sed, awk, jq)
- No real git, no npm, no pip
- Instant startup, zero persistence, zero server dependency

**Config:**
```toml
[workspace]
backend = "justbash"
```

**Implementation:**
- Create `src/front/providers/data/justBashProvider.js`
- Implement `WorkspaceBackend` interface with JustBash WASM
- Capabilities: `workspace.files`, `workspace.exec` (no `workspace.git`, no `workspace.python`)

**Use cases:** Quick demos, offline usage, educational environments.

## Track 2: AI SDK Runtime

**Status:** Future / Not started

Replace or supplement the PI agent runtime with Vercel AI SDK:
- Pluggable model providers (not PI-only)
- Streaming via AI SDK's `useChat` / `streamText`
- Tool registration via AI SDK tool format

**Config:**
```toml
[agent]
runtime = "ai-sdk"  # Currently rejected at startup
```

**Implementation:**
- Create `src/front/providers/ai-sdk/` adapter
- Update `resolveAgentRuntime()` to handle `ai-sdk`
- Frontend: new AgentPanel variant using AI SDK hooks

**Blocked on:** PI deprecation decision. Currently PI is the only supported runtime.

## Track 3: Server-Side PI

**Status:** Deferred / Architecture ready

Run PI in-process on the Node.js backend instead of in the browser:
- Server holds the conversation loop
- Tool calls execute directly via BwrapBackend (no HTTP round-trip)
- User provides API key (passed to server PI)
- Faster tool execution for complex workflows

**Config:**
```toml
[agent]
runtime = "pi"
placement = "server"  # Requires workspace.backend = "bwrap"
```

**Implementation:**
- Import PI agent core into Node.js server process
- Create server-side tool wiring (direct BwrapBackend calls)
- WebSocket streaming from server PI to frontend
- Requires `DATABASE_URL` for workspace state

**Blocked on:** PI Node.js compatibility testing, WebSocket streaming protocol design.

## Priority Order

1. **JustBash** — lowest effort, highest demo value
2. **Server PI** — architecture ready, needs PI compatibility testing
3. **AI SDK** — most ambitious, depends on runtime decision
