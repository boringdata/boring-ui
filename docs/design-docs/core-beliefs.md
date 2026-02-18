# Core Beliefs

These are the non-negotiable design principles that guide boring-ui development.

## 1. Capability Gating Over Feature Flags

The backend advertises what's available at runtime via `/api/capabilities`. The frontend adapts automatically. No compile-time flags, no environment-specific builds. A panel either has what it needs or it shows a clear error state.

## 2. Error-First Degradation

Missing capabilities must never produce blank screens, crashes, or silent failures. Every panel wrapped in `CapabilityGate` renders an actionable error state when its requirements are unmet. The user always sees something meaningful.

## 3. Composition Over Configuration

The backend is assembled from independently mountable routers. The frontend composes from independently registerable panes. You include only what you need. `create_app(routers=['files', 'git'])` gives you a minimal working backend. Adding a pane is one `registerPane()` call.

## 4. Config Deep Merge With Working Defaults

All configuration is optional. Defaults produce a functional application. User config is deep-merged, so you override only what you want. No need to replicate the full config to change one value.

## 5. Frontend and Backend Communicate Only Through HTTP/WS

No shared code, no direct imports across the front/back boundary. The API contract (REST + WebSocket) is the only coupling point. This enables independent deployment and testing.

## 6. Security by Default

- Path validation (`APIConfig.validate_path()`) is mandatory for all filesystem access
- Workspace plugins are disabled by default and guarded by an allowlist
- CORS is restrictive in production
- In hosted mode, capability tokens gate privileged operations

## 7. Layout Resilience

Layout state must never block the application. The recovery chain: saved layout -> structural validation -> versioned migration -> last-known-good backup -> fresh defaults. At least one path always succeeds.

## 8. Behavior-Neutral Refactors

Refactors must preserve existing behavior unless explicitly scoped otherwise. No drive-by improvements, no opportunistic cleanups in the same change. Test before and after.
