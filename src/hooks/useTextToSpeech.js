import { useState, useCallback, useEffect, useRef } from 'react'

/**
 * useTextToSpeech - React hook for Web Speech API synthesis
 *
 * Provides text-to-speech functionality with:
 * - Audio playback control (play, pause, stop)
 * - Volume and rate adjustment
 * - Multiple language support
 * - Voice selection
 * - Graceful degradation
 *
 * @param {Object} options - Configuration options
 * @param {string} [options.language='en-US'] - Language code
 * @param {number} [options.rate=1] - Speech rate (0.1 - 10)
 * @param {number} [options.pitch=1] - Voice pitch (0 - 2)
 * @param {number} [options.volume=1] - Audio volume (0 - 1)
 * @param {Function} [options.onStart] - Callback when speech starts
 * @param {Function} [options.onEnd] - Callback when speech ends
 * @param {Function} [options.onError] - Callback for errors
 * @returns {Object} TTS state and controls
 *
 * @example
 * ```jsx
 * const {
 *   isSpeaking,
 *   isPaused,
 *   text,
 *   speak,
 *   pause,
 *   resume,
 *   stop,
 *   setRate,
 *   setPitch,
 *   setVolume,
 *   isSupported,
 *   error,
 *   availableVoices
 * } = useTextToSpeech()
 * ```
 */
export function useTextToSpeech(options = {}) {
  const {
    language = 'en-US',
    rate = 1,
    pitch = 1,
    volume = 1,
    onStart,
    onEnd,
    onError,
  } = options

  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [isSupported, setIsSupported] = useState(false)
  const [availableVoices, setAvailableVoices] = useState([])
  const [currentRate, setCurrentRate] = useState(rate)
  const [currentPitch, setCurrentPitch] = useState(pitch)
  const [currentVolume, setCurrentVolume] = useState(volume)
  const synthesisRef = useRef(null)
  const utteranceRef = useRef(null)

  // Initialize speech synthesis
  useEffect(() => {
    if (typeof window === 'undefined') return

    const speechSynthesis = window.speechSynthesis

    if (!speechSynthesis) {
      setIsSupported(false)
      return
    }

    setIsSupported(true)
    synthesisRef.current = speechSynthesis

    // Update available voices
    const updateVoices = () => {
      const voices = speechSynthesis.getVoices()
      setAvailableVoices(voices)
    }

    // Get voices (might be async)
    updateVoices()
    speechSynthesis.onvoiceschanged = updateVoices

    return () => {
      if (speechSynthesis) {
        speechSynthesis.cancel()
      }
    }
  }, [])

  const speak = useCallback(
    (textToSpeak) => {
      if (!synthesisRef.current || !isSupported) return

      // Cancel any ongoing speech
      synthesisRef.current.cancel()

      const utterance = new SpeechSynthesisUtterance(textToSpeak)
      utteranceRef.current = utterance

      // Configure utterance
      utterance.lang = language
      utterance.rate = currentRate
      utterance.pitch = currentPitch
      utterance.volume = currentVolume

      // Handle events
      utterance.onstart = () => {
        setIsSpeaking(true)
        setIsPaused(false)
        setText(textToSpeak)
        onStart?.()
      }

      utterance.onend = () => {
        setIsSpeaking(false)
        setIsPaused(false)
        onEnd?.()
      }

      utterance.onerror = (event) => {
        const errorMessage = `Speech synthesis error: ${event.error}`
        setError(errorMessage)
        onError?.(event.error)
      }

      utterance.onpause = () => {
        setIsPaused(true)
      }

      utterance.onresume = () => {
        setIsPaused(false)
      }

      try {
        synthesisRef.current.speak(utterance)
      } catch (err) {
        setError(`Failed to speak: ${err.message}`)
      }
    },
    [language, currentRate, currentPitch, currentVolume, isSupported, onStart, onEnd, onError]
  )

  const pause = useCallback(() => {
    if (!synthesisRef.current) return

    try {
      synthesisRef.current.pause()
    } catch (err) {
      setError(`Failed to pause: ${err.message}`)
    }
  }, [])

  const resume = useCallback(() => {
    if (!synthesisRef.current) return

    try {
      synthesisRef.current.resume()
    } catch (err) {
      setError(`Failed to resume: ${err.message}`)
    }
  }, [])

  const stop = useCallback(() => {
    if (!synthesisRef.current) return

    try {
      synthesisRef.current.cancel()
      setIsSpeaking(false)
      setIsPaused(false)
    } catch (err) {
      setError(`Failed to stop: ${err.message}`)
    }
  }, [])

  const setRate = useCallback((newRate) => {
    const clampedRate = Math.max(0.1, Math.min(10, newRate))
    setCurrentRate(clampedRate)
    if (utteranceRef.current) {
      utteranceRef.current.rate = clampedRate
    }
  }, [])

  const setPitch = useCallback((newPitch) => {
    const clampedPitch = Math.max(0, Math.min(2, newPitch))
    setCurrentPitch(clampedPitch)
    if (utteranceRef.current) {
      utteranceRef.current.pitch = clampedPitch
    }
  }, [])

  const setVolume = useCallback((newVolume) => {
    const clampedVolume = Math.max(0, Math.min(1, newVolume))
    setCurrentVolume(clampedVolume)
    if (utteranceRef.current) {
      utteranceRef.current.volume = clampedVolume
    }
  }, [])

  const setLanguage = useCallback((newLanguage) => {
    // Language will be applied to next utterance
    // For now, we just update the configuration
    if (utteranceRef.current) {
      utteranceRef.current.lang = newLanguage
    }
  }, [])

  return {
    isSpeaking,
    isPaused,
    text,
    error,
    isSupported,
    availableVoices,
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
    setLanguage,
  }
}

export default useTextToSpeech
