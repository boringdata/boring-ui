import { describe, it, expect } from 'vitest'
import { consumeInitialUpdateGuard } from '../../components/editorUpdateGuard'

describe('consumeInitialUpdateGuard', () => {
  it('consumes first update and clears guard', () => {
    const guard = { current: true }
    expect(consumeInitialUpdateGuard(guard)).toBe(true)
    expect(guard.current).toBe(false)
  })

  it('does not consume subsequent updates', () => {
    const guard = { current: false }
    expect(consumeInitialUpdateGuard(guard)).toBe(false)
    expect(guard.current).toBe(false)
  })
})
