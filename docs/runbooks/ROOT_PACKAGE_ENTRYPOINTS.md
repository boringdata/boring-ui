# Root Package Entrypoints

This runbook locks the Phase 1 root-package import/export contract for `boring-ui`.

## Public Entrypoints

The package root surface remains rooted in this repository shape:

- ESM: `./dist/boring-ui.js`
- CJS: `./dist/boring-ui.cjs`
- CSS: `./dist/style.css`

`package.json` contract:

- `main = ./dist/boring-ui.cjs`
- `module = ./dist/boring-ui.js`
- `exports["."].import = ./dist/boring-ui.js`
- `exports["."].require = ./dist/boring-ui.cjs`
- `exports["./style.css"] = ./dist/style.css`

## Ownership Boundary

Root public API is exported from `src/front/index.js` only.

Allowed categories:

- registry APIs
- layout APIs
- config APIs
- selected hooks and panel/component exports
- root `App`

Not part of root public API:

- host-private data-provider internals
- app pages
- internal utility modules
- chat-internal components

## Smoke Proof

Run build + resolution smoke:

```bash
npm run smoke:entrypoints
```

Artifacts:

- `artifacts/root-entrypoint-smoke/<timestamp>/build.log`
- `artifacts/root-entrypoint-smoke/<timestamp>/summary.json`

The smoke run validates:

- `build:lib --debug` succeeds with verbose logs
- dist entrypoint files exist (ESM/CJS/CSS)
- ESM import and CJS require resolve expected root exports
- package export map matches the intended root-package contract

## Local Consumer Fixture Smoke

Run local fixture-consumer import/build smoke:

```bash
npm run smoke:consumer
```

Artifacts:

- `artifacts/root-consumer-smoke/<timestamp>/build.log`
- `artifacts/root-consumer-smoke/<timestamp>/summary.json`

The fixture smoke validates:

- a local consumer project can install the root package via `file:` dependency
- consumer import of `boring-ui` and `boring-ui/style.css` resolves from the fixture
- fixture `vite build` succeeds and emits JS/CSS output

## Fast Contract Check

For lightweight drift protection in unit tests:

```bash
npm run test:run -- src/front/__tests__/rootEntrypointContract.test.js
```
