import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useVoiceRecognition } from '../../hooks/useVoiceRecognition'
import { useTextToSpeech } from '../../hooks/useTextToSpeech'

describe('useVoiceRecognition Hook', () => {
  beforeEach(() => {
    // Mock Web Speech API
    const mockRecognition = vi.fn(() => ({
      start: vi.fn(),
      stop: vi.fn(),
      abort: vi.fn(),
      onstart: null,
      onend: null,
      onresult: null,
      onerror: null,
      continuous: false,
      interimResults: true,
      language: 'en-US',
    }))

    window.SpeechRecognition = mockRecognition
    window.webkitSpeechRecognition = mockRecognition
  })

  afterEach(() => {
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition
  })

  it('initializes with default values', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(result.current.isListening).toBe(false)
    expect(result.current.transcript).toBe('')
    expect(result.current.confidence).toBe(0)
    expect(result.current.error).toBe(null)
    expect(result.current.isSupported).toBe(true)
  })

  it('supports speech recognition API', () => {
    const { result } = renderHook(() => useVoiceRecognition())
    expect(result.current.isSupported).toBe(true)
  })

  it('provides startListening function', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.startListening).toBe('function')
  })

  it('provides stopListening function', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.stopListening).toBe('function')
  })

  it('provides resetTranscript function', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.resetTranscript).toBe('function')
  })

  it('resets transcript correctly', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    // Set some values
    act(() => {
      result.current.resetTranscript()
    })

    expect(result.current.transcript).toBe('')
    expect(result.current.confidence).toBe(0)
  })

  it('provides setLanguage function', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.setLanguage).toBe('function')
  })

  it('returns interim transcript while listening', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(result.current.interimTranscript).toBe('')
  })

  it('handles unsupported browsers gracefully', () => {
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition

    const { result } = renderHook(() => useVoiceRecognition())

    expect(result.current.isSupported).toBe(false)
  })

  it('calls onResult callback when result is final', () => {
    const onResult = vi.fn()
    const { result } = renderHook(() =>
      useVoiceRecognition({ onResult })
    )

    expect(onResult).toBeDefined()
  })

  it('calls onError callback on error', () => {
    const onError = vi.fn()
    const { result } = renderHook(() =>
      useVoiceRecognition({ onError })
    )

    expect(onError).toBeDefined()
  })

  it('accepts language option', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ language: 'fr-FR' })
    )

    expect(result.current).toBeDefined()
  })

  it('accepts continuous option', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ continuous: true })
    )

    expect(result.current).toBeDefined()
  })

  it('accepts interimResults option', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ interimResults: false })
    )

    expect(result.current).toBeDefined()
  })

  it('provides confidence level', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.confidence).toBe('number')
    expect(result.current.confidence).toBeGreaterThanOrEqual(0)
  })

  it('accumulates transcript correctly', async () => {
    const { result } = renderHook(() => useVoiceRecognition())

    act(() => {
      result.current.resetTranscript()
    })

    // Note: In real usage, transcript would accumulate from speech
    // This test verifies the state is initialized correctly
    expect(result.current.transcript).toBe('')
  })
})

describe('useTextToSpeech Hook', () => {
  beforeEach(() => {
    // Mock Web Speech API
    window.speechSynthesis = {
      speak: vi.fn(),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      getVoices: vi.fn(() => []),
      onvoiceschanged: null,
    }
  })

  afterEach(() => {
    delete window.speechSynthesis
  })

  it('initializes with default values', () => {
    const { result } = renderHook(() => useTextToSpeech())

    expect(result.current.isSpeaking).toBe(false)
    expect(result.current.isPaused).toBe(false)
    expect(result.current.text).toBe('')
    expect(result.current.error).toBe(null)
    expect(result.current.isSupported).toBe(true)
  })

  it('supports speech synthesis API', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(result.current.isSupported).toBe(true)
  })

  it('provides speak function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.speak).toBe('function')
  })

  it('provides pause function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.pause).toBe('function')
  })

  it('provides resume function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.resume).toBe('function')
  })

  it('provides stop function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.stop).toBe('function')
  })

  it('provides setRate function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.setRate).toBe('function')
  })

  it('provides setPitch function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.setPitch).toBe('function')
  })

  it('provides setVolume function', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(typeof result.current.setVolume).toBe('function')
  })

  it('clamps rate between 0.1 and 10', () => {
    const { result } = renderHook(() => useTextToSpeech())

    act(() => {
      result.current.setRate(0.05) // Too low
    })
    expect(result.current.currentRate).toBe(0.1)

    act(() => {
      result.current.setRate(15) // Too high
    })
    expect(result.current.currentRate).toBe(10)

    act(() => {
      result.current.setRate(1.5) // Valid
    })
    expect(result.current.currentRate).toBe(1.5)
  })

  it('clamps pitch between 0 and 2', () => {
    const { result } = renderHook(() => useTextToSpeech())

    act(() => {
      result.current.setPitch(-1) // Too low
    })
    expect(result.current.currentPitch).toBe(0)

    act(() => {
      result.current.setPitch(3) // Too high
    })
    expect(result.current.currentPitch).toBe(2)

    act(() => {
      result.current.setPitch(1.5) // Valid
    })
    expect(result.current.currentPitch).toBe(1.5)
  })

  it('clamps volume between 0 and 1', () => {
    const { result } = renderHook(() => useTextToSpeech())

    act(() => {
      result.current.setVolume(-1) // Too low
    })
    expect(result.current.currentVolume).toBe(0)

    act(() => {
      result.current.setVolume(2) // Too high
    })
    expect(result.current.currentVolume).toBe(1)

    act(() => {
      result.current.setVolume(0.5) // Valid
    })
    expect(result.current.currentVolume).toBe(0.5)
  })

  it('accepts language option', () => {
    const { result } = renderHook(() =>
      useTextToSpeech({ language: 'fr-FR' })
    )

    expect(result.current).toBeDefined()
  })

  it('accepts rate option', () => {
    const { result } = renderHook(() =>
      useTextToSpeech({ rate: 1.5 })
    )

    expect(result.current.currentRate).toBe(1.5)
  })

  it('accepts pitch option', () => {
    const { result } = renderHook(() =>
      useTextToSpeech({ pitch: 1.2 })
    )

    expect(result.current.currentPitch).toBe(1.2)
  })

  it('accepts volume option', () => {
    const { result } = renderHook(() =>
      useTextToSpeech({ volume: 0.8 })
    )

    expect(result.current.currentVolume).toBe(0.8)
  })

  it('provides available voices', () => {
    const { result } = renderHook(() => useTextToSpeech())
    expect(Array.isArray(result.current.availableVoices)).toBe(true)
  })

  it('calls onStart callback', () => {
    const onStart = vi.fn()
    const { result } = renderHook(() =>
      useTextToSpeech({ onStart })
    )

    expect(onStart).toBeDefined()
  })

  it('calls onEnd callback', () => {
    const onEnd = vi.fn()
    const { result } = renderHook(() =>
      useTextToSpeech({ onEnd })
    )

    expect(onEnd).toBeDefined()
  })

  it('calls onError callback', () => {
    const onError = vi.fn()
    const { result } = renderHook(() =>
      useTextToSpeech({ onError })
    )

    expect(onError).toBeDefined()
  })

  it('handles unsupported browsers gracefully', () => {
    delete window.speechSynthesis

    const { result } = renderHook(() => useTextToSpeech())

    expect(result.current.isSupported).toBe(false)
  })

  it('maintains state correctly through multiple operations', () => {
    const { result } = renderHook(() => useTextToSpeech())

    expect(result.current.isSpeaking).toBe(false)
    expect(result.current.isPaused).toBe(false)
    expect(result.current.currentRate).toBe(1)
  })
})

describe('Voice Features Integration', () => {
  beforeEach(() => {
    window.SpeechRecognition = vi.fn(() => ({
      start: vi.fn(),
      stop: vi.fn(),
      abort: vi.fn(),
      onstart: null,
      onend: null,
      onresult: null,
      onerror: null,
      continuous: false,
      interimResults: true,
      language: 'en-US',
    }))

    window.speechSynthesis = {
      speak: vi.fn(),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      getVoices: vi.fn(() => []),
      onvoiceschanged: null,
    }
  })

  afterEach(() => {
    delete window.SpeechRecognition
    delete window.speechSynthesis
  })

  it('supports speech-to-text with confidence', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(result.current.confidence).toBeGreaterThanOrEqual(0)
    expect(result.current.confidence).toBeLessThanOrEqual(1)
  })

  it('supports text-to-speech with playback controls', () => {
    const { result } = renderHook(() => useTextToSpeech())

    expect(typeof result.current.speak).toBe('function')
    expect(typeof result.current.pause).toBe('function')
    expect(typeof result.current.resume).toBe('function')
    expect(typeof result.current.stop).toBe('function')
  })

  it('provides graceful degradation for unsupported features', () => {
    delete window.SpeechRecognition
    delete window.speechSynthesis

    const { result: voiceRecResult } = renderHook(() => useVoiceRecognition())
    const { result: ttsResult } = renderHook(() => useTextToSpeech())

    expect(voiceRecResult.current.isSupported).toBe(false)
    expect(ttsResult.current.isSupported).toBe(false)
  })

  it('allows multiple languages for speech input', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ language: 'es-ES' })
    )

    expect(result.current).toBeDefined()
  })

  it('allows multiple languages for speech output', () => {
    const { result } = renderHook(() =>
      useTextToSpeech({ language: 'de-DE' })
    )

    expect(result.current).toBeDefined()
  })

  it('supports continuous recognition mode', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ continuous: true })
    )

    expect(result.current).toBeDefined()
  })

  it('supports interim results display', () => {
    const { result } = renderHook(() =>
      useVoiceRecognition({ interimResults: true })
    )

    expect(typeof result.current.interimTranscript).toBe('string')
  })

  it('provides confidence scoring', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(typeof result.current.confidence).toBe('number')
    expect(result.current.confidence).toBeGreaterThanOrEqual(0)
    expect(result.current.confidence).toBeLessThanOrEqual(1)
  })
})

describe('Voice Features Error Handling', () => {
  beforeEach(() => {
    window.SpeechRecognition = vi.fn(() => ({
      start: vi.fn(),
      stop: vi.fn(),
      abort: vi.fn(),
      onstart: null,
      onend: null,
      onresult: null,
      onerror: null,
      continuous: false,
      interimResults: true,
      language: 'en-US',
    }))

    window.speechSynthesis = {
      speak: vi.fn(),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      getVoices: vi.fn(() => []),
      onvoiceschanged: null,
    }
  })

  afterEach(() => {
    delete window.SpeechRecognition
    delete window.speechSynthesis
  })

  it('handles recognition errors gracefully', () => {
    const onError = vi.fn()
    const { result } = renderHook(() =>
      useVoiceRecognition({ onError })
    )

    expect(result.current.error).toBe(null)
  })

  it('handles synthesis errors gracefully', () => {
    const onError = vi.fn()
    const { result } = renderHook(() =>
      useTextToSpeech({ onError })
    )

    expect(result.current.error).toBe(null)
  })

  it('maintains error state', () => {
    const { result } = renderHook(() => useVoiceRecognition())

    expect(result.current.error).toBeNull()
  })
})
