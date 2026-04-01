import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ModelSelector from '../components/ModelSelector'

// Radix UI relies on PointerEvent which jsdom doesn't fully support.
// Polyfill PointerEvent as a MouseEvent subclass so Radix triggers work.
beforeAll(() => {
  if (!globalThis.PointerEvent) {
    class Pointer extends MouseEvent {
      constructor(type, props) {
        super(type, props)
        if (props?.pointerId != null) this.pointerId = props.pointerId
        if (props?.pointerType != null) this.pointerType = props.pointerType
      }
    }
    globalThis.PointerEvent = Pointer
  }
  // Radix checks this before using pointer events
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = vi.fn(() => false)
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = vi.fn()
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = vi.fn()
  }
})

const MOCK_MODELS = [
  {
    id: 'claude-sonnet-4-20250514',
    name: 'claude-sonnet-4',
    provider: 'Anthropic',
  },
  {
    id: 'claude-opus-4-20250514',
    name: 'claude-opus-4',
    provider: 'Anthropic',
  },
  {
    id: 'gpt-4o',
    name: 'gpt-4o',
    provider: 'OpenAI',
  },
  {
    id: 'gemini-2.5-pro',
    name: 'gemini-2.5-pro',
    provider: 'Google',
  },
]

/**
 * Helper: open a Radix DropdownMenu in jsdom.
 * Radix listens on pointerdown → click, so we dispatch both.
 */
function openDropdown(triggerEl) {
  fireEvent.pointerDown(triggerEl, { button: 0, pointerType: 'mouse' })
  fireEvent.click(triggerEl)
}

describe('ModelSelector', () => {
  const defaultProps = {
    currentModel: MOCK_MODELS[0],
    models: MOCK_MODELS,
    onModelChange: vi.fn(),
    disabled: false,
  }

  it('renders current model name in the trigger button', () => {
    render(<ModelSelector {...defaultProps} />)
    expect(screen.getByText('claude-sonnet-4')).toBeInTheDocument()
  })

  it('opens dropdown on click showing available models', async () => {
    render(<ModelSelector {...defaultProps} />)

    const trigger = screen.getByRole('button', { name: /claude-sonnet-4/i })
    openDropdown(trigger)

    // All model names should be visible in the dropdown
    expect(await screen.findByText('claude-opus-4')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('gemini-2.5-pro')).toBeInTheDocument()
  })

  it('selecting a model calls onModelChange callback', async () => {
    const onModelChange = vi.fn()
    render(<ModelSelector {...defaultProps} onModelChange={onModelChange} />)

    // Open the dropdown
    const trigger = screen.getByRole('button', { name: /claude-sonnet-4/i })
    openDropdown(trigger)

    // Click on a different model
    const gptOption = await screen.findByText('gpt-4o')
    fireEvent.click(gptOption)

    expect(onModelChange).toHaveBeenCalledWith(MOCK_MODELS[2])
  })

  it('shows provider name alongside model name', async () => {
    render(<ModelSelector {...defaultProps} />)

    const trigger = screen.getByRole('button', { name: /claude-sonnet-4/i })
    openDropdown(trigger)

    // Provider labels should appear as group headers
    expect(await screen.findByText('OpenAI')).toBeInTheDocument()
    expect(screen.getByText('Google')).toBeInTheDocument()
    // Anthropic appears both on trigger badge and as group label
    const anthropicElements = screen.getAllByText('Anthropic')
    expect(anthropicElements.length).toBeGreaterThanOrEqual(2)
  })

  it('is disabled when disabled prop is true', () => {
    render(<ModelSelector {...defaultProps} disabled={true} />)
    const trigger = screen.getByRole('button', { name: /claude-sonnet-4/i })
    expect(trigger).toBeDisabled()
  })

  it('shows provider badge on the trigger', () => {
    render(<ModelSelector {...defaultProps} />)
    expect(screen.getByText('Anthropic')).toBeInTheDocument()
  })
})
