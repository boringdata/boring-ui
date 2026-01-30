import { useState, useCallback, useEffect, useRef } from 'react'

/**
 * useVoiceRecognition - React hook for Web Speech API recognition
 *
 * Provides speech-to-text functionality with:
 * - Real-time transcription
 * - Confidence scores
 * - Multiple language support
 * - Graceful degradation
 * - Error handling
 *
 * @param {Object} options - Configuration options
 * @param {string} [options.language='en-US'] - Language code
 * @param {boolean} [options.continuous=false] - Continue listening after silence
 * @param {number} [options.interimResults=true] - Show interim results
 * @param {Function} [options.onResult] - Callback for results
 * @param {Function} [options.onError] - Callback for errors
 * @returns {Object} Voice recognition state and controls
 *
 * @example
 * ```jsx
 * const {
 *   isListening,
 *   transcript,
 *   confidence,
 *   startListening,
 *   stopListening,
 *   resetTranscript,
 *   isSupported,
 *   error
 * } = useVoiceRecognition()
 * ```
 */
export function useVoiceRecognition(options = {}) {
  const {
    language = 'en-US',
    continuous = false,
    interimResults = true,
    onResult,
    onError,
  } = options

  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [confidence, setConfidence] = useState(0)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState(null)
  const [isSupported, setIsSupported] = useState(false)
  const recognitionRef = useRef(null)

  // Initialize speech recognition
  useEffect(() => {
    if (typeof window === 'undefined') return

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      setIsSupported(false)
      return
    }

    setIsSupported(true)
    recognitionRef.current = new SpeechRecognition()
    const recognition = recognitionRef.current

    // Configure recognition
    recognition.continuous = continuous
    recognition.interimResults = interimResults
    recognition.language = language

    // Handle results
    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      let finalConfidence = 0

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        const confidence = event.results[i][0].confidence

        if (event.results[i].isFinal) {
          final += transcript
          finalConfidence = confidence
        } else {
          interim += transcript
        }
      }

      setInterimTranscript(interim)
      if (final) {
        setTranscript((prev) => prev + final)
        setConfidence(finalConfidence)
      }

      onResult?.({
        transcript: final,
        interim,
        confidence: finalConfidence,
        isFinal: final.length > 0,
      })
    }

    // Handle errors
    recognition.onerror = (event) => {
      const errorMessage = `Speech recognition error: ${event.error}`
      setError(errorMessage)
      onError?.(event.error)
    }

    // Handle start
    recognition.onstart = () => {
      setIsListening(true)
      setError(null)
    }

    // Handle end
    recognition.onend = () => {
      setIsListening(false)
      setInterimTranscript('')
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
    }
  }, [language, continuous, interimResults, onResult, onError])

  const startListening = useCallback(() => {
    if (!recognitionRef.current || !isSupported) return

    try {
      recognitionRef.current.start()
    } catch (err) {
      setError(`Failed to start listening: ${err.message}`)
    }
  }, [isSupported])

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) return

    try {
      recognitionRef.current.stop()
    } catch (err) {
      setError(`Failed to stop listening: ${err.message}`)
    }
  }, [])

  const resetTranscript = useCallback(() => {
    setTranscript('')
    setInterimTranscript('')
    setConfidence(0)
    setError(null)
  }, [])

  const setLanguage = useCallback((newLanguage) => {
    if (recognitionRef.current) {
      recognitionRef.current.language = newLanguage
    }
  }, [])

  return {
    isListening,
    transcript,
    interimTranscript,
    confidence,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
    setLanguage,
  }
}

export default useVoiceRecognition
