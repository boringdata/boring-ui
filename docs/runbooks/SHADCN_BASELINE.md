# Shadcn Baseline

Phase 1 uses a deterministic, npm-only shadcn baseline in the current root-package
layout.

## Pinned Toolchain

Pinned versions for the migration baseline:

- `tailwindcss`: `4.1.18`
- `@tailwindcss/vite`: `4.1.18`
- `shadcn` CLI: `4.1.0`
- `tailwind-merge`: `3.4.0`
- `tw-animate-css`: `1.4.0`
- `lucide-react`: `0.562.0`

## Checked-In Bootstrap Config

`components.json` is the canonical shadcn bootstrap config for this repo shape:

- Tailwind config: `tailwind.config.js`
- Tailwind CSS entry: `src/front/styles.css`
- alias root: `@/` -> `src/front/*`
- style preset: `new-york`
- icon library: `lucide`
- `tsx = false` and `rsc = false`

## Deterministic NPM Invocation Pattern

Do not use floating version tags. Keep this migration track npm-only with explicit
versioned commands.

Initialize (when bootstrap needs to be refreshed):

```bash
npx --yes shadcn@4.1.0 init
```

Add primitives (non-interactive, config-driven):

```bash
npx --yes shadcn@4.1.0 add <component>
```

Phase 1 initial primitive batch used for this repo:

```bash
npx --yes shadcn@4.1.0 add button badge dialog dropdown-menu input textarea select label switch tooltip avatar tabs separator --yes
```

## Thin Wrapper Policy

Default:

- use generated primitives directly
- keep wrappers thin and only introduce them when repeated boring-ui behavior justifies
  a shared abstraction

For each wrapper introduced later, record:

- why a wrapper is needed beyond primitive composition
- which generated primitive it wraps
- any token/behavior contract that must stay stable

## Drift Gate

Run the baseline checker:

```bash
npm run lint:shadcn
```

This gate validates:

- pinned versions in `package.json`
- key fields in `components.json`
- pinned npm command patterns in this runbook
- required sections in `docs/runbooks/UPSTREAM_SHADCN.md`
