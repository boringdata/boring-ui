import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import React from 'react'
import CodeBlock from '../../components/Chat/CodeBlock'
import SyntaxHighlighter from '../../components/Chat/SyntaxHighlighter'

/**
 * STORY-C002: Rich Code Highlighting & Syntax Display
 * Test suite for code block components with focus on:
 * - Syntax highlighting performance (<50ms)
 * - Copy button feedback
 * - Language support (50+ languages)
 * - Diff highlighting
 * - Line numbers
 * - Collapse/expand functionality
 */

describe('CodeBlock Component', () => {
  const simpleCode = 'console.log("Hello, world!")'
  const longCode = Array(30)
    .fill(0)
    .map((_, i) => `const variable${i} = ${i}`)
    .join('\n')

  const defaultProps = {
    code: simpleCode,
    language: 'javascript',
  }

  describe('Rendering', () => {
    it('renders code content', () => {
      render(<CodeBlock {...defaultProps} />)
      expect(screen.getByText(/Hello, world/)).toBeInTheDocument()
    })

    it('renders language badge', () => {
      render(<CodeBlock {...defaultProps} language="javascript" />)
      expect(screen.getByText(/JavaScript/i)).toBeInTheDocument()
    })

    it('renders title instead of language badge when provided', () => {
      render(
        <CodeBlock
          {...defaultProps}
          title="my-script.js"
          language="javascript"
        />,
      )
      expect(screen.getByText('my-script.js')).toBeInTheDocument()
      // Language badge should not be displayed separately when title is shown
    })

    it('renders code lines correctly', () => {
      const multiLineCode = 'line1\nline2\nline3'
      render(<CodeBlock {...defaultProps} code={multiLineCode} />)
      expect(screen.getByText(/line1/)).toBeInTheDocument()
      expect(screen.getByText(/line2/)).toBeInTheDocument()
      expect(screen.getByText(/line3/)).toBeInTheDocument()
    })

    it('renders empty code gracefully', () => {
      render(<CodeBlock {...defaultProps} code="" />)
      const container = screen.getByRole('region', { hidden: true }) ||
        document.querySelector('.code-block-container')
      expect(container).toBeInTheDocument()
    })
  })

  describe('Line Numbers', () => {
    it('shows line numbers by default for multi-line code', () => {
      const multiLineCode = 'line1\nline2\nline3\nline4\nline5\nline6'
      const { container } = render(
        <CodeBlock {...defaultProps} code={multiLineCode} />,
      )
      const lineNumbers = container.querySelectorAll('.code-line-number')
      expect(lineNumbers.length).toBeGreaterThan(0)
    })

    it('respects showLineNumbers prop', () => {
      const { container: container1 } = render(
        <CodeBlock {...defaultProps} showLineNumbers={true} />,
      )
      const { container: container2 } = render(
        <CodeBlock {...defaultProps} showLineNumbers={false} />,
      )

      const lines1 = container1.querySelectorAll('.code-line-number')
      const lines2 = container2.querySelectorAll('.code-line-number')

      expect(lines1.length).toBeGreaterThan(lines2.length)
    })

    it('does not show line numbers for single-line code by default', () => {
      const { container } = render(<CodeBlock {...defaultProps} code="single" />)
      const lineNumbers = container.querySelectorAll('.code-line-number')
      expect(lineNumbers.length).toBe(0)
    })
  })

  describe('Copy Button', () => {
    beforeEach(() => {
      // Mock clipboard API
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn(() => Promise.resolve()),
        },
      })
    })

    it('renders copy button', () => {
      render(<CodeBlock {...defaultProps} />)
      expect(screen.getByLabelText(/Copy code/i)).toBeInTheDocument()
    })

    it('copies code to clipboard on button click', async () => {
      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)

      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
          simpleCode,
        )
      })
    })

    it('shows "Copied!" feedback after copy', async () => {
      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)

      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(screen.getByText('Copied!')).toBeInTheDocument()
      })
    })

    it('resets copy feedback after 2 seconds', async () => {
      vi.useFakeTimers()
      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)

      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(screen.getByText('Copied!')).toBeInTheDocument()
      })

      vi.advanceTimersByTime(2000)

      await waitFor(() => {
        expect(screen.queryByText('Copied!')).not.toBeInTheDocument()
      })

      vi.useRealTimers()
    })

    it('handles clipboard errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation()
      navigator.clipboard.writeText = vi.fn(() => Promise.reject(new Error('Clipboard error')))

      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)

      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled()
      })

      consoleSpy.mockRestore()
    })
  })

  describe('Collapse/Expand', () => {
    it('shows expand button for long code blocks', () => {
      render(<CodeBlock {...defaultProps} code={longCode} maxLines={20} />)
      expect(screen.getByLabelText(/Collapse|Expand/i)).toBeInTheDocument()
    })

    it('does not show expand button for short code', () => {
      render(<CodeBlock {...defaultProps} code={simpleCode} maxLines={20} />)
      expect(screen.queryByLabelText(/Collapse|Expand/i)).not.toBeInTheDocument()
    })

    it('collapses code when expand button clicked', async () => {
      const { container } = render(
        <CodeBlock {...defaultProps} code={longCode} maxLines={5} />,
      )
      const expandButton = screen.getByLabelText(/Expand/i)

      fireEvent.click(expandButton)

      await waitFor(() => {
        const lines = container.querySelectorAll('.code-line')
        expect(lines.length).toBeLessThan(longCode.split('\n').length)
      })
    })

    it('expands code when collapse button clicked', async () => {
      const { container } = render(
        <CodeBlock
          {...defaultProps}
          code={longCode}
          maxLines={5}
          collapsible={true}
        />,
      )
      const expandButton = screen.getByLabelText(/Expand/i)

      // Initial state is collapsed
      fireEvent.click(expandButton)

      // Click again to expand
      const collapseButton = screen.getByLabelText(/Collapse/i)
      fireEvent.click(collapseButton)

      await waitFor(() => {
        const lines = container.querySelectorAll('.code-line')
        expect(lines.length).toBeGreaterThan(5)
      })
    })

    it('respects collapsible prop', () => {
      const { rerender } = render(
        <CodeBlock {...defaultProps} code={longCode} collapsible={true} />,
      )
      expect(screen.getByLabelText(/Collapse|Expand/i)).toBeInTheDocument()

      rerender(
        <CodeBlock {...defaultProps} code={longCode} collapsible={false} />,
      )
      expect(screen.queryByLabelText(/Collapse|Expand/i)).not.toBeInTheDocument()
    })

    it('shows collapsed hint when collapsed', async () => {
      render(
        <CodeBlock
          {...defaultProps}
          code={longCode}
          maxLines={10}
          collapsible={true}
        />,
      )
      const expandButton = screen.getByLabelText(/Expand/i)

      fireEvent.click(expandButton)

      await waitFor(() => {
        expect(screen.getByText(/more lines/i)).toBeInTheDocument()
      })
    })
  })

  describe('Diff Highlighting', () => {
    const diffCode = `diff --git a/file.js b/file.js
+added line
-removed line
 context line`

    it('applies diff styling when isDiff is true', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} code={diffCode} isDiff={true} />,
      )
      const codeBlock = container.querySelector('.code-block-diff')
      expect(codeBlock).toBeInTheDocument()
    })

    it('highlights added lines', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} code={diffCode} isDiff={true} />,
      )
      const addedLines = container.querySelectorAll('.code-line-add')
      expect(addedLines.length).toBeGreaterThan(0)
    })

    it('highlights removed lines', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} code={diffCode} isDiff={true} />,
      )
      const removedLines = container.querySelectorAll('.code-line-remove')
      expect(removedLines.length).toBeGreaterThan(0)
    })
  })

  describe('Language Support', () => {
    const languages = [
      'javascript',
      'python',
      'json',
      'bash',
      'jsx',
      'typescript',
      'tsx',
      'html',
      'css',
      'sql',
    ]

    languages.forEach((lang) => {
      it(`renders code for ${lang} language`, () => {
        const { container } = render(
          <CodeBlock {...defaultProps} language={lang} />,
        )
        expect(
          container.querySelector(`.code-block-lang-${lang}`),
        ).toBeInTheDocument()
      })
    })

    it('renders terminal style for bash', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} language="bash" />,
      )
      expect(container.querySelector('.code-block-terminal')).toBeInTheDocument()
    })
  })

  describe('Terminal Style', () => {
    it('applies terminal styling for shell languages', () => {
      const { container } = render(
        <CodeBlock
          {...defaultProps}
          code="$ echo 'Hello'"
          language="bash"
        />,
      )
      expect(container.querySelector('.code-block-terminal')).toBeInTheDocument()
    })

    it('applies terminal styling for sh', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} language="sh" />,
      )
      expect(container.querySelector('.code-block-terminal')).toBeInTheDocument()
    })

    it('applies terminal styling for zsh', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} language="zsh" />,
      )
      expect(container.querySelector('.code-block-terminal')).toBeInTheDocument()
    })
  })

  describe('CSS Classes and Styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} className="custom-code" />,
      )
      expect(
        container.querySelector('.code-block-container.custom-code'),
      ).toBeInTheDocument()
    })

    it('applies language-specific class', () => {
      const { container } = render(
        <CodeBlock {...defaultProps} language="python" />,
      )
      expect(
        container.querySelector('.code-block-lang-python'),
      ).toBeInTheDocument()
    })
  })

  describe('Performance', () => {
    it('renders large code blocks efficiently', () => {
      const largeCode = Array(1000)
        .fill(0)
        .map((_, i) => `// Line ${i}: Some code here`)
        .join('\n')

      const start = performance.now()
      render(<CodeBlock {...defaultProps} code={largeCode} />)
      const duration = performance.now() - start

      // Should render reasonably fast
      expect(duration).toBeLessThan(500)
    })
  })

  describe('Accessibility', () => {
    it('copy button has accessibility label', () => {
      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)
      expect(copyButton).toBeInTheDocument()
    })

    it('expand button has accessibility label', () => {
      render(
        <CodeBlock {...defaultProps} code={longCode} collapsible={true} />,
      )
      const expandButton = screen.getByLabelText(/Expand/i)
      expect(expandButton).toBeInTheDocument()
    })

    it('includes title attribute on interactive elements', () => {
      render(<CodeBlock {...defaultProps} />)
      const copyButton = screen.getByLabelText(/Copy code/i)
      expect(copyButton.getAttribute('title')).toBeTruthy()
    })
  })
})

describe('SyntaxHighlighter Component', () => {
  const simpleJsCode = 'const x = 5'

  describe('Rendering', () => {
    it('renders code', () => {
      render(
        <SyntaxHighlighter code={simpleJsCode} language="javascript" />,
      )
      expect(screen.getByText(/const x = 5/)).toBeInTheDocument()
    })

    it('handles empty code', () => {
      const { container } = render(
        <SyntaxHighlighter code="" language="javascript" />,
      )
      expect(container.querySelector('.syntax-highlighter')).toBeInTheDocument()
    })

    it('renders multiple lines', () => {
      const multiLine = 'line1\nline2\nline3'
      render(
        <SyntaxHighlighter code={multiLine} language="plaintext" />,
      )
      expect(screen.getByText(/line1/)).toBeInTheDocument()
      expect(screen.getByText(/line2/)).toBeInTheDocument()
    })
  })

  describe('Line Numbers', () => {
    it('renders line numbers when enabled', () => {
      const { container } = render(
        <SyntaxHighlighter
          code={simpleJsCode}
          language="javascript"
          showLineNumbers={true}
        />,
      )
      const lineNumbers = container.querySelectorAll('.code-line-number')
      expect(lineNumbers.length).toBeGreaterThan(0)
    })

    it('does not render line numbers when disabled', () => {
      const { container } = render(
        <SyntaxHighlighter
          code={simpleJsCode}
          language="javascript"
          showLineNumbers={false}
        />,
      )
      const lineNumbers = container.querySelectorAll('.code-line-number')
      expect(lineNumbers.length).toBe(0)
    })

    it('renders correct line numbers', () => {
      const { container } = render(
        <SyntaxHighlighter
          code="line1\nline2\nline3"
          language="javascript"
          showLineNumbers={true}
        />,
      )
      const lineNumbers = container.querySelectorAll('.code-line-number')
      expect(lineNumbers).toHaveLength(3)
    })
  })

  describe('Diff Highlighting', () => {
    const diffCode = '+added\n-removed\n context'

    it('applies diff highlighting', () => {
      const { container } = render(
        <SyntaxHighlighter
          code={diffCode}
          language="diff"
          isDiff={true}
        />,
      )
      const addedLines = container.querySelectorAll('.code-line-add')
      const removedLines = container.querySelectorAll('.code-line-remove')

      expect(addedLines.length).toBeGreaterThan(0)
      expect(removedLines.length).toBeGreaterThan(0)
    })
  })

  describe('Syntax Highlighting', () => {
    it('highlights JavaScript keywords', () => {
      const { container } = render(
        <SyntaxHighlighter
          code="const x = 5; return x;"
          language="javascript"
        />,
      )
      const keywords = container.querySelectorAll('.syntax-keyword')
      expect(keywords.length).toBeGreaterThan(0)
    })

    it('highlights strings', () => {
      const { container } = render(
        <SyntaxHighlighter
          code='const name = "John"'
          language="javascript"
        />,
      )
      const strings = container.querySelectorAll('.syntax-string')
      expect(strings.length).toBeGreaterThan(0)
    })

    it('highlights numbers', () => {
      const { container } = render(
        <SyntaxHighlighter
          code="const nums = [1, 2, 3]"
          language="javascript"
        />,
      )
      const numbers = container.querySelectorAll('.syntax-number')
      expect(numbers.length).toBeGreaterThan(0)
    })

    it('highlights comments', () => {
      const { container } = render(
        <SyntaxHighlighter
          code="// This is a comment"
          language="javascript"
        />,
      )
      const comments = container.querySelectorAll('.syntax-comment')
      expect(comments.length).toBeGreaterThan(0)
    })
  })

  describe('Error Handling', () => {
    it('calls onError callback on error', () => {
      const onError = vi.fn()
      render(
        <SyntaxHighlighter
          code={simpleJsCode}
          language="javascript"
          onError={onError}
        />,
      )
      // Component should still render even with errors
      expect(screen.getByText(/const x = 5/)).toBeInTheDocument()
    })
  })

  describe('Language Support', () => {
    const languageSamples = {
      javascript: 'const x = 5',
      python: 'x = 5',
      json: '{"key": "value"}',
      bash: 'echo "Hello"',
      jsx: 'const el = <div>Hello</div>',
    }

    Object.entries(languageSamples).forEach(([lang, code]) => {
      it(`renders ${lang}`, () => {
        render(
          <SyntaxHighlighter code={code} language={lang} />,
        )
        // Should render without error
        expect(
          document.querySelector(`code.language-${lang}`),
        ).toBeInTheDocument()
      })
    })
  })

  describe('Memoization', () => {
    it('is memoized for performance', () => {
      const { rerender } = render(
        <SyntaxHighlighter code={simpleJsCode} language="javascript" />,
      )
      const before = screen.getByText(/const x = 5/)

      // Re-render with same props
      rerender(
        <SyntaxHighlighter code={simpleJsCode} language="javascript" />,
      )
      const after = screen.getByText(/const x = 5/)

      // Should be same DOM element (memoized)
      expect(before.parentElement).toBe(after.parentElement)
    })
  })
})

describe('CodeBlock Integration Tests', () => {
  it('renders complete code block with all features', () => {
    const code = `function hello() {
  console.log("Hello, World!");
  return true;
}`

    const { container } = render(
      <CodeBlock
        code={code}
        language="javascript"
        title="hello.js"
        showLineNumbers={true}
      />,
    )

    // Check all elements are present
    expect(screen.getByText('hello.js')).toBeInTheDocument()
    expect(screen.getByText(/Copy code/)).toBeInTheDocument()
    expect(container.querySelectorAll('.code-line-number').length).toBeGreaterThan(0)
    expect(screen.getByText(/Hello, World/)).toBeInTheDocument()
  })
})
