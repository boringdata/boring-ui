/**
 * LightningFS instance shared by lightningFsProvider and isomorphicGitProvider.
 *
 * @module providers/data/lightningFs
 */
import LightningFS from '@isomorphic-git/lightning-fs'

export const fs = new LightningFS('boring-fs')
export const pfs = fs.promises
