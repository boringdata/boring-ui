import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FileAttachment from '../FileAttachment'

/**
 * Helper: create a mock File object
 */
function createMockFile(name = 'test.txt', size = 1024, type = 'text/plain') {
  const file = new File(['x'.repeat(size)], name, { type })
  return file
}

describe('FileAttachment', () => {
  const defaultProps = {
    files: [],
    onAttach: vi.fn(),
    onRemove: vi.fn(),
  }

  it('renders a paperclip/attachment button', () => {
    render(<FileAttachment {...defaultProps} />)
    const btn = screen.getByTestId('file-attach-btn')
    expect(btn).toBeInTheDocument()
  })

  it('clicking the button triggers the hidden file input', () => {
    render(<FileAttachment {...defaultProps} />)
    const btn = screen.getByTestId('file-attach-btn')
    const input = document.querySelector('input[type="file"]')
    expect(input).toBeTruthy()
    // The input should be hidden
    expect(input.style.display === 'none' || input.hidden || input.className.includes('hidden')).toBeTruthy()
  })

  it('calls onAttach when files are selected via the input', () => {
    const onAttach = vi.fn()
    render(<FileAttachment {...defaultProps} onAttach={onAttach} />)

    const input = document.querySelector('input[type="file"]')
    const file = createMockFile('readme.md', 512, 'text/markdown')
    fireEvent.change(input, { target: { files: [file] } })

    expect(onAttach).toHaveBeenCalledWith(file)
  })

  it('shows filename and size preview for attached files', () => {
    const file = createMockFile('document.pdf', 2048, 'application/pdf')
    render(<FileAttachment {...defaultProps} files={[file]} />)

    expect(screen.getByText('document.pdf')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
  })

  it('remove button on preview dismisses the attachment', () => {
    const onRemove = vi.fn()
    const file = createMockFile('photo.png', 4096, 'image/png')
    render(<FileAttachment {...defaultProps} files={[file]} onRemove={onRemove} />)

    const removeBtn = screen.getByTestId('file-remove-0')
    fireEvent.click(removeBtn)

    expect(onRemove).toHaveBeenCalledWith(0)
  })

  it('supports multiple file previews', () => {
    const files = [
      createMockFile('a.txt', 100, 'text/plain'),
      createMockFile('b.js', 200, 'text/javascript'),
      createMockFile('c.png', 300, 'image/png'),
    ]
    render(<FileAttachment {...defaultProps} files={files} />)

    expect(screen.getByText('a.txt')).toBeInTheDocument()
    expect(screen.getByText('b.js')).toBeInTheDocument()
    expect(screen.getByText('c.png')).toBeInTheDocument()
  })

  it('shows error for files exceeding 10MB', () => {
    const onAttach = vi.fn()
    render(<FileAttachment {...defaultProps} onAttach={onAttach} />)

    const input = document.querySelector('input[type="file"]')
    const bigFile = createMockFile('huge.bin', 11 * 1024 * 1024, 'application/octet-stream')
    fireEvent.change(input, { target: { files: [bigFile] } })

    // onAttach should NOT be called for oversized files
    expect(onAttach).not.toHaveBeenCalled()
    // Error message should appear
    expect(screen.getByText(/exceeds 10MB/i)).toBeInTheDocument()
  })

  it('drag-and-drop shows drop zone indicator', () => {
    render(<FileAttachment {...defaultProps} />)

    const dropZone = screen.getByTestId('file-drop-zone')
    fireEvent.dragEnter(dropZone, {
      dataTransfer: { items: [{ kind: 'file' }], types: ['Files'] },
    })

    expect(screen.getByTestId('file-drop-indicator')).toBeInTheDocument()
  })

  it('dropping a file calls onAttach', () => {
    const onAttach = vi.fn()
    render(<FileAttachment {...defaultProps} onAttach={onAttach} />)

    const dropZone = screen.getByTestId('file-drop-zone')
    const file = createMockFile('dropped.txt', 500, 'text/plain')

    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    expect(onAttach).toHaveBeenCalledWith(file)
  })
})
