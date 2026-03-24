import React, { useEffect, useState } from 'react'
import GitDiff from './GitDiff'
import { Label } from './ui/label'
import { Textarea } from './ui/textarea'

export default function ApprovalPanel({ request, onFeedbackChange }) {
  const [feedback, setFeedback] = useState('')

  useEffect(() => {
    setFeedback('')
  }, [request?.id])

  useEffect(() => {
    onFeedbackChange?.(feedback)
  }, [feedback, onFeedbackChange])

  if (!request) return null

  return (
    <>
      <div className="approval-feedback">
        <Label htmlFor="approval-feedback-input">Feedback (optional)</Label>
        <Textarea
          id="approval-feedback-input"
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="Tell Claude what to adjust before approving."
          rows={2}
        />
      </div>
      <div className="approval-diff">
        <GitDiff diff={request.diff} showFileHeader={false} />
      </div>
    </>
  )
}
