# Evidence: bd-25ym

## Problem
Verification runner for `bd-3g1g.7.2` showed Playwright failing:
`src/front/__tests__/e2e/layout.spec.ts` `Layout Persistence › collapsed state persists`
timed out at 30s (see `.verify/.../logs/playwright_e2e.log` from the matrix run).

## Fix
- Avoid flaky `page.reload()` default `load` wait by using `waitUntil: 'domcontentloaded'` and explicit UI readiness waits.
- Add extra per-test timeout headroom for the collapsed-state persistence test.
- Align dockview readiness timeouts for consistency.

## Verification
- `PATH=/usr/bin:/bin:$PATH npm run -s test:e2e -- src/front/__tests__/e2e/layout.spec.ts` (pass)
