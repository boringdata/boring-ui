import { useState, useEffect } from 'react'
import { useTextToSpeech } from '../../hooks/useTextToSpeech'

/**
 * VoiceOutput - Audio playback component for text-to-speech
 *
 * Features:
 * - Play, pause, resume, and stop controls
 * - Rate, pitch, and volume adjustment
 * - Language selection
 * - Graceful degradation
 * - Real-time playback status
 *
 * @param {Object} props
 * @param {string} props.text - Text to speak
 * @param {string} [props.language='en-US'] - Language code
 * @param {Function} [props.onStart] - Callback when speech starts
 * @param {Function} [props.onEnd] - Callback when speech ends
 * @param {Function} [props.onError] - Callback for errors
 * @param {boolean} [props.autoPlay=false] - Auto-play on mount
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * <VoiceOutput
 *   text="Hello, this is spoken text"
 *   language="en-US"
 *   onStart={() => console.log('Started speaking')}
 *   onEnd={() => console.log('Finished speaking')}
 * />
 * ```
 */
export function VoiceOutput({
  text,
  language = 'en-US',
  onStart,
  onEnd,
  onError,
  autoPlay = false,
}) {
  const {
    isSpeaking,
    isPaused,
    error,
    isSupported,
    currentRate,
    currentPitch,
    currentVolume,
    speak,
    pause,
    resume,
    stop,
    setRate,
    setPitch,
    setVolume,
  } = useTextToSpeech({
    language,
    onStart,
    onEnd,
    onError,
  })

  const [showControls, setShowControls] = useState(false)
  const [displayText, setDisplayText] = useState(text)

  // Auto-play on mount if enabled
  useEffect(() => {
    if (autoPlay && text && isSupported) {
      speak(text)
    }
  }, [autoPlay, text, isSupported, speak])

  // Update display text when prop changes
  useEffect(() => {
    setDisplayText(text)
  }, [text])

  if (!isSupported) {
    return (
      <div
        className="voice-output-unsupported"
        style={{
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--color-info-light)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-text-primary)',
          fontSize: 'var(--text-sm)',
        }}
      >
        Text-to-speech is not supported in your browser.
        <br />
        Please use Chrome, Edge, or Safari for voice output.
      </div>
    )
  }

  return (
    <div
      className="voice-output-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
        padding: 'var(--space-3)',
        backgroundColor: 'var(--color-bg-secondary)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      {/* Playback Controls */}
      <div
        className="voice-output-controls"
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        {/* Play/Pause Button */}
        {!isSpeaking ? (
          <button
            className="play-button"
            onClick={() => speak(displayText)}
            aria-label="Play audio"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '48px',
              height: '48px',
              minWidth: '48px',
              minHeight: '48px',
              borderRadius: '50%',
              border: '2px solid var(--color-border)',
              backgroundColor: 'var(--color-bg-primary)',
              cursor: 'pointer',
              transition: 'all 150ms ease',
              color: 'var(--color-text-primary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-accent)'
              e.currentTarget.style.borderColor = 'var(--color-accent)'
              e.currentTarget.style.color = 'white'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-primary)'
              e.currentTarget.style.borderColor = 'var(--color-border)'
              e.currentTarget.style.color = 'var(--color-text-primary)'
            }}
          >
            <PlayIcon />
          </button>
        ) : (
          <>
            <button
              className="pause-button"
              onClick={pause}
              aria-label="Pause audio"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '48px',
                height: '48px',
                minWidth: '48px',
                minHeight: '48px',
                borderRadius: '50%',
                border: '2px solid var(--color-accent)',
                backgroundColor: 'var(--color-accent)',
                cursor: 'pointer',
                transition: 'all 150ms ease',
                color: 'white',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-accent-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-accent)'
              }}
            >
              {isPaused ? <ResumeIcon /> : <PauseIcon />}
            </button>

            <button
              className="stop-button"
              onClick={stop}
              aria-label="Stop audio"
              style={{
                padding: 'var(--space-2) var(--space-3)',
                minWidth: '44px',
                minHeight: '44px',
                backgroundColor: 'var(--color-error-light)',
                border: '1px solid var(--color-error)',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                color: 'var(--color-error)',
                fontWeight: 'var(--font-medium)',
                fontSize: 'var(--text-sm)',
                transition: 'all 150ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-error)'
                e.currentTarget.style.color = 'white'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-error-light)'
                e.currentTarget.style.color = 'var(--color-error)'
              }}
            >
              Stop
            </button>
          </>
        )}

        {/* Settings Toggle */}
        <button
          className="settings-toggle"
          onClick={() => setShowControls(!showControls)}
          aria-label="Toggle playback settings"
          aria-expanded={showControls}
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
          ⚙️
        </button>

        {/* Status */}
        <div
          className="voice-status"
          style={{
            flex: 1,
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-secondary)',
            minWidth: '150px',
          }}
        >
          {isSpeaking && (
            <>
              <span style={{ color: 'var(--color-accent)', fontWeight: 'var(--font-medium)' }}>
                ● Speaking...
              </span>
            </>
          )}
          {!isSpeaking && (
            <span>Ready to play</span>
          )}
        </div>
      </div>

      {/* Settings Controls */}
      {showControls && (
        <div
          className="voice-settings"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-3)',
            padding: 'var(--space-3)',
            backgroundColor: 'var(--color-bg-primary)',
            borderRadius: 'var(--radius-md)',
            borderTop: '1px solid var(--color-border)',
          }}
        >
          {/* Rate Slider */}
          <div className="setting-group">
            <label
              htmlFor="rate-slider"
              style={{
                display: 'block',
                marginBottom: 'var(--space-2)',
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--font-medium)',
              }}
            >
              Speed: {currentRate.toFixed(1)}x
            </label>
            <input
              id="rate-slider"
              type="range"
              min="0.5"
              max="2"
              step="0.1"
              value={currentRate}
              onChange={(e) => setRate(parseFloat(e.target.value))}
              style={{
                width: '100%',
              }}
            />
          </div>

          {/* Pitch Slider */}
          <div className="setting-group">
            <label
              htmlFor="pitch-slider"
              style={{
                display: 'block',
                marginBottom: 'var(--space-2)',
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--font-medium)',
              }}
            >
              Pitch: {currentPitch.toFixed(1)}x
            </label>
            <input
              id="pitch-slider"
              type="range"
              min="0.5"
              max="2"
              step="0.1"
              value={currentPitch}
              onChange={(e) => setPitch(parseFloat(e.target.value))}
              style={{
                width: '100%',
              }}
            />
          </div>

          {/* Volume Slider */}
          <div className="setting-group">
            <label
              htmlFor="volume-slider"
              style={{
                display: 'block',
                marginBottom: 'var(--space-2)',
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--font-medium)',
              }}
            >
              Volume: {Math.round(currentVolume * 100)}%
            </label>
            <input
              id="volume-slider"
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={currentVolume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              style={{
                width: '100%',
              }}
            />
          </div>
        </div>
      )}

      {/* Text Preview */}
      {displayText && (
        <div
          className="voice-text-preview"
          style={{
            padding: 'var(--space-2) var(--space-3)',
            backgroundColor: 'var(--color-bg-tertiary)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            lineHeight: 'var(--leading-relaxed)',
            color: 'var(--color-text-primary)',
            maxHeight: '120px',
            overflowY: 'auto',
          }}
        >
          {displayText}
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
    </div>
  )
}

/**
 * SVG Icons for voice controls
 */
function PlayIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="none"
    >
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="none"
    >
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  )
}

function ResumeIcon() {
  return <PlayIcon />
}

export default VoiceOutput
