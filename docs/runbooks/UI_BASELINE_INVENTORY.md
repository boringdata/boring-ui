# UI Baseline And Inventory

This runbook defines the deterministic baseline workflow for `bd-hlx1.1.2`.

## Goals

- produce a machine-generated AST inventory of host primitive usage
- produce reproducible visual baseline artifacts for core host flows
- keep artifact locations and logging conventions stable across reruns

## Artifacts

### AST Inventory

Command:

```bash
npm run inventory:ui
```

Default output directory:

- `artifacts/ui-inventory/`

Default files:

- `primitive-usage-<timestamp>.json`
- `primitive-usage-<timestamp>.md`

The JSON is canonical machine-readable data. The Markdown summary is for quick review.

### Visual Baselines

Command:

```bash
npm run baseline:ui
```

Default output directory:

- `artifacts/ui-baselines/<timestamp>/`

Per-viewport outputs:

- `<viewport-name>/` screenshots + `report.json` from `scripts/ui-layout-matrix-check.mjs`
- top-level `run.log`
- top-level `summary.json`

## Determinism Contract

- reduced motion is forced to `reduce` by default
- viewport matrix is explicit and logged
- each run writes timestamped artifacts, logs, and pass/fail summary
- script ordering is fixed: one viewport run at a time in matrix order

## Viewport Matrix

Default matrix (`--matrix` override supported):

- `desktop=1600x1000`
- `laptop=1366x900`
- `tablet=1024x768`

Example custom run:

```bash
npm run baseline:ui -- --url http://127.0.0.1:5173/ --matrix desktop=1600x1000,wide=1920x1080
```

## Fixture And Seed Strategy

For comparable reruns:

- run against local dev stack with a stable workspace checkout
- avoid volatile external side effects during baseline capture
- use existing repository files as deterministic file-open targets
- keep auth/session state local and reproducible (same browser profile assumptions per run)

## Logging Strategy

- orchestration-level logs: `artifacts/ui-baselines/<timestamp>/run.log`
- per-viewport detailed checks: `report.json` in each viewport directory
- aggregate status: `summary.json` (pass/fail per viewport with metadata)

## Evidence Convention

When using these artifacts in a bead:

- reference the exact artifact path in bead comments using `EVIDENCE:`
- include the exact command invocation and exit status
