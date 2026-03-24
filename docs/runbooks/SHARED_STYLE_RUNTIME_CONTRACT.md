# Shared Style Runtime Contract

This runbook documents the minimal runtime-facing shared-style assumptions that Phase 1
leaves behind.

Scope of this document:

- docs-level contract only
- no compiler policy or allowlist enforcement
- no new runtime infrastructure

## Phase 1 Guarantees

Runtime and child panel work may assume the following are true:

1. host app imports `boring-ui/style.css` exactly once at startup
2. shared primitives and base styles come from that host-loaded stylesheet
3. token and theme bridge is available through `src/front/styles/tokens.css` as part of
   `boring-ui/style.css`
4. theme state is expressed through document-root `data-theme` (`light` or `dark`)
5. runtime panels should consume shared token/semantic variables rather than shipping
   separate baseline CSS copies

## Runtime Root Defaults

Phase 1 runtime-root defaults that downstream work should preserve:

- one shared stylesheet import at host boot
- one document-root theme selector (`data-theme`)
- one token bridge with both default and dark values
- preflight/reset ownership remains in host root CSS (not runtime panel bundles)

## What Later Phases May Assume

Explicitly safe assumptions:

- classes that rely on shared token variables resolve when host CSS is loaded
- theme switches update shared token values via `data-theme` on the root element
- runtime panel UI may rely on token-driven color, spacing, radius, and typography
  variables already present in the host stylesheet

Example:

- acceptable runtime panel style usage: consume existing variables like
  `var(--color-bg-primary)` or `var(--radius-sm)` without re-defining baseline tokens

## Intentionally Undecided In Phase 1

The following are intentionally not settled yet:

- machine-enforced allowlist/denylist for runtime CSS imports
- compiler-time CSS bundling policy for runtime panels
- compatibility version negotiation for style contracts
- automated runtime panel style linting against host contracts
- external package extraction strategy for style surfaces

Example:

- not yet guaranteed: importing arbitrary panel-local CSS files from runtime bundles and
  having them automatically merged under policy controls

## Non-Goals

- no backend compiler policy system in this bead
- no runtime diagnostics engine in this bead
- no child-app canary or release hardening in this bead

## Drift Check

Contract drift is guarded by:

- `src/front/__tests__/sharedStyleRuntimeContract.test.js`
