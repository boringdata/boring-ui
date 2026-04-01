import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import EnhancedComposer from '../components/EnhancedComposer'

// Polyfill PointerEvent for Radix DropdownMenu
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
  { id: 'claude-sonnet-4-20250514', name: 'claude-sonnet-4', provider: 'Anthropic' },
  { id: 'gpt-4o', name: 'gpt-4o', provider: 'OpenAI' },
]

describe('EnhancedComposer', () => {
  const defaultProps = {
    value: '',
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onStop: vi.fn(),
    status: 'ready',
    disabled: false,
    currentModel: MOCK_MODELS[0],
    models: MOCK_MODELS,
    onModelChange: vi.fn(),
    files: [],
    onFileAttach: vi.fn(),
    onFileRemove: vi.fn(),
  }

  it('renders the chat composer textarea', () => {
    render(<EnhancedComposer {...defaultProps} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders the model selector trigger', () => {
    render(<EnhancedComposer {...defaultProps} />)
    expect(screen.getByText('claude-sonnet-4')).toBeInTheDocument()
  })

  it('renders the file attachment button', () => {
    render(<EnhancedComposer {...defaultProps} />)
    expect(screen.getByTestId('file-attach-btn')).toBeInTheDocument()
  })

  it('shows file previews when files are attached', () => {
    const file = new File(['data'], 'test.txt', { type: 'text/plain' })
    render(<EnhancedComposer {...defaultProps} files={[file]} />)
    expect(screen.getByText('test.txt')).toBeInTheDocument()
  })

  it('passes onSubmit through to ChatComposer', () => {
    const onSubmit = vi.fn()
    render(<EnhancedComposer {...defaultProps} value="Hello" onSubmit={onSubmit} />)

    const input = screen.getByRole('textbox')
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
    expect(onSubmit).toHaveBeenCalled()
  })

  it('disables model selector when streaming', () => {
    render(<EnhancedComposer {...defaultProps} status="streaming" />)
    const modelTrigger = screen.getByText('claude-sonnet-4').closest('button')
    expect(modelTrigger).toBeDisabled()
  })

  it('passes files through to FileAttachment', () => {
    const files = [
      new File(['a'], 'a.txt', { type: 'text/plain' }),
      new File(['b'], 'b.txt', { type: 'text/plain' }),
    ]
    render(<EnhancedComposer {...defaultProps} files={files} />)
    expect(screen.getByText('a.txt')).toBeInTheDocument()
    expect(screen.getByText('b.txt')).toBeInTheDocument()
  })
})
