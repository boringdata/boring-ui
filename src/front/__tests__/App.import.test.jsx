import { describe, expect, it } from 'vitest'

describe('App module', () => {
  it('imports without module-level reference errors', async () => {
    await expect(import('../App')).resolves.toHaveProperty('default')
  }, 15000)
})
