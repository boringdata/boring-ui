import { describe, expect, it } from 'vitest'
import { classifyLightningFsBootstrap, normalizeRepoUrl } from '../../hooks/useLightningFsGitBootstrap'

describe('normalizeRepoUrl', () => {
  it('normalizes ssh and https GitHub urls to the same canonical form', () => {
    expect(normalizeRepoUrl('git@github.com:BoringData/Boring-UI.git')).toBe('https://github.com/boringdata/boring-ui')
    expect(normalizeRepoUrl('https://github.com/BoringData/Boring-UI.git')).toBe('https://github.com/boringdata/boring-ui')
  })
})

describe('classifyLightningFsBootstrap', () => {
  it('requests clone for an empty non-git workspace', () => {
    expect(classifyLightningFsBootstrap({
      enabled: true,
      installationConnected: true,
      repoUrl: 'https://github.com/boringdata/boring-ui-repo.git',
      gitStatus: { is_repo: false },
      remotes: [],
      rootEntries: [],
    })).toMatchObject({
      state: 'needs-clone',
      needsBootstrap: true,
      syncReady: false,
    })
  })

  it('marks workspace ready when origin already matches the selected repo', () => {
    expect(classifyLightningFsBootstrap({
      enabled: true,
      installationConnected: true,
      repoUrl: 'https://github.com/boringdata/boring-ui-repo.git',
      gitStatus: { is_repo: true },
      remotes: [{ remote: 'origin', url: 'git@github.com:boringdata/boring-ui-repo.git' }],
      rootEntries: [{ name: '.git' }, { name: 'README.md' }],
    })).toMatchObject({
      state: 'ready',
      syncReady: true,
      needsBootstrap: false,
    })
  })

  it('blocks auto-binding when the browser workspace already has plain files', () => {
    expect(classifyLightningFsBootstrap({
      enabled: true,
      installationConnected: true,
      repoUrl: 'https://github.com/boringdata/boring-ui-repo.git',
      gitStatus: { is_repo: false },
      remotes: [],
      rootEntries: [{ name: 'notes.md' }],
    })).toMatchObject({
      state: 'blocked-local-files',
      syncReady: false,
      needsBootstrap: false,
    })
  })

  it('blocks auto-binding when another origin is already configured', () => {
    expect(classifyLightningFsBootstrap({
      enabled: true,
      installationConnected: true,
      repoUrl: 'https://github.com/boringdata/boring-ui-repo.git',
      gitStatus: { is_repo: true },
      remotes: [{ remote: 'origin', url: 'https://github.com/boringdata/other-repo.git' }],
      rootEntries: [{ name: '.git' }, { name: 'README.md' }],
    })).toMatchObject({
      state: 'blocked-remote-mismatch',
      syncReady: false,
      needsBootstrap: false,
    })
  })
})
