import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')
const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

describe('Phase 1 guardrails and CSS retirement contract', () => {
  it('keeps the phase1 guardrail lint script wired into npm lint', () => {
    const pkg = JSON.parse(readRepoFile('package.json'))
    expect(pkg.scripts['lint:phase1']).toBe('node scripts/check-phase1-guardrails.mjs')
    expect(pkg.scripts.lint).toContain('npm run lint:phase1')
  })

  it('keeps guardrail scan coverage for retired tokens/selectors and page-local wrappers', () => {
    const source = readRepoFile('scripts/check-phase1-guardrails.mjs')
    expect(source).toContain('retiredClassTokens')
    expect(source).toContain('primitiveWrapperPattern')
    expect(source).toContain('.modal-overlay')
    expect(source).toContain("path.join(frontRoot, 'pages')")
  })

  it('keeps retired primitive selectors out of shared host styles', () => {
    const styles = readRepoFile('src/front/styles.css')
    expect(styles).not.toContain('.btn {')
    expect(styles).not.toContain('.btn-primary {')
    expect(styles).not.toContain('.btn-secondary {')
    expect(styles).not.toContain('.btn-ghost {')
    expect(styles).not.toContain('.btn-icon {')
    expect(styles).not.toContain('.modal-overlay {')
  })

  it('documents phased retirement and intentional retained CSS boundaries', () => {
    const runbook = readRepoFile('docs/runbooks/PHASE1_GUARDRAILS_CSS_RETIREMENT.md')
    expect(runbook).toContain('Guardrails Added')
    expect(runbook).toContain('Phased CSS Retirement In This Slice')
    expect(runbook).toContain('Intentionally Retained CSS')
    expect(runbook).toContain('.settings-btn')
    expect(runbook).toContain('DockView')
  })
})
