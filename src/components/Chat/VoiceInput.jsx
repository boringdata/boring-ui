import { useState } from 'react'
import { useVoiceRecognition } from '../../hooks/useVoiceRecognition'

/**
 * VoiceInput - Microphone input component with real-time transcription
 *
 * Features:
 * - Real-time speech-to-text transcription
 * - Confidence display
 * - Microphone visual feedback
 * - Fallback to text input
 * - Browser compatibility detection
 * - Multiple language support
 *
 * @param {Object} props
 * @param {Function} props.onTranscript - Callback when transcription is complete
 * @param {string} [props.language='en-US'] - Language code
 * @param {Function} [props.onError] - Callback for errors
 * @param {string} [props.placeholder] - Input placeholder
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * <VoiceInput
 *   onTranscript={(text) => console.log('Transcribed:', text)}
 *   language="en-US"
 * />
 * ```
 */
export function VoiceInput({
  onTranscript,
  language = 'en-US',
  onError,
  placeholder = 'Click microphone to speak...',
}) {
  const {
    isListening,
    transcript,
    interimTranscript,
    confidence,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  } = useVoiceRecognition({
    language,
    onResult: (result) => {
      if (result.isFinal) {
        onTranscript?.(result.transcript)
      }
    },
    onError: (err) => {
      onError?.(err)
    },
  })

  const [isManuallyTyping, setIsManuallyTyping] = useState(false)

  if (!isSupported) {
    return (
      <div
        className="voice-input-unsupported"
        style={{
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--color-warning-light)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-text-primary)',
          fontSize: 'var(--text-sm)',
        }}
      >
        Speech recognition is not supported in your browser.
        <br />
        Please use Chrome, Edge, or Safari for voice input.
      </div>
    )
  }

  return (
    <div
      className="voice-input-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
      }}
    >
      {/* Microphone Button */}
      <div
        className="voice-input-controls"
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'center',
        }}
      >
        <button
          className={`microphone-button ${isListening ? 'active' : ''}`}
          onClick={isListening ? stopListening : startListening}
          aria-label={isListening ? 'Stop listening' : 'Start listening'}
          aria-pressed={isListening}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            height: '48px',
            minWidth: '48px',
            minHeight: '48px',
            borderRadius: '50%',
            border: isListening ? '2px solid var(--color-error)' : '2px solid var(--color-border)',
            backgroundColor: isListening ? 'var(--color-error-light)' : 'var(--color-bg-secondary)',
            cursor: 'pointer',
            transition: 'all 150ms ease',
            color: isListening ? 'var(--color-error)' : 'var(--color-text-primary)',
          }}
          onMouseEnter={(e) => {
            if (!isListening) {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-tertiary)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isListening) {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-secondary)'
            }
          }}
        >
          <MicrophoneIcon isActive={isListening} />
        </button>

        {/* Status Text */}
        <div
          className="voice-status"
          style={{
            flex: 1,
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {isListening && (
            <>
              <span style={{ color: 'var(--color-error)', fontWeight: 'var(--font-medium)' }}>
                ● Recording...
              </span>
            </>
          )}
          {!isListening && transcript && (
            <span>Transcribed: {transcript.substring(0, 50)}...</span>
          )}
          {!isListening && !transcript && <span>Ready to listen</span>}
        </div>

        {/* Clear Button */}
        {(transcript || interimTranscript) && (
          <button
            className="clear-transcript-button"
            onClick={resetTranscript}
            aria-label="Clear transcript"
            style={{
              padding: 'var(--space-2) var(--space-3)',
              minWidth: '44px',
              minHeight: '44px',
              backgroundColor: 'transparent',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              color: 'var(--color-text-secondary)',
              transition: 'all 150ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-tertiary)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Transcription Display */}
      {(transcript || interimTranscript) && (
        <div
          className="voice-transcript"
          style={{
            padding: 'var(--space-3)',
            backgroundColor: 'var(--color-bg-tertiary)',
            borderRadius: 'var(--radius-md)',
            borderLeft: '4px solid var(--color-accent)',
            fontSize: 'var(--text-sm)',
            lineHeight: 'var(--leading-relaxed)',
          }}
        >
          {/* Final transcript */}
          {transcript && (
            <div
              className="final-transcript"
              style={{
                color: 'var(--color-text-primary)',
                fontWeight: 'var(--font-medium)',
              }}
            >
              {transcript}
            </div>
          )}

          {/* Interim transcript (while listening) */}
          {interimTranscript && (
            <div
              className="interim-transcript"
              style={{
                color: 'var(--color-text-secondary)',
                fontStyle: 'italic',
                opacity: 0.8,
                marginTop: transcript ? 'var(--space-1)' : 0,
              }}
            >
              {interimTranscript}
            </div>
          )}

          {/* Confidence display */}
          {transcript && confidence > 0 && (
            <div
              className="confidence-display"
              style={{
                marginTop: 'var(--space-2)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-secondary)',
              }}
            >
              Confidence:{' '}
              <span
                style={{
                  color:
                    confidence > 0.8
                      ? 'var(--color-success)'
                      : confidence > 0.5
                        ? 'var(--color-warning)'
                        : 'var(--color-error)',
                  fontWeight: 'var(--font-semibold)',
                }}
              >
                {Math.round(confidence * 100)}%
              </span>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div
          className="voice-error"
          role="alert"
          style={{
            padding: 'var(--space-2) var(--space-3)',
            backgroundColor: 'var(--color-error-light)',
            borderRadius: 'var(--radius-md)',
            borderLeft: '4px solid var(--color-error)',
            color: 'var(--color-error)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {error}
        </div>
      )}

      {/* Keyboard Input Fallback */}
      <div
        className="voice-input-fallback"
        style={{
          paddingTop: 'var(--space-2)',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <textarea
          placeholder={placeholder}
          value={isManuallyTyping ? undefined : transcript}
          onChange={(e) => {
            setIsManuallyTyping(true)
            onTranscript?.(e.target.value)
          }}
          onFocus={() => setIsManuallyTyping(true)}
          onBlur={() => setIsManuallyTyping(!transcript)}
          style={{
            width: '100%',
            minHeight: '80px',
            padding: 'var(--space-2) var(--space-3)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-bg-primary)',
            color: 'var(--color-text-primary)',
            fontSize: '16px', // Prevents iOS zoom
            fontFamily: 'var(--font-sans)',
            resize: 'vertical',
            appearance: 'none',
            WebkitAppearance: 'none',
          }}
          aria-label="Message text input"
          aria-describedby={error ? 'voice-error' : undefined}
        />
      </div>
    </div>
  )
}

/**
 * MicrophoneIcon - SVG microphone icon with animation
 */
function MicrophoneIcon({ isActive = false }) {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        animation: isActive ? 'pulse 1s infinite' : 'none',
      }}
    >
      <path d="M12 1a3 3 0 0 0-3 3v12a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  )
}

export default VoiceInput
