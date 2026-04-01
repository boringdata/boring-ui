import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')
const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

describe('Root Package Entrypoint Contract', () => {
  it('keeps package export map aligned to dist root entrypoints', () => {
    const packageJson = JSON.parse(readRepoFile('package.json'))

    expect(packageJson.main).toBe('./dist/boring-ui.cjs')
    expect(packageJson.module).toBe('./dist/boring-ui.js')
    expect(packageJson.exports?.['.']?.import).toBe('./dist/boring-ui.js')
    expect(packageJson.exports?.['.']?.require).toBe('./dist/boring-ui.cjs')
    expect(packageJson.exports?.['./style.css']).toBe('./dist/style.css')
  })

  it('keeps source public API anchored in root entrypoint modules only', () => {
    const indexSource = readRepoFile('src/front/index.js')

    expect(indexSource).toContain("} from './registry'")
    expect(indexSource).toContain("} from './layout'")
    expect(indexSource).toContain("} from './shared/config'")
    expect(indexSource).toContain("export { ThemeProvider, useTheme } from './shared/hooks/useTheme'")
    expect(indexSource).toContain("export { cn } from './lib/utils'")
    expect(indexSource).toContain("export { Button, buttonVariants } from './shared/components/ui/button'")
    expect(indexSource).toContain("export { default as App } from './App'")

    // Host-private internals should not leak into the package root public API.
    expect(indexSource).not.toContain("from './providers/data'")
    expect(indexSource).not.toContain("from './utils/'")
    expect(indexSource).not.toContain("from './pages/'")
    expect(indexSource).not.toContain("from './components/chat/'")
  })

  it('documents root-package consumer import paths for Phase 1', () => {
    const readme = readRepoFile('README.md')
    expect(readme).toContain("import { addPiAgentTools } from 'boring-ui'")
    expect(readme).toContain('`boring-ui/style.css`')
  })

  it('keeps smoke script hooks for root entrypoints and local fixture consumer', () => {
    const packageJson = JSON.parse(readRepoFile('package.json'))
    expect(packageJson.scripts?.['smoke:entrypoints']).toBe('node scripts/smoke-root-entrypoints.mjs')
    expect(packageJson.scripts?.['smoke:consumer']).toBe('node scripts/smoke-root-consumer-fixture.mjs')
  })
})
