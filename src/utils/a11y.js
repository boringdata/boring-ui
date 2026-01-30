/**
 * Accessibility (a11y) Utilities
 * Collection of helper functions for WCAG 2.1 AAA compliance
 * Includes contrast checking, ARIA utilities, and keyboard navigation helpers
 */

/**
 * Get contrast ratio between two colors
 * Formula per WCAG 2.0
 * @param {string} foreground - CSS color value (hex, rgb, named)
 * @param {string} background - CSS color value (hex, rgb, named)
 * @returns {object} {ratio: number, isAACompliant: boolean, isAAACompliant: boolean}
 */
export function getContrastRatio(foreground, background) {
  const getLuminance = (hex) => {
    const rgb = parseInt(hex.slice(1), 16)
    const r = (rgb >> 16) & 0xff
    const g = (rgb >> 8) & 0xff
    const b = (rgb >> 0) & 0xff

    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance <= 0.03928
      ? luminance / 12.92
      : Math.pow((luminance + 0.055) / 1.055, 2.4)
  }

  const l1 = getLuminance(foreground)
  const l2 = getLuminance(background)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  const ratio = (lighter + 0.05) / (darker + 0.05)

  return {
    ratio: Math.round(ratio * 100) / 100,
    isAACompliant: ratio >= 4.5,
    isAAACompliant: ratio >= 7,
  }
}

/**
 * Generate accessible skip link HTML
 * @returns {string} HTML for skip to main link
 */
export function createSkipLink() {
  return `
    <a href="#main-content" class="sr-only">
      Skip to main content
    </a>
  `
}

/**
 * Create a focus trap instance for modals and dialogs
 * @param {HTMLElement} container - Container element
 * @returns {object} {trap: function, untrap: function}
 */
export function createFocusTrap(container) {
  if (!container) return { trap: () => {}, untrap: () => {} }

  const focusableElements = container.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )
  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]

  const handleKeyDown = (e) => {
    if (e.key !== 'Tab') return

    if (e.shiftKey) {
      // Shift+Tab
      if (document.activeElement === firstElement) {
        lastElement?.focus()
        e.preventDefault()
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        firstElement?.focus()
        e.preventDefault()
      }
    }
  }

  return {
    trap: () => {
      firstElement?.focus()
      container.addEventListener('keydown', handleKeyDown)
    },
    untrap: () => {
      container.removeEventListener('keydown', handleKeyDown)
    },
  }
}

/**
 * Announce message to screen readers
 * @param {string} message - Message to announce
 * @param {string} priority - 'polite' or 'assertive'
 */
export function announceToScreenReader(message, priority = 'polite') {
  const announcement = document.createElement('div')
  announcement.setAttribute('role', 'status')
  announcement.setAttribute('aria-live', priority)
  announcement.setAttribute('aria-atomic', 'true')
  announcement.className = 'sr-only'
  announcement.textContent = message

  document.body.appendChild(announcement)

  // Remove after announcement is read
  setTimeout(() => announcement.remove(), 1000)
}

/**
 * Generate accessible label for form field
 * @param {string} id - Input field ID
 * @param {string} label - Label text
 * @param {boolean} required - Is field required
 * @returns {string} HTML for label
 */
export function createLabel(id, label, required = false) {
  return `
    <label for="${id}" class="block text-sm font-medium">
      ${label}
      ${required ? '<span class="text-error ml-1">*</span>' : ''}
    </label>
  `
}

/**
 * Generate error message with proper ARIA linkage
 * @param {string} id - Input field ID
 * @param {string} error - Error message
 * @returns {string} HTML for error message
 */
export function createErrorMessage(id, error) {
  return `
    <p id="${id}-error" class="mt-1 text-sm text-error" role="alert">
      ${error}
    </p>
  `
}

/**
 * Check if element is visible (for keyboard navigation)
 * @param {HTMLElement} element - Element to check
 * @returns {boolean}
 */
export function isVisible(element) {
  if (!element) return false
  return !!(element.offsetParent || element.offsetWidth || element.offsetHeight)
}

/**
 * Get all focusable elements in container
 * @param {HTMLElement} container - Container element
 * @returns {Array} Array of focusable elements
 */
export function getFocusableElements(container = document) {
  return Array.from(
    container.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
  ).filter(isVisible)
}

/**
 * Create accessible icon button (for icon-only buttons)
 * @param {string} ariaLabel - Accessibility label
 * @param {string} icon - Icon SVG or HTML
 * @returns {string} HTML for accessible icon button
 */
export function createIconButton(ariaLabel, icon) {
  return `
    <button aria-label="${ariaLabel}" class="icon-button">
      ${icon}
    </button>
  `
}

/**
 * Keyboard event utilities
 */
export const KeyCode = {
  ENTER: 'Enter',
  ESCAPE: 'Escape',
  SPACE: ' ',
  TAB: 'Tab',
  ARROW_UP: 'ArrowUp',
  ARROW_DOWN: 'ArrowDown',
  ARROW_LEFT: 'ArrowLeft',
  ARROW_RIGHT: 'ArrowRight',
  HOME: 'Home',
  END: 'End',
}

/**
 * Check if keyboard event is for activation (Enter or Space)
 * @param {KeyboardEvent} e
 * @returns {boolean}
 */
export function isActivationKey(e) {
  return e.key === KeyCode.ENTER || e.key === KeyCode.SPACE
}
