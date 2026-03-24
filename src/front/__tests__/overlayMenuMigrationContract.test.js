import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')
const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

describe('Phase 1 Overlay/Menu Migration Contract', () => {
  it('keeps CreateWorkspaceModal wired to shared dialog primitives', () => {
    const source = readRepoFile('src/front/pages/CreateWorkspaceModal.jsx')
    expect(source).toContain("from '../components/ui/dialog'")
    expect(source).toContain('<Dialog')
    expect(source).toContain('<DialogContent')
    expect(source).toContain('<DialogTitle')
    expect(source).toContain('<DialogFooter')
  })

  it('keeps EditorPanel mode selector wired to shared dropdown primitives', () => {
    const source = readRepoFile('src/front/panels/EditorPanel.jsx')
    expect(source).toContain("from '../components/ui/dropdown-menu'")
    expect(source).toContain('<DropdownMenu')
    expect(source).toContain('<DropdownMenuTrigger')
    expect(source).toContain('<DropdownMenuContent')
    expect(source).toContain('<DropdownMenuItem')
  })

  it('documents intentional custom overlay behavior that remains', () => {
    const runbook = readRepoFile('docs/runbooks/PHASE1_OVERLAY_MENU_MIGRATION.md')
    expect(runbook).toContain('Intentionally Custom Overlay/Menu Behavior')
    expect(runbook).toContain('SyncStatusFooter')
    expect(runbook).toContain('UserMenu')
    expect(runbook).toContain('FileTree')
  })
})
