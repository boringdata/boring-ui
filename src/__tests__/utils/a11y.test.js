import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  getContrastRatio,
  createFocusTrap,
  announceToScreenReader,
  isVisible,
  getFocusableElements,
  isActivationKey,
  KeyCode,
} from '../../utils/a11y'

describe('a11y utilities', () => {
  describe('getContrastRatio', () => {
    it('calculates contrast ratio correctly', () => {
      const result = getContrastRatio('#ffffff', '#000000')
      expect(result.ratio).toBeGreaterThan(20)
      expect(result.isAACompliant).toBe(true)
      expect(result.isAAACompliant).toBe(true)
    })

    it('identifies AA compliant contrast', () => {
      // White on dark gray (should be AA compliant)
      const result = getContrastRatio('#ffffff', '#666666')
      expect(result.isAACompliant).toBe(true)
    })

    it('identifies non-AA compliant contrast', () => {
      // Light gray on white (insufficient contrast)
      const result = getContrastRatio('#f0f0f0', '#ffffff')
      expect(result.isAACompliant).toBe(false)
    })

    it('identifies AAA compliant contrast', () => {
      const result = getContrastRatio('#ffffff', '#000000')
      expect(result.isAAACompliant).toBe(true)
    })

    it('handles reversed color order', () => {
      const ratio1 = getContrastRatio('#ffffff', '#000000')
      const ratio2 = getContrastRatio('#000000', '#ffffff')
      expect(ratio1.ratio).toBe(ratio2.ratio)
    })
  })

  describe('createFocusTrap', () => {
    let container

    beforeEach(() => {
      container = document.createElement('div')
      container.innerHTML = `
        <button class="first">First</button>
        <input type="text" />
        <button class="last">Last</button>
      `
      document.body.appendChild(container)
    })

    afterEach(() => {
      document.body.removeChild(container)
    })

    it('creates focus trap object with methods', () => {
      const trap = createFocusTrap(container)
      expect(trap).toHaveProperty('trap')
      expect(trap).toHaveProperty('untrap')
      expect(typeof trap.trap).toBe('function')
      expect(typeof trap.untrap).toBe('function')
    })

    it('returns empty trap for null container', () => {
      const trap = createFocusTrap(null)
      expect(() => trap.trap()).not.toThrow()
      expect(() => trap.untrap()).not.toThrow()
    })

    it('focuses first element when trap is activated', () => {
      const trap = createFocusTrap(container)
      trap.trap()
      expect(document.activeElement).toBe(container.querySelector('.first'))
    })
  })

  describe('announceToScreenReader', () => {
    beforeEach(() => {
      // Clear any existing announcements
      document.querySelectorAll('[role="status"]').forEach(el => el.remove())
    })

    afterEach(() => {
      document.querySelectorAll('[role="status"]').forEach(el => el.remove())
    })

    it('creates and removes announcement element', async () => {
      announceToScreenReader('Test announcement')
      const announcement = document.querySelector('[role="status"]')
      expect(announcement).toBeInTheDocument()

      await new Promise(resolve => setTimeout(resolve, 1100))
      expect(document.querySelector('[role="status"]')).not.toBeInTheDocument()
    })

    it('sets aria-live to polite by default', () => {
      announceToScreenReader('Test')
      const announcement = document.querySelector('[role="status"]')
      expect(announcement).toHaveAttribute('aria-live', 'polite')
    })

    it('respects priority parameter', () => {
      announceToScreenReader('Test', 'assertive')
      const announcement = document.querySelector('[role="status"]')
      expect(announcement).toHaveAttribute('aria-live', 'assertive')
    })

    it('sets aria-atomic for atomic reading', () => {
      announceToScreenReader('Test')
      const announcement = document.querySelector('[role="status"]')
      expect(announcement).toHaveAttribute('aria-atomic', 'true')
    })

    it('contains the message text', () => {
      announceToScreenReader('My test message')
      const announcement = document.querySelector('[role="status"]')
      expect(announcement).toHaveTextContent('My test message')
    })
  })

  describe('isVisible', () => {
    it('returns true for visible elements', () => {
      const div = document.createElement('div')
      document.body.appendChild(div)
      expect(isVisible(div)).toBe(true)
      document.body.removeChild(div)
    })

    it('returns false for null element', () => {
      expect(isVisible(null)).toBe(false)
    })

    it('returns false for hidden elements', () => {
      const div = document.createElement('div')
      div.style.display = 'none'
      document.body.appendChild(div)
      expect(isVisible(div)).toBe(false)
      document.body.removeChild(div)
    })
  })

  describe('getFocusableElements', () => {
    let container

    beforeEach(() => {
      container = document.createElement('div')
      container.innerHTML = `
        <button>Button</button>
        <a href="#">Link</a>
        <input type="text" />
        <select><option>Option</option></select>
        <textarea></textarea>
        <div tabindex="0">Div with tabindex</div>
        <span>Non-focusable span</span>
      `
      document.body.appendChild(container)
    })

    afterEach(() => {
      document.body.removeChild(container)
    })

    it('returns array of focusable elements', () => {
      const focusable = getFocusableElements(container)
      expect(Array.isArray(focusable)).toBe(true)
      expect(focusable.length).toBeGreaterThan(0)
    })

    it('includes button elements', () => {
      const focusable = getFocusableElements(container)
      const hasButton = focusable.some(el => el.tagName === 'BUTTON')
      expect(hasButton).toBe(true)
    })

    it('includes input elements', () => {
      const focusable = getFocusableElements(container)
      const hasInput = focusable.some(el => el.tagName === 'INPUT')
      expect(hasInput).toBe(true)
    })

    it('excludes non-focusable elements', () => {
      const focusable = getFocusableElements(container)
      const hasSpan = focusable.some(el => el.tagName === 'SPAN' && !el.hasAttribute('tabindex'))
      expect(hasSpan).toBe(false)
    })
  })

  describe('isActivationKey', () => {
    it('returns true for Enter key', () => {
      const event = new KeyboardEvent('keydown', { key: KeyCode.ENTER })
      expect(isActivationKey(event)).toBe(true)
    })

    it('returns true for Space key', () => {
      const event = new KeyboardEvent('keydown', { key: KeyCode.SPACE })
      expect(isActivationKey(event)).toBe(true)
    })

    it('returns false for other keys', () => {
      const event = new KeyboardEvent('keydown', { key: 'ArrowUp' })
      expect(isActivationKey(event)).toBe(false)
    })

    it('returns false for Tab key', () => {
      const event = new KeyboardEvent('keydown', { key: KeyCode.TAB })
      expect(isActivationKey(event)).toBe(false)
    })
  })

  describe('KeyCode constants', () => {
    it('has all required key codes', () => {
      expect(KeyCode.ENTER).toBe('Enter')
      expect(KeyCode.ESCAPE).toBe('Escape')
      expect(KeyCode.SPACE).toBe(' ')
      expect(KeyCode.TAB).toBe('Tab')
      expect(KeyCode.ARROW_UP).toBe('ArrowUp')
      expect(KeyCode.ARROW_DOWN).toBe('ArrowDown')
      expect(KeyCode.ARROW_LEFT).toBe('ArrowLeft')
      expect(KeyCode.ARROW_RIGHT).toBe('ArrowRight')
      expect(KeyCode.HOME).toBe('Home')
      expect(KeyCode.END).toBe('End')
    })
  })
})
