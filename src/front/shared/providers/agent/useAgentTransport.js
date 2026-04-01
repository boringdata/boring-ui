/**
 * useAgentTransport — Config-driven agent transport selection.
 *
 * Reads `config.agents.mode` to decide where the agent runs:
 *
 *   'frontend' → PiAgentCoreTransport (pi-agent-core in browser)
 *                Tools from defaultTools.js + agentConfig extensions
 *
 *   'backend'  → DefaultChatTransport (Vercel AI SDK to server)
 *                POST /api/v1/agent/chat, tools resolved server-side
 *
 * Both transports implement ChatTransport, consumed by useChat().
 *
 * @module providers/agent/useAgentTransport
 */

import { useMemo, useRef, useCallback, useState } from 'react'
import { DefaultChatTransport } from 'ai'
import { PiAgentCoreTransport } from '../pi/piAgentCoreTransport'
import { createPiNativeTools, mergePiTools } from '../pi/defaultTools'
import { getPiAgentConfig } from '../pi/agentConfig'
import { useDataProvider } from '../data/DataContext'
import { useQueryClient } from '@tanstack/react-query'
import { buildApiUrl } from '../../utils/apiBase'
import { getConfig, getDefaultConfig } from '../../config/appConfig'
import { getWorkspaceIdFromPathname } from '../../utils/controlPlane'
import { getEnvApiKey } from '../pi/envApiKeys.browser'

// Session-scoped API key store (in-memory, not persisted)
const sessionApiKeys = new Map()

/** Store an API key for this browser session. */
export function setSessionApiKey(provider, key) {
  if (key) {
    sessionApiKeys.set(provider, key)
  } else {
    sessionApiKeys.delete(provider)
  }
}

/** Resolve API key: env vars first, then session store. */
function resolveApiKey(provider) {
  return getEnvApiKey(provider) || sessionApiKeys.get(provider) || ''
}

/**
 * Resolve agent mode from URL params (dev override) then config.
 *
 * URL: ?agent_mode=backend  or  ?agent_mode=frontend
 * Config: config.agents.mode
 *
 * @returns {'frontend'|'backend'}
 */
export function resolveAgentMode() {
  // Dev override via URL param
  if (typeof window !== 'undefined') {
    const param = new URLSearchParams(window.location.search).get('agent_mode')
    if (param === 'backend' || param === 'frontend') return param
  }

  const config = getConfig() || getDefaultConfig()
  const mode = String(config?.agents?.mode || 'frontend').trim().toLowerCase()
  return mode === 'backend' ? 'backend' : 'frontend'
}

/**
 * Get the current workspace ID from the URL path, if any.
 *
 * @returns {string} workspace ID or empty string
 */
function getWorkspaceId() {
  if (typeof window === 'undefined') return ''
  return getWorkspaceIdFromPathname(window.location.pathname)
}

/**
 * React hook that returns the correct ChatTransport for the configured mode.
 *
 * - Frontend mode: PiAgentCoreTransport instance is kept in a ref to
 *   preserve the Agent and its conversation state across re-renders.
 *   Tools are updated via updateTools() when the data provider changes.
 *
 * - Backend mode: DefaultChatTransport is recreated when workspaceId
 *   changes (workspace scoping requires a new transport instance).
 *
 * @returns {{ transport: ChatTransport, mode: 'frontend'|'backend' }}
 */
export function useAgentTransport() {
  const mode = resolveAgentMode()
  const dataProvider = useDataProvider()
  const queryClient = useQueryClient()
  const workspaceId = getWorkspaceId()

  // Build tools for frontend mode (browser agent)
  const tools = useMemo(() => {
    if (mode !== 'frontend') return []
    const defaultTools = createPiNativeTools(dataProvider, queryClient)
    const { tools: configuredTools } = getPiAgentConfig()
    if (configuredTools.length > 0) {
      return mergePiTools(defaultTools, configuredTools)
    }
    return defaultTools
  }, [mode, dataProvider, queryClient])

  // Stable ref for frontend transport (preserves Agent state)
  const frontendTransportRef = useRef(null)

  const transport = useMemo(() => {
    if (mode === 'backend') {
      return new DefaultChatTransport({
        api: buildApiUrl('/api/v1/agent/chat'),
        credentials: 'include',
        body: workspaceId ? { workspace_id: workspaceId } : undefined,
      })
    }

    // Frontend: reuse transport ref, update tools if changed
    if (!frontendTransportRef.current) {
      frontendTransportRef.current = new PiAgentCoreTransport({
        tools,
        getApiKey: resolveApiKey,
      })
    } else {
      frontendTransportRef.current.updateTools(tools)
    }
    return frontendTransportRef.current
  }, [mode, tools, workspaceId])

  const [thinkingLevel, setThinkingLevelState] = useState('off')
  const [selectedModel, setSelectedModelState] = useState(null)
  const [availableModels, setAvailableModels] = useState([])

  const setThinkingLevel = useCallback((level) => {
    setThinkingLevelState(level)
    if (mode === 'frontend' && frontendTransportRef.current?.setThinkingLevel) {
      frontendTransportRef.current.setThinkingLevel(level)
    }
  }, [mode])

  const setModel = useCallback((provider, modelId) => {
    const value = provider && modelId ? { provider, modelId } : null
    setSelectedModelState(value)
    if (mode === 'frontend' && frontendTransportRef.current?.setModel) {
      frontendTransportRef.current.setModel(provider, modelId)
    }
  }, [mode])

  // Load available models once for frontend mode
  useMemo(() => {
    if (mode !== 'frontend') return
    const t = frontendTransportRef.current
    if (t?.getAvailableModels) {
      t.getAvailableModels().then(setAvailableModels).catch(() => {})
    }
  }, [mode, transport])

  return {
    transport,
    mode,
    thinkingLevel,
    setThinkingLevel,
    selectedModel,
    setModel,
    availableModels,
  }
}
