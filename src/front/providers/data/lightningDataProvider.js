/**
 * LightningFS + isomorphic-git composed DataProvider.
 *
 * Creates an isolated LightningFS instance by name so standalone apps can test
 * multiple filesystem setups without external host registration.
 */
import LightningFS from '@isomorphic-git/lightning-fs'
import { createLightningFsProvider } from './lightningFsProvider'
import { createIsomorphicGitProvider } from './isomorphicGitProvider'

const normalizeFsName = (name) => {
  const value = String(name || '').trim()
  return value || 'boring-fs'
}

/**
 * Create a composed DataProvider backed by LightningFS + isomorphic-git.
 *
 * @param {{ fsName?: string, dir?: string }} [opts]
 * @returns {import('./types').DataProvider}
 */
export const createLightningDataProvider = (opts = {}) => {
  const fsName = normalizeFsName(opts.fsName)
  const dir = String(opts.dir || '/')
  const fs = new LightningFS(fsName)
  const pfs = fs.promises

  return {
    files: createLightningFsProvider(pfs),
    git: createIsomorphicGitProvider({ fs, pfs, dir }),
  }
}

