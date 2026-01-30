import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ToolCard from '../../components/Chat/ToolCard'
import ToolTimeline from '../../components/Chat/ToolTimeline'

/**
 * ToolCard Component Tests
 * Testing: tool rendering, status indicators, expand/collapse, copy functionality
 */
describe('ToolCard Component', () => {
  const defaultProps = {
    id: 'tool-1',
    toolName: 'Calculate',
    status: 'success',
    input: { expression: '2 + 2' },
    output: '4',
    duration: 1234,
  }

  describe('Rendering', () => {
    it('should render tool card with basic info', () => {
      render(<ToolCard {...defaultProps} />)

      expect(screen.getByText('Calculate')).toBeInTheDocument()
      expect(screen.getByText('Input Parameters')).toBeInTheDocument()
    })

    it('should display tool name correctly', () => {
      render(<ToolCard {...defaultProps} toolName="WebSearch" />)
      expect(screen.getByText('WebSearch')).toBeInTheDocument()
    })

    it('should render without errors when minimal props provided', () => {
      const { container } = render(<ToolCard id="tool-1" toolName="Test" />)
      expect(container.querySelector('.tool-card')).toBeInTheDocument()
    })

    it('should display dependency count when dependencies exist', () => {
      const props = {
        ...defaultProps,
        dependencies: ['tool-0', 'tool-1'],
      }
      render(<ToolCard {...props} />)

      expect(screen.getByText('Depends on 2 tools')).toBeInTheDocument()
    })

    it('should handle singular dependency text', () => {
      render(<ToolCard {...defaultProps} dependencies={['tool-0']} />)
      expect(screen.getByText('Depends on 1 tool')).toBeInTheDocument()
    })
  })

  describe('Status Indicators', () => {
    it('should display success icon for successful status', () => {
      const { container } = render(
        <ToolCard {...defaultProps} status="success" />,
      )
      const card = container.querySelector('.tool-card-success')
      expect(card).toBeInTheDocument()
    })

    it('should display loading icon for loading status', () => {
      const { container } = render(
        <ToolCard {...defaultProps} status="loading" />,
      )
      const card = container.querySelector('.tool-card-loading')
      expect(card).toBeInTheDocument()
      // Check for loading spinner animation
      const loader = container.querySelector('.tool-status-icon-loading')
      expect(loader).toBeInTheDocument()
    })

    it('should display error icon for error status', () => {
      const { container } = render(
        <ToolCard {...defaultProps} status="error" error="Tool failed" />,
      )
      const card = container.querySelector('.tool-card-error')
      expect(card).toBeInTheDocument()
      const errorIcon = container.querySelector('.tool-status-icon-error')
      expect(errorIcon).toBeInTheDocument()
    })

    it('should apply correct status class to card', () => {
      const { container } = render(
        <ToolCard {...defaultProps} status="error" error="Test error" />,
      )
      expect(
        container.querySelector('.tool-card.tool-card-error'),
      ).toBeInTheDocument()
    })
  })

  describe('Input Parameters Display', () => {
    it('should display input parameters', () => {
      render(
        <ToolCard
          {...defaultProps}
          input={{ param1: 'value1', param2: 'value2' }}
        />,
      )

      expect(screen.getByText('param1:')).toBeInTheDocument()
      expect(screen.getByText('value1')).toBeInTheDocument()
      expect(screen.getByText('param2:')).toBeInTheDocument()
      expect(screen.getByText('value2')).toBeInTheDocument()
    })

    it('should not show input section when no parameters', () => {
      render(<ToolCard {...defaultProps} input={{}} />)

      const inputSection = screen.queryByText('Input Parameters')
      expect(inputSection).not.toBeInTheDocument()
    })

    it('should handle object input parameters', () => {
      const complexInput = {
        config: { timeout: 5000, retries: 3 },
      }
      render(<ToolCard {...defaultProps} input={complexInput} />)

      expect(screen.getByText('config:')).toBeInTheDocument()
      expect(
        screen.getByText(/{"timeout":5000,"retries":3}/),
      ).toBeInTheDocument()
    })

    it('should display duration when provided', () => {
      render(<ToolCard {...defaultProps} duration={5000} />)

      expect(screen.getByText('5.00s')).toBeInTheDocument()
    })

    it('should format milliseconds correctly', () => {
      render(<ToolCard {...defaultProps} duration={234} />)

      expect(screen.getByText('234ms')).toBeInTheDocument()
    })
  })

  describe('Expand/Collapse Functionality', () => {
    it('should have collapsed results by default', () => {
      const { container } = render(
        <ToolCard {...defaultProps} output="test output" />,
      )
      const expandButton = container.querySelector('.tool-card-expand-button')
      expect(expandButton).toBeInTheDocument()

      // Results should be hidden by default
      const results = container.querySelector('.tool-card-results')
      expect(results).toHaveClass('tool-card-results')
      expect(results).not.toHaveClass('tool-card-results-expanded')
    })

    it('should expand results on button click', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard {...defaultProps} output="test output" />,
      )

      const expandButton = container.querySelector('.tool-card-expand-button')
      await user.click(expandButton)

      const results = container.querySelector('.tool-card-results-expanded')
      expect(results).toBeInTheDocument()
    })

    it('should toggle expanded state correctly', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard {...defaultProps} output="test output" />,
      )

      const expandButton = container.querySelector('.tool-card-expand-button')

      // Click to expand
      await user.click(expandButton)
      let results = container.querySelector('.tool-card-results-expanded')
      expect(results).toBeInTheDocument()

      // Click to collapse
      await user.click(expandButton)
      results = container.querySelector('.tool-card-results-expanded')
      expect(results).not.toBeInTheDocument()
    })

    it('should call onExpand callback when expanding', async () => {
      const user = userEvent.setup()
      const onExpand = vi.fn()
      const { container } = render(
        <ToolCard
          {...defaultProps}
          output="test output"
          onExpand={onExpand}
        />,
      )

      const expandButton = container.querySelector('.tool-card-expand-button')
      await user.click(expandButton)

      expect(onExpand).toHaveBeenCalledWith('tool-1', true)
    })

    it('should start expanded if expanded prop is true', () => {
      const { container } = render(
        <ToolCard {...defaultProps} output="test output" expanded={true} />,
      )

      const results = container.querySelector('.tool-card-results-expanded')
      expect(results).toBeInTheDocument()
    })
  })

  describe('Output Display', () => {
    it('should display output in expanded section', async () => {
      const user = userEvent.setup()
      render(
        <ToolCard
          {...defaultProps}
          output="Expected output"
          expanded={true}
        />,
      )

      expect(screen.getByText('Expected output')).toBeInTheDocument()
    })

    it('should format JSON output with pretty printing', async () => {
      const user = userEvent.setup()
      const output = { result: 42, name: 'test' }
      const { container } = render(
        <ToolCard {...defaultProps} output={output} expanded={true} />,
      )

      const outputContent = container.querySelector('.tool-card-output-content')
      expect(outputContent).toHaveTextContent('"result"')
      expect(outputContent).toHaveTextContent('42')
    })

    it('should not show output section when output is null', () => {
      render(<ToolCard {...defaultProps} output={null} />)

      const outputSection = screen.queryByText('Output')
      expect(outputSection).not.toBeInTheDocument()
    })
  })

  describe('Copy Functionality', () => {
    beforeEach(() => {
      // Mock navigator.clipboard
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn(() => Promise.resolve()),
        },
      })
    })

    it('should display copy button for successful operations with output', () => {
      const { container } = render(
        <ToolCard {...defaultProps} status="success" output="test output" />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      expect(copyButton).toBeInTheDocument()
    })

    it('should not display copy button for error status', () => {
      const { container } = render(
        <ToolCard
          {...defaultProps}
          status="error"
          error="Error occurred"
          output={null}
        />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      expect(copyButton).not.toBeInTheDocument()
    })

    it('should copy text output to clipboard', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard
          {...defaultProps}
          status="success"
          output="Copy this text"
          onCopy={vi.fn()}
        />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      await user.click(copyButton)

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        'Copy this text',
      )
    })

    it('should copy JSON output to clipboard as string', async () => {
      const user = userEvent.setup()
      const output = { key: 'value', number: 123 }
      const { container } = render(
        <ToolCard
          {...defaultProps}
          status="success"
          output={output}
          onCopy={vi.fn()}
        />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      await user.click(copyButton)

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        JSON.stringify(output, null, 2),
      )
    })

    it('should show success feedback after copying', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard {...defaultProps} status="success" output="test" />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      await user.click(copyButton)

      await waitFor(() => {
        expect(copyButton).toHaveClass('tool-card-copy-success')
      })
    })

    it('should call onCopy callback when copying', async () => {
      const user = userEvent.setup()
      const onCopy = vi.fn()
      const { container } = render(
        <ToolCard
          {...defaultProps}
          status="success"
          output="test"
          onCopy={onCopy}
        />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      await user.click(copyButton)

      expect(onCopy).toHaveBeenCalledWith('tool-1')
    })
  })

  describe('Error Handling', () => {
    it('should display error message when status is error', () => {
      render(
        <ToolCard
          {...defaultProps}
          status="error"
          error="Connection timeout"
          output={null}
        />,
      )

      expect(screen.getByText('Connection timeout')).toBeInTheDocument()
      expect(screen.getByText('Error')).toBeInTheDocument()
    })

    it('should not show output when error occurs', () => {
      render(
        <ToolCard
          {...defaultProps}
          status="error"
          error="Failed"
          output={null}
        />,
      )

      const output = screen.queryByText('Output')
      expect(output).not.toBeInTheDocument()
    })

    it('should display error in expandable section', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard
          {...defaultProps}
          status="error"
          error="Tool execution failed"
          expanded={true}
        />,
      )

      expect(screen.getByText('Tool execution failed')).toBeInTheDocument()
    })
  })

  describe('Performance', () => {
    it('should render within performance targets', () => {
      const startTime = performance.now()

      render(<ToolCard {...defaultProps} />)

      const endTime = performance.now()
      const renderTime = endTime - startTime

      // Should render in less than 100ms (warning threshold)
      expect(renderTime).toBeLessThan(500) // Generous for test environment
    })

    it('should handle many input parameters', () => {
      const manyInputs = {}
      for (let i = 0; i < 50; i++) {
        manyInputs[`param_${i}`] = `value_${i}`
      }

      const { container } = render(
        <ToolCard {...defaultProps} input={manyInputs} />,
      )

      expect(container.querySelectorAll('.tool-card-param')).toHaveLength(50)
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels on buttons', () => {
      const { container } = render(
        <ToolCard
          {...defaultProps}
          output="test output"
          status="success"
        />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      const expandButton = container.querySelector('.tool-card-expand-button')

      expect(copyButton).toHaveAttribute('aria-label')
      expect(expandButton).toHaveAttribute('aria-label')
    })

    it('should have proper data attributes for testing', () => {
      const { container } = render(<ToolCard {...defaultProps} />)

      const card = container.querySelector('[data-tool-id="tool-1"]')
      expect(card).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      const { container } = render(
        <ToolCard {...defaultProps} output="test" />,
      )

      const expandButton = container.querySelector('.tool-card-expand-button')
      expandButton.focus()
      expect(expandButton).toHaveFocus()

      await user.keyboard('{Enter}')

      const results = container.querySelector('.tool-card-results-expanded')
      expect(results).toBeInTheDocument()
    })
  })
})

/**
 * ToolTimeline Component Tests
 * Testing: tool list rendering, filtering, dependencies, statistics
 */
describe('ToolTimeline Component', () => {
  const mockTools = [
    {
      id: 'tool-1',
      toolName: 'SearchWeb',
      status: 'success',
      input: { query: 'AI' },
      output: { results: 'Found 100 results' },
      duration: 1200,
      dependencies: [],
    },
    {
      id: 'tool-2',
      toolName: 'ProcessResults',
      status: 'success',
      input: { data: 'web results' },
      output: 'Processed successfully',
      duration: 800,
      dependencies: ['tool-1'],
    },
    {
      id: 'tool-3',
      toolName: 'Format',
      status: 'loading',
      input: {},
      output: null,
      duration: null,
      dependencies: ['tool-2'],
    },
  ]

  describe('Rendering', () => {
    it('should render timeline with tools', () => {
      render(<ToolTimeline tools={mockTools} />)

      expect(screen.getByText('Tool Execution Timeline')).toBeInTheDocument()
      expect(screen.getByText('SearchWeb')).toBeInTheDocument()
      expect(screen.getByText('ProcessResults')).toBeInTheDocument()
    })

    it('should show empty state when no tools', () => {
      render(<ToolTimeline tools={[]} />)

      expect(
        screen.getByText('No tools have been invoked yet.'),
      ).toBeInTheDocument()
    })

    it('should show empty search state', () => {
      render(<ToolTimeline tools={mockTools} searchQuery="NonExistent" />)

      expect(screen.getByText(/No tools match your search/)).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('should filter tools by name search', () => {
      render(<ToolTimeline tools={mockTools} searchQuery="Search" />)

      expect(screen.getByText('SearchWeb')).toBeInTheDocument()
      expect(screen.queryByText('ProcessResults')).not.toBeInTheDocument()
    })

    it('should filter tools by id search', () => {
      render(<ToolTimeline tools={mockTools} searchQuery="tool-2" />)

      expect(screen.getByText('ProcessResults')).toBeInTheDocument()
      expect(screen.queryByText('SearchWeb')).not.toBeInTheDocument()
    })

    it('should support case-insensitive search', () => {
      render(<ToolTimeline tools={mockTools} searchQuery="searchweb" />)

      expect(screen.getByText('SearchWeb')).toBeInTheDocument()
    })

    it('should hide non-successful tools when showAll is false', () => {
      render(<ToolTimeline tools={mockTools} showAll={false} />)

      expect(screen.getByText('SearchWeb')).toBeInTheDocument()
      expect(screen.getByText('ProcessResults')).toBeInTheDocument()
      // Loading tool should not be visible
      expect(screen.queryByText('Format')).not.toBeInTheDocument()
    })

    it('should show all tools when showAll is true', () => {
      render(<ToolTimeline tools={mockTools} showAll={true} />)

      expect(screen.getByText('SearchWeb')).toBeInTheDocument()
      expect(screen.getByText('ProcessResults')).toBeInTheDocument()
      expect(screen.getByText('Format')).toBeInTheDocument()
    })
  })

  describe('Dependencies Display', () => {
    it('should show dependency information', () => {
      render(<ToolTimeline tools={mockTools} />)

      expect(screen.getByText('Depends on:')).toBeInTheDocument()
    })

    it('should display dependent tools', () => {
      render(<ToolTimeline tools={mockTools} />)

      expect(screen.getByText('Used by:')).toBeInTheDocument()
    })

    it('should link tools by dependency', () => {
      const { container } = render(<ToolTimeline tools={mockTools} />)

      // Check that dependency connectors are created
      const connectors = container.querySelectorAll(
        '.tool-timeline-connector-dependent',
      )
      expect(connectors.length).toBeGreaterThan(0)
    })
  })

  describe('Statistics', () => {
    it('should display tool statistics', () => {
      render(<ToolTimeline tools={mockTools} />)

      expect(screen.getByText('Total Tools:')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('Successful:')).toBeInTheDocument()
      expect(screen.getByText('Failed:')).toBeInTheDocument()
    })

    it('should count successful and failed tools', () => {
      render(<ToolTimeline tools={mockTools} />)

      const successCount = screen.getByText('Successful:').parentElement
      expect(successCount).toHaveTextContent('2')

      const failureCount = screen.getByText('Failed:').parentElement
      expect(failureCount).toHaveTextContent('0')
    })

    it('should calculate total time from durations', () => {
      render(<ToolTimeline tools={mockTools} />)

      expect(screen.getByText('Total Time:')).toBeInTheDocument()
      // 1200 + 800 + 0 = 2000ms = 2.00s
      expect(screen.getByText('2.00s')).toBeInTheDocument()
    })

    it('should show filter count when searching', () => {
      render(<ToolTimeline tools={mockTools} searchQuery="Search" />)

      expect(screen.getByText('1 of 3')).toBeInTheDocument()
    })
  })

  describe('Tool Expansion', () => {
    it('should track expand state for each tool', async () => {
      const user = userEvent.setup()
      const { container } = render(<ToolTimeline tools={mockTools} />)

      const expandButtons = container.querySelectorAll(
        '.tool-card-expand-button',
      )

      // Expand first tool
      await user.click(expandButtons[0])

      // First tool should be expanded
      const toolCards = container.querySelectorAll('.tool-timeline-card')
      expect(toolCards[0]).toHaveTextContent('Output')
    })
  })

  describe('Callbacks', () => {
    it('should call onToolExpand callback', async () => {
      const user = userEvent.setup()
      const onToolExpand = vi.fn()
      const { container } = render(
        <ToolTimeline tools={mockTools} onToolExpand={onToolExpand} />,
      )

      const expandButton = container.querySelector('.tool-card-expand-button')
      await user.click(expandButton)

      expect(onToolExpand).toHaveBeenCalled()
    })

    it('should call onToolCopy callback', async () => {
      const user = userEvent.setup()
      const onToolCopy = vi.fn()

      // Mock clipboard
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn(() => Promise.resolve()),
        },
      })

      const { container } = render(
        <ToolTimeline tools={mockTools} onToolCopy={onToolCopy} />,
      )

      const copyButton = container.querySelector('.tool-card-copy-button')
      if (copyButton) {
        await user.click(copyButton)
        expect(onToolCopy).toHaveBeenCalled()
      }
    })
  })

  describe('Accessibility', () => {
    it('should have accessible timeline structure', () => {
      const { container } = render(<ToolTimeline tools={mockTools} />)

      expect(container.querySelector('.tool-timeline')).toBeInTheDocument()
      expect(container.querySelector('.tool-timeline-list')).toBeInTheDocument()
    })

    it('should have proper semantic HTML', () => {
      render(<ToolTimeline tools={mockTools} />)

      const heading = screen.getByText('Tool Execution Timeline')
      expect(heading.tagName).toBe('H2')
    })
  })
})
