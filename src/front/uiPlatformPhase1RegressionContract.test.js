import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { describe, expect, it } from 'vitest'

const projectRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..')
const runbookPath = path.join(projectRoot, 'docs/runbooks/UI_PLATFORM_PHASE1_REGRESSION_GATES.md')
const runbook = fs.readFileSync(runbookPath, 'utf8')
const playwrightWrapper = fs.readFileSync(path.join(projectRoot, 'scripts/run-playwright-e2e.sh'), 'utf8')

describe('ui-platform phase 1 regression contract', () => {
  it('documents the required regression-gate sections', () => {
    const requiredSections = [
      '## Minimum Coverage Matrix',
      '## Logging Contract',
      '## Artifact Contract',
      '## Waiver Process',
      '## Evidence Checklist',
      '## Downstream Rule',
    ]

    for (const heading of requiredSections) {
      expect(runbook).toContain(heading)
    }
  })

  it('keeps Playwright artifact capture strict enough for Phase 1 migration work', async () => {
    const configUrl = pathToFileURL(path.join(projectRoot, 'playwright.config.js')).href
    const { default: playwrightConfig } = await import(configUrl)

    expect(playwrightConfig.outputDir).toBe('test-results/playwright-artifacts')
    expect(playwrightConfig.expect?.toHaveScreenshot?.animations).toBe('disabled')
    expect(playwrightConfig.expect?.toHaveScreenshot?.caret).toBe('hide')
    expect(playwrightConfig.expect?.toHaveScreenshot?.scale).toBe('css')
    expect(playwrightConfig.use?.screenshot).toBe('only-on-failure')
    expect(playwrightConfig.use?.trace).toBe('retain-on-failure')
    expect(playwrightConfig.use?.video).toBe('retain-on-failure')
    expect(playwrightConfig.workers).toBe(1)
  })

  it('requires the Playwright wrapper to log run metadata into the artifact directory', () => {
    expect(playwrightWrapper).toContain('PW_E2E_ARTIFACT_DIR')
    expect(playwrightWrapper).toContain('run.log')
    expect(playwrightWrapper).toContain('started_at=')
    expect(playwrightWrapper).toContain('finished_at=')
    expect(playwrightWrapper).toContain('git_head=')
    expect(playwrightWrapper).toContain('pwd=')
  })

  it('documents regression-specific browser and visual artifact expectations', () => {
    expect(runbook).toContain('browser-events.ndjson')
    expect(runbook).toContain('step-log.json')
    expect(runbook).toContain('phase1-regression-logging.spec.ts-snapshots')
  })
})
