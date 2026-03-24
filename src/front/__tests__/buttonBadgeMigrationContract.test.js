import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')

const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

const buttonMigratedFiles = [
  'src/front/components/UserMenu.jsx',
  'src/front/components/ThemeToggle.jsx',
  'src/front/components/SidebarSectionHeader.jsx',
  'src/front/providers/pi/backendAdapter.jsx',
  'src/front/providers/pi/PiSessionToolbar.jsx',
  'src/front/components/FileTree.jsx',
  'src/front/components/GitChangesView.jsx',
  'src/front/panels/TerminalPanel.jsx',
]

describe('Phase 1 Button/Badge Migration Contract', () => {
  it('keeps migrated surfaces off legacy .btn class usage', () => {
    for (const file of buttonMigratedFiles) {
      const source = readRepoFile(file)
      expect(source).not.toContain('btn btn-')
      expect(source).not.toContain('btn-primary')
      expect(source).not.toContain('btn-secondary')
      expect(source).not.toContain('btn-ghost')
      expect(source).not.toContain('btn-icon')
    }
  })

  it('keeps shared Button primitive usage in migrated surfaces', () => {
    for (const file of buttonMigratedFiles) {
      const source = readRepoFile(file)
      expect(source).toContain('Button')
    }
  })

  it('keeps shared Badge primitive usage in status/count badge surfaces', () => {
    for (const file of [
      'src/front/components/FileTree.jsx',
      'src/front/components/GitChangesView.jsx',
      'src/front/panels/TerminalPanel.jsx',
    ]) {
      const source = readRepoFile(file)
      expect(source).toContain('Badge')
      expect(source).toContain('<Badge')
    }
  })

  it('documents wrapper exceptions for the migration slice', () => {
    const runbook = readRepoFile('docs/runbooks/PHASE1_BUTTON_BADGE_MIGRATION.md')
    expect(runbook).toContain('Wrapper Exceptions')
    expect(runbook).toContain('className-bridge pattern')
  })
})
