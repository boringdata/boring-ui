import { useState, useRef } from 'react'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'

export default function CreateWorkspaceModal({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return

    if (trimmed.length > 100) {
      setError('Name must be 100 characters or fewer')
      return
    }

    setCreating(true)
    setError('')
    try {
      await onCreate(trimmed)
    } catch (err) {
      setError(err?.message || 'Failed to create workspace')
      setCreating(false)
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        className="modal-dialog create-workspace-dialog"
        aria-describedby={undefined}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          inputRef.current?.focus()
        }}
      >
        <DialogHeader className="modal-header">
          <DialogTitle className="modal-title">Create Workspace</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <Label className="settings-field-label" htmlFor="workspace-name">
              Workspace Name
            </Label>
            <Input
              id="workspace-name"
              ref={inputRef}
              type="text"
              className="settings-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Workspace"
              disabled={creating}
              autoComplete="off"
            />
            {error && <div className="modal-error">{error}</div>}
          </div>
          <DialogFooter className="modal-footer">
            <Button
              type="button"
              variant="secondary"
              className="settings-btn settings-btn-secondary"
              onClick={onClose}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              className="settings-btn settings-btn-primary"
              disabled={creating || !name.trim()}
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
