# CSS Contract

This runbook defines the Phase 1 root-package CSS and theme entrypoint contract for
`boring-ui`.

## Public CSS Entrypoint

Host apps consume shared UI styles through one public CSS entrypoint:

- `boring-ui/style.css` -> `dist/style.css`

Phase 1 decision:

- keep `./style.css` as the only public CSS subpath export
- do not publish additional CSS subpath exports yet (keep internals private)

Library consumers should import `boring-ui/style.css` once at host startup.

## Layering Ownership

The root package uses three style layers with explicit ownership:

1. Token and theme bridge layer (`src/front/styles/tokens.css`)
2. Root shared base and primitive layer (`src/front/styles.css`)
3. Feature-local styles inside component/panel modules (private, non-exported)

Phase 1 public contract includes layers 1 and 2 through `boring-ui/style.css`.

## Theme Entrypoint Semantics

`tokens.css` is the canonical theme bridge:

- default token values are defined under `:root`
- dark-mode overrides are defined under `[data-theme="dark"]`
- semantic aliases (legacy bridge tokens) stay available for existing surfaces

Theme switching contract:

- `ThemeProvider` / `useTheme` updates `document.documentElement` with `data-theme`
- shared styles and primitives consume token/semantic variables from `tokens.css`

## Root Stylesheet Import Order

`src/front/styles.css` must keep this import order:

1. font import
2. `./styles/tokens.css`
3. `./styles/scrollbars.css`

This guarantees tokens/theme variables exist before shared base and primitive styles.

## Preflight Ownership

Preflight/reset ownership stays in root package CSS (`src/front/styles.css`), not in
Tailwind preflight.

Contract rules:

- no `@tailwind base`
- no `@import "tailwindcss"` in `src/front/styles.css`

## Tailwind Baseline Assumptions

Tailwind remains explicit and pinned for the current package shape:

- `tailwindcss` pinned in `package.json` dev dependencies
- `@tailwindcss/vite` pinned in `package.json` dev dependencies
- `tailwind.config.js` keeps `darkMode: 'selector'`

## Consumer Expectations

- host imports `boring-ui/style.css` exactly once
- consumers do not import internal files like `src/front/styles/tokens.css`
- runtime and child panels assume host-loaded shared UI CSS and token bridge

## Guardrails

Contract drift is enforced by `src/front/__tests__/cssContract.test.js`, including:

- CSS export surface (`./style.css` only)
- root stylesheet import location and ordering
- token + dark theme bridge availability
- theme application contract (`data-theme` on document root)
- Tailwind/preflight baseline constraints
