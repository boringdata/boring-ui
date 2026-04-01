import React, { useCallback, useRef, useState } from 'react'
import { Paperclip, X } from 'lucide-react'

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

/**
 * Format bytes into human-readable size string.
 */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * FileAttachment - Paperclip button + drag-and-drop + file preview chips.
 *
 * Props:
 *   files    - File[] array of currently attached files
 *   onAttach - (file: File) => void, called per file when attached
 *   onRemove - (index: number) => void, called when a file chip is dismissed
 */
export default function FileAttachment({ files = [], onAttach, onRemove }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState(null)

  const validateAndAttach = useCallback(
    (file) => {
      setError(null)
      if (file.size > MAX_FILE_SIZE) {
        setError(`"${file.name}" exceeds 10MB limit`)
        return
      }
      onAttach(file)
    },
    [onAttach]
  )

  const handleInputChange = useCallback(
    (e) => {
      const selected = e.target.files
      if (!selected) return
      for (const file of selected) {
        validateAndAttach(file)
      }
      // Reset input so re-selecting the same file works
      e.target.value = ''
    },
    [validateAndAttach]
  )

  const handleButtonClick = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const handleDragEnter = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }, [])

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      e.stopPropagation()
      setDragOver(false)
      const dropped = e.dataTransfer?.files
      if (!dropped) return
      for (const file of dropped) {
        validateAndAttach(file)
      }
    },
    [validateAndAttach]
  )

  return (
    <div className="vc-file-attachment">
      <div
        className={`vc-file-drop-zone ${dragOver ? 'vc-file-drop-active' : ''}`}
        data-testid="file-drop-zone"
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <button
          className="vc-file-attach-btn"
          data-testid="file-attach-btn"
          onClick={handleButtonClick}
          type="button"
          title="Attach file"
        >
          <Paperclip size={16} />
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="vc-file-input-hidden"
          style={{ display: 'none' }}
          onChange={handleInputChange}
          accept="image/*,.pdf,.docx,.xlsx,.pptx,.txt,.md,.js,.jsx,.ts,.tsx,.py,.go,.rs,.json,.yaml,.yml,.toml,.css,.html"
        />
        {dragOver && (
          <div className="vc-file-drop-indicator" data-testid="file-drop-indicator">
            Drop files here
          </div>
        )}
      </div>

      {error && (
        <div className="vc-file-error" role="alert">
          {error}
        </div>
      )}

      {files.length > 0 && (
        <div className="vc-file-previews">
          {files.map((file, idx) => (
            <div key={`${file.name}-${idx}`} className="vc-file-chip">
              <span className="vc-file-chip-name">{file.name}</span>
              <span className="vc-file-chip-size">{formatSize(file.size)}</span>
              <button
                className="vc-file-chip-remove"
                data-testid={`file-remove-${idx}`}
                onClick={() => onRemove(idx)}
                type="button"
                title="Remove file"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
