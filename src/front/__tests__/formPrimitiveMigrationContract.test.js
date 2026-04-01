import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')
const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

describe('Phase 1 Form Primitive Migration Contract', () => {
  it('keeps shared Input primitives wired in core settings/auth/modal surfaces', () => {
    for (const file of [
      'src/front/pages/CreateWorkspaceModal.jsx',
      'src/front/pages/UserSettingsPage.jsx',
      'src/front/pages/WorkspaceSettingsPage.jsx',
      'src/front/pages/AuthPage.jsx',
    ]) {
      const source = readRepoFile(file)
      expect(source).toContain('Input')
      expect(source).toContain('<Input')
    }
  })

  it('keeps shared Label primitives wired where explicit labels are rendered', () => {
    for (const file of [
      'src/front/pages/CreateWorkspaceModal.jsx',
      'src/front/pages/AuthPage.jsx',
      'src/front/pages/PageShell.jsx',
    ]) {
      const source = readRepoFile(file)
      expect(source).toContain('Label')
      expect(source).toContain('<Label')
    }
  })

  it('keeps shared Textarea primitives wired in approval + PI backend composer surfaces', () => {
    for (const file of [
      'src/front/shared/providers/pi/backendAdapter.jsx',
      'src/front/shared/components/ApprovalPanel.jsx',
    ]) {
      const source = readRepoFile(file)
      expect(source).toContain('Textarea')
      expect(source).toContain('<Textarea')
    }
  })

  it('keeps shared Select primitives wired for workspace sync interval settings', () => {
    const source = readRepoFile('src/front/pages/WorkspaceSettingsPage.jsx')
    expect(source).toContain("from '../shared/components/ui/select'")
    expect(source).toContain('<Select ')
    expect(source).toContain('<SelectTrigger')
    expect(source).toContain('<SelectContent')
    expect(source).toContain('<SelectItem')
  })

  it('documents intentional native/custom form-control exceptions', () => {
    const runbook = readRepoFile('docs/runbooks/PHASE1_FORM_PRIMITIVE_MIGRATION.md')
    expect(runbook).toContain('Intentionally Native/Custom Controls')
    expect(runbook).toContain('TerminalPanel')
    expect(runbook).toContain('FileTree')
  })
})
