# UI Platform Phase 1 Regression Gates

## Scope

This runbook is the quality contract for `bd-hlx1` Phase 1 host migration work.
It applies to the active Phase 1 beads that migrate the current host app onto
the shadcn-native primitive path while preserving the current repo/package shape.

It does not define later rollout/soak policy for Track B runtime work.

## Minimum Coverage Matrix

Every Phase 1 migration bead must declare which of these layers it touched and
must either provide the matching proof or explicitly justify why the layer is
not applicable.

| Layer | Minimum expectation | Typical trigger |
| --- | --- | --- |
| Vitest unit/interaction | Focused tests for the primitive, helper, or host wrapper that changed | Any shared component or utility change |
| Frontend integration | Layout/state wiring proof for affected host flows | Changes that cross panels, providers, or persistence |
| Accessibility assertions | Keyboard, focus, disabled, ARIA, and error-state checks | Any interactive primitive or form/control work |
| Playwright e2e | Real browser proof for visible host flows and failure artifacts | Overlay, navigation, focus, async save, or multi-surface regressions |

## Logging Contract

Phase 1 tests must leave logs that explain what was exercised without requiring
reverse-engineering from stack traces alone.

### Vitest and integration expectations

- Log the scenario or fixture being exercised when the setup is non-trivial.
- Log key state transitions that matter for debugging, such as open/close,
  loading/ready/error, focus handoff, or validation status changes.
- On failure, include the component, route, panel, or fixture name in the output.
- Prefer explicit assertion context over opaque snapshots with no narrative.

### Playwright expectations

- Preserve a deterministic artifact directory for every run.
- On failure, keep screenshots, video, trace data, and the browser-facing log.
- Log enough run metadata to reproduce the environment: args, worker count,
  server reuse mode, and artifact location.
- Capture browser console and network failures when adding new end-to-end flows.

## Artifact Contract

The canonical Playwright artifact surface for Phase 1 is:

- `test-results/playwright-artifacts/` for run-scoped Playwright output
- `test-results/results.json` for machine-readable summary output
- `test-results/junit.xml` for CI-oriented summary output
- `playwright-report/` for HTML review output

If a bead adds custom baselines or supporting evidence, it must also link those
artifacts from the bead evidence record so reviewers can diagnose regressions.

## Waiver Process

Intentional diffs are allowed only when they are explicit and reviewable.

Every waiver must record:

- the bead id and affected flow
- why the old behavior changed
- what user-visible difference is expected
- the artifact paths that prove the new behavior
- the approval reference or reviewer signoff

Absence of a waiver means the change is treated as an unintended regression.

## Evidence Checklist

Every Phase 1 bead should leave a proof note that includes:

- commands run
- focused test files or suites
- artifact paths for any Playwright or screenshot output
- any waiver ids, or `none`
- residual risks that remain intentionally open

## Downstream Rule

Later `bd-hlx1.2.*` migration beads should reference this runbook directly
instead of re-defining coverage, logging, artifact, or waiver policy ad hoc.
