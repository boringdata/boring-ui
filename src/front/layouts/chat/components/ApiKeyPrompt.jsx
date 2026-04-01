import React, { useState, useCallback } from 'react'
import { Key, Check } from 'lucide-react'
import { setSessionApiKey } from '../../../shared/providers/agent/useAgentTransport'

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic', placeholder: 'sk-ant-...' },
  { id: 'openai', label: 'OpenAI', placeholder: 'sk-...' },
  { id: 'google', label: 'Google', placeholder: 'AIza...' },
]

/**
 * ApiKeyPrompt — Inline form shown when the agent can't start
 * because no API key is configured.
 *
 * Stores the key in session memory (not persisted) so the transport
 * can use it on the next attempt.
 *
 * Props:
 *   onKeySaved - () => void, called after a key is stored (parent can retry)
 */
export default function ApiKeyPrompt({ onKeySaved }) {
  const [provider, setProvider] = useState('anthropic')
  const [key, setKey] = useState('')
  const [saved, setSaved] = useState(false)

  const handleSave = useCallback(() => {
    const trimmed = key.trim()
    if (!trimmed) return
    setSessionApiKey(provider, trimmed)
    setSaved(true)
    setTimeout(() => {
      setSaved(false)
      setKey('')
      if (onKeySaved) onKeySaved()
    }, 600)
  }, [provider, key, onKeySaved])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSave()
    }
  }, [handleSave])

  return (
    <div className="vc-apikey-prompt" data-testid="api-key-prompt">
      <div className="vc-apikey-header">
        <Key size={16} />
        <span>Enter an API key to start</span>
      </div>
      <div className="vc-apikey-form">
        <select
          className="vc-apikey-provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <input
          className="vc-apikey-input"
          type="password"
          placeholder={PROVIDERS.find((p) => p.id === provider)?.placeholder || 'API key'}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <button
          type="button"
          className={`vc-apikey-save${saved ? ' saved' : ''}`}
          onClick={handleSave}
          disabled={!key.trim()}
        >
          {saved ? <Check size={14} /> : 'Save'}
        </button>
      </div>
      <div className="vc-apikey-note">
        Key is stored in memory only — not saved to disk.
      </div>
    </div>
  )
}
