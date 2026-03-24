import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import CreateWorkspaceModal from '../../pages/CreateWorkspaceModal'

describe('CreateWorkspaceModal', () => {
  it('renders dialog shell and autofocuses the workspace name input', async () => {
    render(<CreateWorkspaceModal onClose={vi.fn()} onCreate={vi.fn()} />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Create Workspace')).toBeInTheDocument()
    const input = screen.getByLabelText('Workspace Name')

    await waitFor(() => {
      expect(input).toHaveFocus()
    })
  })

  it('submits trimmed workspace name', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(<CreateWorkspaceModal onClose={vi.fn()} onCreate={onCreate} />)

    const input = screen.getByLabelText('Workspace Name')
    fireEvent.change(input, { target: { value: '  New Workspace  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith('New Workspace')
    })
  })

  it('invokes onClose from cancel and escape interactions', async () => {
    const onClose = vi.fn()
    render(<CreateWorkspaceModal onClose={onClose} onCreate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled()
    })
  })
})
