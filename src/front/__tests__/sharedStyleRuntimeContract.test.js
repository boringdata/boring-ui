import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')

const readRepoFile = (relativePath) => (
  fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')
)

describe('Shared Style Runtime Contract Docs', () => {
  it('defines Phase 1 runtime-facing guarantees and defaults', () => {
    const runbook = readRepoFile('docs/runbooks/SHARED_STYLE_RUNTIME_CONTRACT.md')

    expect(runbook).toContain('## Phase 1 Guarantees')
    expect(runbook).toContain('## Runtime Root Defaults')
    expect(runbook).toContain('host app imports `boring-ui/style.css` exactly once at startup')
    expect(runbook).toContain('theme state is expressed through document-root `data-theme` (`light` or `dark`)')
  })

  it('documents explicit assumption examples and intentional undecided areas', () => {
    const runbook = readRepoFile('docs/runbooks/SHARED_STYLE_RUNTIME_CONTRACT.md')

    expect(runbook).toContain('## What Later Phases May Assume')
    expect(runbook).toContain('## Intentionally Undecided In Phase 1')
    expect(runbook).toContain('acceptable runtime panel style usage')
    expect(runbook).toContain('not yet guaranteed: importing arbitrary panel-local CSS files')
  })

  it('keeps the runbook discoverable from top-level docs', () => {
    const runbookIndex = readRepoFile('docs/runbooks/README.md')
    const readme = readRepoFile('README.md')

    expect(runbookIndex).toContain('Shared Style Runtime Contract')
    expect(runbookIndex).toContain('./SHARED_STYLE_RUNTIME_CONTRACT.md')
    expect(readme).toContain('Shared Style Runtime Contract')
  })
})
