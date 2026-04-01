import React from 'react'
import ChatComposer from './ChatComposer'
import ModelSelector from './ModelSelector'
import FileAttachment from './FileAttachment'

/**
 * EnhancedComposer - Composes ChatComposer + ModelSelector + FileAttachment.
 *
 * Layout:
 *   [model selector] [  composer input  ] [attach] [send/stop]
 *   [           file preview chips              ]
 *
 * Props (ChatComposer):
 *   value, onChange, onSubmit, onStop, status, disabled
 *
 * Props (ModelSelector):
 *   currentModel, models, onModelChange
 *
 * Props (FileAttachment):
 *   files, onFileAttach, onFileRemove
 */
export default function EnhancedComposer({
  // ChatComposer props
  value,
  onChange,
  onSubmit,
  onStop,
  status,
  disabled,
  // ModelSelector props
  currentModel,
  models,
  onModelChange,
  // FileAttachment props
  files = [],
  onFileAttach,
  onFileRemove,
}) {
  const isStreaming = status === 'streaming'

  return (
    <div className="vc-enhanced-composer">
      <div className="vc-enhanced-composer-toolbar">
        <ModelSelector
          currentModel={currentModel}
          models={models}
          onModelChange={onModelChange}
          disabled={isStreaming || disabled}
        />
      </div>

      {files.length > 0 && (
        <FileAttachment
          files={files}
          onAttach={onFileAttach}
          onRemove={onFileRemove}
        />
      )}

      <div className="vc-enhanced-composer-row">
        <ChatComposer
          value={value}
          onChange={onChange}
          onSubmit={onSubmit}
          onStop={onStop}
          status={status}
          disabled={disabled}
        />
        <FileAttachment
          files={[]}
          onAttach={onFileAttach}
          onRemove={onFileRemove}
        />
      </div>
    </div>
  )
}
