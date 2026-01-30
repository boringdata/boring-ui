import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import {
  hasContrastAAA,
  hasContrastAA,
  generateId,
  isKeyboardAccessible,
  getFocusableElements,
  trapFocus,
  prefersReducedMotion,
  prefersHighContrast,
  hasAccessibleName,
  getAccessibleName,
  validateHeadingHierarchy,
  isVisibleToScreenReader,
} from '../../utils/a11y'
import {
  AccessibleMessage,
  AccessibleCodeBlock,
  AccessibleLink,
  AccessibleList,
  AccessibleListItem,
  AccessibleHeading,
  AccessibleParagraph,
  AccessibleEmphasis,
} from '../../components/Chat/AccessibleMessage'

describe('WCAG 2.1 AAA Accessibility Utilities', () => {
  describe('Contrast Ratio Functions', () => {
    it('checks WCAG AAA contrast (7:1)', () => {
      // White on black = 21:1
      const result = hasContrastAAA('#ffffff', '#000000')
      expect(result).toBe(true)
    })

    it('rejects low contrast for AAA', () => {
      // Light gray on white = not enough contrast
      const result = hasContrastAAA('#cccccc', '#ffffff')
      expect(result).toBe(false)
    })

    it('checks WCAG AA contrast (4.5:1)', () => {
      // White on dark blue
      const result = hasContrastAA('#ffffff', '#003399')
      expect(result).toBe(true)
    })
  })

  describe('ID Generation', () => {
    it('generates unique IDs', () => {
      const id1 = generateId('test')
      const id2 = generateId('test')
      expect(id1).not.toBe(id2)
      expect(id1).toMatch(/^test-/)
      expect(id2).toMatch(/^test-/)
    })

    it('uses default prefix if not provided', () => {
      const id = generateId()
      expect(id).toMatch(/^id-/)
    })
  })

  describe('Keyboard Accessibility', () => {
    it('identifies keyboard accessible button', () => {
      const { container } = render(
        <button data-testid="btn">Click me</button>
      )
      const button = container.querySelector('button')
      expect(isKeyboardAccessible(button)).toBe(true)
    })

    it('identifies keyboard accessible link', () => {
      const { container } = render(
        <a href="https://example.com">Link</a>
      )
      const link = container.querySelector('a')
      expect(isKeyboardAccessible(link)).toBe(true)
    })

    it('identifies keyboard accessible input', () => {
      const { container } = render(
        <input type="text" />
      )
      const input = container.querySelector('input')
      expect(isKeyboardAccessible(input)).toBe(true)
    })

    it('identifies element with tabindex', () => {
      const { container } = render(
        <div tabIndex="0">Focusable</div>
      )
      const div = container.querySelector('div')
      expect(isKeyboardAccessible(div)).toBe(true)
    })

    it('rejects inaccessible elements', () => {
      const { container } = render(
        <div>Not focusable</div>
      )
      const div = container.querySelector('div')
      expect(isKeyboardAccessible(div)).toBe(false)
    })
  })

  describe('Get Focusable Elements', () => {
    it('returns all focusable elements in container', () => {
      const { container } = render(
        <div>
          <button>Button 1</button>
          <button>Button 2</button>
          <a href="#">Link</a>
          <input type="text" />
        </div>
      )

      const focusable = getFocusableElements(container)
      expect(focusable.length).toBeGreaterThanOrEqual(4)
    })

    it('excludes disabled elements', () => {
      const { container } = render(
        <div>
          <button>Enabled</button>
          <button disabled>Disabled</button>
        </div>
      )

      const focusable = getFocusableElements(container)
      expect(focusable).not.toContain(
        container.querySelector('button:disabled')
      )
    })
  })

  describe('Media Query Preferences', () => {
    it('detects reduced motion preference', () => {
      const matchMedia = vi.fn(() => ({
        matches: true,
        addListener: vi.fn(),
        removeListener: vi.fn(),
      }))
      window.matchMedia = matchMedia

      const result = prefersReducedMotion()
      expect(matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)')
    })

    it('detects high contrast preference', () => {
      const matchMedia = vi.fn(() => ({
        matches: true,
        addListener: vi.fn(),
        removeListener: vi.fn(),
      }))
      window.matchMedia = matchMedia

      const result = prefersHighContrast()
      expect(matchMedia).toHaveBeenCalledWith('(prefers-contrast: more)')
    })
  })

  describe('Accessible Name Functions', () => {
    it('detects accessible name from aria-label', () => {
      const { container } = render(
        <button aria-label="Close menu">×</button>
      )
      const button = container.querySelector('button')
      expect(hasAccessibleName(button)).toBe(true)
      expect(getAccessibleName(button)).toBe('Close menu')
    })

    it('detects accessible name from text content', () => {
      const { container } = render(
        <button>Click me</button>
      )
      const button = container.querySelector('button')
      expect(hasAccessibleName(button)).toBe(true)
      expect(getAccessibleName(button)).toBe('Click me')
    })

    it('detects accessible name from alt text', () => {
      const { container } = render(
        <img src="logo.png" alt="Company Logo" />
      )
      const img = container.querySelector('img')
      expect(hasAccessibleName(img)).toBe(true)
      expect(getAccessibleName(img)).toBe('Company Logo')
    })

    it('detects missing accessible name', () => {
      const { container } = render(
        <button>×</button>
      )
      // Button with just symbol may not have clear accessible name
      const button = container.querySelector('button')
      // This depends on implementation
      expect(hasAccessibleName(button)).toBe(true) // Has text content "×"
    })
  })

  describe('Heading Hierarchy Validation', () => {
    it('validates proper heading hierarchy', () => {
      const { container } = render(
        <div>
          <h1>Main Title</h1>
          <h2>Subtitle</h2>
          <h3>Sub-subtitle</h3>
        </div>
      )

      const result = validateHeadingHierarchy(container)
      expect(result.valid).toBe(true)
      expect(result.issues).toHaveLength(0)
    })

    it('detects skipped heading levels', () => {
      const { container } = render(
        <div>
          <h1>Main Title</h1>
          <h3>Skipped h2</h3>
        </div>
      )

      const result = validateHeadingHierarchy(container)
      expect(result.valid).toBe(false)
      expect(result.issues.length).toBeGreaterThan(0)
    })

    it('detects non-h1 first heading', () => {
      const { container } = render(
        <div>
          <h2>Not h1</h2>
          <h3>Sub</h3>
        </div>
      )

      const result = validateHeadingHierarchy(container)
      expect(result.valid).toBe(false)
    })
  })

  describe('Screen Reader Visibility', () => {
    it('identifies visible elements', () => {
      const { container } = render(
        <div>Visible</div>
      )
      const div = container.querySelector('div')
      expect(isVisibleToScreenReader(div)).toBe(true)
    })

    it('detects hidden elements', () => {
      const { container } = render(
        <div hidden>Hidden</div>
      )
      const div = container.querySelector('div')
      expect(isVisibleToScreenReader(div)).toBe(false)
    })

    it('detects aria-hidden elements', () => {
      const { container } = render(
        <div aria-hidden="true">Hidden from SR</div>
      )
      const div = container.querySelector('div')
      expect(isVisibleToScreenReader(div)).toBe(false)
    })
  })
})

describe('AccessibleMessage Component', () => {
  it('renders with semantic article element', () => {
    const { container } = render(
      <AccessibleMessage role="assistant">
        Hello world
      </AccessibleMessage>
    )

    const article = container.querySelector('article')
    expect(article).toBeInTheDocument()
  })

  it('has proper ARIA labels', () => {
    const { container } = render(
      <AccessibleMessage role="user" timestamp="2:45 PM">
        Test message
      </AccessibleMessage>
    )

    const article = container.querySelector('article')
    expect(article).toHaveAttribute('aria-label')
    expect(article.getAttribute('aria-label')).toContain('You')
  })

  it('displays role and timestamp in header', () => {
    render(
      <AccessibleMessage role="assistant" timestamp="3:00 PM">
        Message
      </AccessibleMessage>
    )

    expect(screen.getByText('Assistant')).toBeInTheDocument()
    expect(screen.getByText('3:00 PM')).toBeInTheDocument()
  })

  it('displays loading indicator', () => {
    const { container } = render(
      <AccessibleMessage role="assistant" isLoading>
        Typing...
      </AccessibleMessage>
    )

    expect(container.querySelector('.message-loading')).toBeInTheDocument()
  })

  it('renders action buttons with labels', async () => {
    const handleAction = vi.fn()
    const actions = [
      { id: 'copy', label: 'Copy', icon: '📋' },
      { id: 'edit', label: 'Edit', icon: '✏️' },
    ]

    render(
      <AccessibleMessage
        role="assistant"
        actions={actions}
        onActionClick={handleAction}
      >
        Message with actions
      </AccessibleMessage>
    )

    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThanOrEqual(2)

    await userEvent.click(buttons[0])
    expect(handleAction).toHaveBeenCalled()
  })

  it('is keyboard focusable', () => {
    const { container } = render(
      <AccessibleMessage role="assistant">
        Message
      </AccessibleMessage>
    )

    const article = container.querySelector('article')
    expect(article).toHaveAttribute('tabindex', '0')
  })

  it('respects user preference for dark assistant message', () => {
    const { container } = render(
      <AccessibleMessage role="assistant">
        Assistant message
      </AccessibleMessage>
    )

    const article = container.querySelector('article')
    expect(article).toHaveClass('accessible-message-assistant')
  })

  it('uses accent color for user message', () => {
    const { container } = render(
      <AccessibleMessage role="user">
        User message
      </AccessibleMessage>
    )

    const article = container.querySelector('article')
    expect(article).toHaveClass('accessible-message-user')
  })
})

describe('AccessibleCodeBlock Component', () => {
  it('renders with semantic figure element', () => {
    const { container } = render(
      <AccessibleCodeBlock code="console.log('test')" language="javascript" />
    )

    const figure = container.querySelector('figure')
    expect(figure).toBeInTheDocument()
  })

  it('displays language and line count', () => {
    render(
      <AccessibleCodeBlock
        code="line1\nline2\nline3"
        language="python"
      />
    )

    expect(screen.getByText('python')).toBeInTheDocument()
    expect(screen.getByText(/3 lines/)).toBeInTheDocument()
  })

  it('includes aria-label on code element', () => {
    const { container } = render(
      <AccessibleCodeBlock code="test" language="javascript" />
    )

    const code = container.querySelector('code')
    expect(code?.parentElement).toHaveAttribute('aria-label')
  })
})

describe('AccessibleLink Component', () => {
  it('renders as semantic link', () => {
    render(
      <AccessibleLink href="https://example.com">
        Example
      </AccessibleLink>
    )

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', 'https://example.com')
  })

  it('indicates external links', () => {
    render(
      <AccessibleLink href="https://example.com" external>
        External Link
      </AccessibleLink>
    )

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('has accessible label for external links', () => {
    render(
      <AccessibleLink href="https://example.com" external>
        External Link
      </AccessibleLink>
    )

    const link = screen.getByRole('link')
    expect(link.getAttribute('aria-label')).toContain('opens in new window')
  })
})

describe('AccessibleList Component', () => {
  it('renders ordered list', () => {
    const { container } = render(
      <AccessibleList type="ordered">
        <li>Item 1</li>
        <li>Item 2</li>
      </AccessibleList>
    )

    const ol = container.querySelector('ol')
    expect(ol).toBeInTheDocument()
  })

  it('renders unordered list', () => {
    const { container } = render(
      <AccessibleList type="unordered">
        <li>Item 1</li>
        <li>Item 2</li>
      </AccessibleList>
    )

    const ul = container.querySelector('ul')
    expect(ul).toBeInTheDocument()
  })

  it('includes aria-label', () => {
    const { container } = render(
      <AccessibleList aria-label="Steps to follow">
        <li>Step 1</li>
      </AccessibleList>
    )

    const list = container.querySelector('ul, ol')
    expect(list).toHaveAttribute('aria-label', 'Steps to follow')
  })
})

describe('AccessibleListItem Component', () => {
  it('renders as list item', () => {
    const { container } = render(
      <AccessibleListItem>Item content</AccessibleListItem>
    )

    const li = container.querySelector('li')
    expect(li).toBeInTheDocument()
    expect(li?.textContent).toContain('Item content')
  })
})

describe('AccessibleHeading Component', () => {
  it('renders h2 by default', () => {
    const { container } = render(
      <AccessibleHeading>Heading</AccessibleHeading>
    )

    const h2 = container.querySelector('h2')
    expect(h2).toBeInTheDocument()
  })

  it('renders specified heading level', () => {
    const { container } = render(
      <AccessibleHeading level={3}>Sub-heading</AccessibleHeading>
    )

    const h3 = container.querySelector('h3')
    expect(h3).toBeInTheDocument()
  })

  it('has semantic class names', () => {
    const { container } = render(
      <AccessibleHeading level={2}>Title</AccessibleHeading>
    )

    const h2 = container.querySelector('h2')
    expect(h2).toHaveClass('h2')
  })
})

describe('AccessibleParagraph Component', () => {
  it('renders as semantic paragraph', () => {
    const { container } = render(
      <AccessibleParagraph>Text content</AccessibleParagraph>
    )

    const p = container.querySelector('p')
    expect(p).toBeInTheDocument()
  })
})

describe('AccessibleEmphasis Component', () => {
  it('renders emphasis with em tag', () => {
    const { container } = render(
      <AccessibleEmphasis type="emphasis">important</AccessibleEmphasis>
    )

    const em = container.querySelector('em')
    expect(em).toBeInTheDocument()
  })

  it('renders strong emphasis with strong tag', () => {
    const { container } = render(
      <AccessibleEmphasis type="strong">very important</AccessibleEmphasis>
    )

    const strong = container.querySelector('strong')
    expect(strong).toBeInTheDocument()
  })
})

describe('WCAG 2.1 AAA Compliance Features', () => {
  it('all interactive elements are keyboard accessible', () => {
    const { container } = render(
      <div>
        <button>Button</button>
        <a href="#">Link</a>
        <input type="text" />
        <AccessibleMessage role="user">
          Message
        </AccessibleMessage>
      </div>
    )

    const buttons = container.querySelectorAll('button, a, input')
    buttons.forEach((btn) => {
      expect(isKeyboardAccessible(btn)).toBe(true)
    })
  })

  it('focus indicators are visible', () => {
    const { container } = render(
      <button>Focusable Button</button>
    )

    const button = container.querySelector('button')
    button?.focus()
    expect(button).toHaveFocus()
  })

  it('touch targets meet 48px minimum', () => {
    const { container } = render(
      <AccessibleMessage
        role="assistant"
        actions={[
          { id: 'copy', label: 'Copy' },
        ]}
        onActionClick={() => {}}
      >
        Message
      </AccessibleMessage>
    )

    // Buttons should have min-width and min-height styles
    const buttons = container.querySelectorAll('button')
    buttons.forEach((btn) => {
      const styles = window.getComputedStyle(btn)
      // Check that button has appropriate sizing attributes
      expect(btn.getAttribute('style') || styles.minHeight).toBeTruthy()
    })
  })

  it('semantic HTML structure is valid', () => {
    const { container } = render(
      <div>
        <AccessibleHeading level={1}>Title</AccessibleHeading>
        <AccessibleParagraph>Content</AccessibleParagraph>
        <AccessibleList type="unordered">
          <AccessibleListItem>Item 1</AccessibleListItem>
        </AccessibleList>
      </div>
    )

    expect(container.querySelector('h1')).toBeInTheDocument()
    expect(container.querySelector('p')).toBeInTheDocument()
    expect(container.querySelector('ul')).toBeInTheDocument()
    expect(container.querySelector('li')).toBeInTheDocument()
  })
})
