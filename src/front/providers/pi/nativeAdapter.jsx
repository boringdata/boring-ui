import './litClassFieldFix.js' // Must precede pi-web-ui to fix Lit class field shadowing
import { useEffect, useMemo, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Agent } from '@mariozechner/pi-agent-core'
import { getModel } from '@mariozechner/pi-ai'
import { ChatPanel, defaultConvertToLlm } from '@mariozechner/pi-web-ui'
import piAppCss from '@mariozechner/pi-web-ui/app.css?raw'
import piAppCssUrl from '@mariozechner/pi-web-ui/app.css?url'
import { useDataProvider } from '../data'
import { getPiRuntime } from './runtime'
import { getPiAgentConfig } from './agentConfig'
import { createPiNativeTools, mergePiTools } from './defaultTools'
import { getAdditionalChatPanelTools } from './chatPanelTools'
import {
  publishPiSessionState,
  subscribePiSessionActions,
} from './sessionBus'

const PI_SYSTEM_PROMPT = [
  'You are an Agent integrated into Boring UI.',
  'Do not claim to be Claude Code or a terminal-native coding agent unless the user explicitly configured that mode.',
  'Be concise, accurate, and action-oriented.',
].join(' ')

const defaultModel = () => {
  return (
    getModel('anthropic', 'claude-sonnet-4-5-20250929')
    || getModel('openai', 'gpt-4o-mini')
    || getModel('google', 'gemini-2.5-flash')
    || getModel('google', 'gemini-2.5-flash-lite-preview-06-17')
    || null
  )
}

const firstUserText = (messages) => {
  const first = messages.find((m) => m.role === 'user' || m.role === 'user-with-attachments')
  if (!first) return ''

  if (typeof first.content === 'string') return first.content.trim()
  if (!Array.isArray(first.content)) return ''

  return first.content
    .filter((item) => item?.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text)
    .join(' ')
    .trim()
}

const titleFromMessages = (messages) => {
  const text = firstUserText(messages)
  if (!text) return 'New session'
  if (text.length <= 48) return text
  return `${text.slice(0, 45)}...`
}

const usageTotals = (messages) => {
  const totals = {
    input: 0,
    output: 0,
    cacheRead: 0,
    cacheWrite: 0,
    totalTokens: 0,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
  }

  for (const msg of messages) {
    if (msg.role !== 'assistant' || !msg.usage) continue
    totals.input += msg.usage.input || 0
    totals.output += msg.usage.output || 0
    totals.cacheRead += msg.usage.cacheRead || 0
    totals.cacheWrite += msg.usage.cacheWrite || 0
    totals.totalTokens += msg.usage.totalTokens || 0
    totals.cost.input += msg.usage.cost?.input || 0
    totals.cost.output += msg.usage.cost?.output || 0
    totals.cost.cacheRead += msg.usage.cost?.cacheRead || 0
    totals.cost.cacheWrite += msg.usage.cost?.cacheWrite || 0
    totals.cost.total += msg.usage.cost?.total || 0
  }

  return totals
}

const piCssBase = piAppCssUrl.replace(/[^/]+$/, '')
const piCss = piAppCss.replace(/url\((['"]?)fonts\//g, `url($1${piCssBase}fonts/`)

const scopedCss = `${piCss}\n
/* ── Layout ── */
:host, .pi-root {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.pi-root {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

pi-chat-panel {
  flex: 1;
  min-height: 0;
  width: 100%;
}

/* ── Bridge boring-ui design tokens → pi-web-ui (shadcn) tokens ── */
/* Light mode defaults — these map our app's palette into the library's variable namespace */
:host {
  --background: #ffffff;
  --foreground: #111827;
  --card: #ffffff;
  --card-foreground: #111827;
  --popover: #ffffff;
  --popover-foreground: #111827;
  --primary: #ea580c;
  --primary-foreground: #ffffff;
  --secondary: #f3f4f6;
  --secondary-foreground: #111827;
  --muted: #f9fafb;
  --muted-foreground: #6b7280;
  --accent: #f3f4f6;
  --accent-foreground: #ea580c;
  --destructive: #ef4444;
  --destructive-foreground: #ffffff;
  --border: #e5e7eb;
  --input: #e5e7eb;
  --ring: #ea580c;
  --radius: 0.5rem;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

/* Dark mode — activated when boring-ui sets data-theme="dark" on the document */
:host-context([data-theme="dark"]) :host,
:host-context([data-theme="dark"]) .pi-root,
:host(.dark) {
  --background: #0f0f0f;
  --foreground: #fafafa;
  --card: #1a1a1a;
  --card-foreground: #fafafa;
  --popover: #1a1a1a;
  --popover-foreground: #fafafa;
  --primary: #fb923c;
  --primary-foreground: #0f0f0f;
  --secondary: #262626;
  --secondary-foreground: #fafafa;
  --muted: #1a1a1a;
  --muted-foreground: #a1a1aa;
  --accent: #262626;
  --accent-foreground: #fb923c;
  --destructive: #f87171;
  --destructive-foreground: #fafafa;
  --border: #2e2e2e;
  --input: #2e2e2e;
  --ring: #fb923c;
}

/* ── Typography — align with boring-ui (14px base, Inter) ── */
.pi-root {
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.pi-root .text-sm { font-size: 13px; }
.pi-root .text-xs { font-size: 11px; }
.pi-root .text-base { font-size: 14px; }
.pi-root .text-lg { font-size: 16px; }

.pi-root textarea,
.pi-root input,
.pi-root button {
  font-family: var(--font-sans);
}

.pi-root pre,
.pi-root code,
.pi-root .font-mono {
  font-family: var(--font-mono);
}

/* ── Message area spacing ── */
.pi-root .max-w-3xl {
  max-width: 100%;
  padding-left: 12px;
  padding-right: 12px;
}

/* ── Message editor input — compact for panel layout ── */
message-editor textarea {
  font-size: 14px !important;
  line-height: 1.5 !important;
  padding: 12px !important;
}

message-editor .bg-card.rounded-xl.border {
  border-radius: 12px;
}

/* ── Focus ring uses app accent ── */
message-editor .bg-card.rounded-xl.border:has(textarea:focus),
message-editor .bg-card.rounded-xl.border:has(textarea:focus-visible) {
  border-color: color-mix(in srgb, var(--primary) 40%, var(--border)) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary) 15%, transparent);
}

message-editor textarea:focus-visible,
message-editor input:focus-visible,
message-editor [contenteditable="true"]:focus-visible {
  outline: none !important;
  outline-offset: 0 !important;
}

/* ── Model selector button — smaller, matches app buttons ── */
message-editor button {
  font-size: 12px;
  border-radius: 6px;
}

/* ── Stats row — smaller ── */
.pi-root .text-xs.text-muted-foreground.flex.justify-between {
  font-size: 11px;
  padding: 2px 4px 4px;
}

/* ── User message pill — use app accent instead of hardcoded orange ── */
.user-message-container {
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 12%, transparent), color-mix(in srgb, var(--primary) 15%, transparent)) !important;
  border-color: color-mix(in srgb, var(--primary) 25%, transparent) !important;
}

/* ── Model selector dialog — align with app design ── */
agent-model-selector .fixed.inset-0 {
  font-family: var(--font-sans);
  font-size: 14px;
}

/* Dialog backdrop */
agent-model-selector .fixed.inset-0 > .fixed.inset-0 {
  background: rgba(0, 0, 0, 0.5) !important;
  backdrop-filter: blur(4px);
}

/* Dialog panel */
agent-model-selector .bg-background {
  border-radius: 12px !important;
  border: 1px solid var(--border);
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
}

/* Dialog header title */
agent-model-selector h2 {
  font-size: 16px;
  font-weight: 600;
}

/* Search input in dialog */
agent-model-selector input[type="text"],
agent-model-selector input[placeholder] {
  font-size: 14px;
  border-radius: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  background: var(--background);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

agent-model-selector input:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary) 15%, transparent) !important;
  outline: none !important;
}

/* Filter buttons (Thinking, Vision) */
agent-model-selector .rounded-full {
  font-size: 12px !important;
  padding: 4px 12px !important;
  border-radius: 9999px !important;
}

/* Model list items */
agent-model-selector [data-model-item] {
  padding: 10px 16px !important;
  transition: background 0.1s ease;
}

agent-model-selector [data-model-item] .text-sm {
  font-size: 13px;
}

agent-model-selector [data-model-item] .text-xs {
  font-size: 11px;
}

/* Provider badge in model list */
agent-model-selector [data-model-item] .inline-flex.items-center {
  font-size: 11px;
  border-radius: 4px;
}

/* Close button in dialogs */
agent-model-selector button[aria-label*="Close"],
agent-model-selector button[type="button"]:has(svg) {
  cursor: pointer;
}

/* ── Hide artifacts panel + floating pill entirely ── */
pi-chat-panel artifacts-panel {
  display: none !important;
}

pi-chat-panel > .relative > button.absolute.z-30 {
  display: none !important;
}

/* Ensure chat area always takes full width (no 50% split for artifacts) */
pi-chat-panel > .relative > .h-full:first-child {
  width: 100% !important;
}

/* ── Scrollbar inside shadow DOM ── */
.pi-root ::-webkit-scrollbar { width: 8px; }
.pi-root ::-webkit-scrollbar-track { background: transparent; }
.pi-root ::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}
.pi-root ::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--foreground) 25%, transparent);
}
`

const fixLitClassFieldShadowing = (element) => {
  if (!element || typeof element !== 'object') return false

  let fixed = false

  const props = element.constructor?.elementProperties
  if (props instanceof Map) {
    for (const key of props.keys()) {
      if (!Object.prototype.hasOwnProperty.call(element, key)) continue
      const value = element[key]
      delete element[key]
      element[key] = value
      fixed = true
    }
  }

  const ownKeys = Object.keys(element)
  for (const key of ownKeys) {
    let proto = Object.getPrototypeOf(element)
    let descriptor = null
    while (proto && !descriptor) {
      descriptor = Object.getOwnPropertyDescriptor(proto, key) || null
      proto = Object.getPrototypeOf(proto)
    }

    if (!descriptor || (typeof descriptor.get !== 'function' && typeof descriptor.set !== 'function')) {
      continue
    }

    const value = element[key]
    delete element[key]
    if (typeof descriptor.set === 'function') {
      element[key] = value
    }
    fixed = true
  }

  if (fixed && typeof element.requestUpdate === 'function') {
    element.requestUpdate()
  }
  return fixed
}

const fixLitTree = (root) => {
  if (!root) return
  const stack = [root]

  while (stack.length > 0) {
    const node = stack.pop()
    if (!node) continue

    if (node.nodeType === Node.ELEMENT_NODE) {
      fixLitClassFieldShadowing(node)
      if (node.shadowRoot) stack.push(node.shadowRoot)
      stack.push(...Array.from(node.children))
      continue
    }

    if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
      stack.push(...Array.from(node.children || []))
    }
  }
}

const logPiError = (context, error) => {
  console.error(`[PiNativeAdapter] ${context}`, error)
}

const modelKey = (model) => `${String(model?.api || '')}:${String(model?.id || '')}`

const createSessionId = () => {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }

  // randomUUID is unavailable on some non-secure origins.
  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    globalThis.crypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }

  const suffix = Math.random().toString(36).slice(2, 10)
  return `pi-${Date.now()}-${suffix}`
}

const promptForApiKey = async (provider, runtime) => {
  const allowInjectedTestKey = import.meta.env.DEV || import.meta.env.MODE === 'test'
  const injectedKey = allowInjectedTestKey ? String(window.__PI_TEST_API_KEY__ || '').trim() : ''
  if (injectedKey) {
    await runtime.providerKeys.set(provider, injectedKey)
    return true
  }

  const label = `${provider || 'model'} API key`
  const entry = typeof window?.prompt === 'function'
    ? window.prompt(`Enter ${label} to use the agent in this browser session:`)
    : null
  const key = String(entry || '').trim()
  if (!key) return false
  await runtime.providerKeys.set(provider, key)
  return true
}

export default function PiNativeAdapter({ panelId, sessionBootstrap = 'latest', initialSessionId = '' }) {
  const dataProvider = useDataProvider()
  const queryClient = useQueryClient()
  const defaultTools = useMemo(
    () => createPiNativeTools(dataProvider, queryClient),
    [dataProvider, queryClient],
  )
  const rootRef = useRef(null)
  const chatPanelRef = useRef(null)
  const agentRef = useRef(null)
  const unsubscribeRef = useRef(() => {})
  const sessionIdRef = useRef('')
  const sessionTitleRef = useRef('New session')

  useEffect(() => {
    const rootEl = rootRef.current
    if (!rootEl) return undefined

    const runtime = getPiRuntime()
    let active = true

    const shadowHost = document.createElement('div')
    shadowHost.style.display = 'flex'
    shadowHost.style.width = '100%'
    shadowHost.style.height = '100%'
    shadowHost.style.minHeight = '0'

    const shadowRoot = shadowHost.attachShadow({ mode: 'open' })
    const styleEl = document.createElement('style')
    styleEl.textContent = scopedCss
    shadowRoot.appendChild(styleEl)

    const panelRoot = document.createElement('div')
    panelRoot.className = 'pi-root'
    shadowRoot.appendChild(panelRoot)

    // Sync dark mode: boring-ui uses data-theme="dark", pi-web-ui uses .dark class
    const syncDarkMode = () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
      panelRoot.classList.toggle('dark', isDark)
    }
    syncDarkMode()
    const themeObserver = new MutationObserver(syncDarkMode)
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    const chatPanel = new ChatPanel()
    fixLitClassFieldShadowing(chatPanel)
    chatPanelRef.current = chatPanel
    panelRoot.appendChild(chatPanel)

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of Array.from(mutation.addedNodes)) {
          if (node.nodeType !== Node.ELEMENT_NODE) {
            continue
          }
          fixLitTree(node)
        }
      }
    })
    observer.observe(shadowRoot, { childList: true, subtree: true })

    rootEl.appendChild(shadowHost)
    fixLitTree(shadowRoot)

    const refreshSessionState = async () => {
      if (!active) return

      const metadata = await runtime.sessions.getAllMetadata()
      const persisted = metadata
        .slice()
        .sort((a, b) => b.lastModified.localeCompare(a.lastModified))
        .map((item) => ({
          id: item.id,
          title: item.title || 'Untitled session',
          lastModified: item.lastModified,
        }))

      const currentId = sessionIdRef.current
      if (currentId && !persisted.some((session) => session.id === currentId)) {
        persisted.unshift({
          id: currentId,
          title: sessionTitleRef.current || 'New session',
          lastModified: new Date().toISOString(),
        })
      }

      publishPiSessionState(panelId, {
        currentSessionId: currentId,
        sessions: persisted,
      })
    }

    const persistCurrentSession = async () => {
      const agent = agentRef.current
      const currentSessionId = sessionIdRef.current
      if (!agent || !currentSessionId || !active) return

      const messages = agent.state.messages || []
      const previous = await runtime.sessions.get(currentSessionId)
      const hasMessages = messages.length > 0
      const previousModel = previous?.model || null
      const nextModel = agent.state.model || null
      const modelChanged = modelKey(previousModel) !== modelKey(nextModel)
      const thinkingChanged = String(previous?.thinkingLevel || 'off') !== String(agent.state.thinkingLevel || 'off')

      if (!hasMessages && previous && !modelChanged && !thinkingChanged) {
        await refreshSessionState()
        return
      }

      const title = hasMessages
        ? titleFromMessages(messages)
        : (previous?.title || sessionTitleRef.current || 'New session')
      sessionTitleRef.current = title

      const now = new Date().toISOString()
      const usage = usageTotals(messages)

      const createdAt = previous?.createdAt || now

      await runtime.sessions.save(
        {
          id: currentSessionId,
          title,
          model: agent.state.model,
          thinkingLevel: agent.state.thinkingLevel,
          messages,
          createdAt,
          lastModified: now,
        },
        {
          id: currentSessionId,
          title,
          createdAt,
          lastModified: now,
          messageCount: messages.length,
          usage,
          modelId: agent.state.model?.id || null,
          thinkingLevel: agent.state.thinkingLevel,
          preview: firstUserText(messages).slice(0, 120),
        },
      )

      await refreshSessionState()
    }

    const mountAgent = async (sessionData) => {
      if (!active) return

      unsubscribeRef.current()
      unsubscribeRef.current = () => {}
      const agentConfig = getPiAgentConfig()

      const model = sessionData?.model || defaultModel()
      if (!model) {
        throw new Error('PI adapter could not find a default model')
      }

      const nextSessionId = sessionData?.id || createSessionId()
      sessionIdRef.current = nextSessionId
      sessionTitleRef.current = sessionData?.title || 'New session'

      const agent = new Agent({
        initialState: {
          systemPrompt: agentConfig.systemPrompt || PI_SYSTEM_PROMPT,
          model,
          thinkingLevel: sessionData?.thinkingLevel || 'off',
          messages: sessionData?.messages || [],
          tools: mergePiTools(
            defaultTools,
            Array.isArray(agentConfig.tools) ? agentConfig.tools : [],
          ),
        },
        convertToLlm: defaultConvertToLlm,
      })
      agent.sessionId = nextSessionId
      agentRef.current = agent

      unsubscribeRef.current = agent.subscribe((event) => {
        if (!active) return
        if (event.type === 'message_end' || event.type === 'agent_end') {
          persistCurrentSession().catch((error) => logPiError('Failed to persist session', error))
        }
      })

      if (chatPanelRef.current) {
        await chatPanelRef.current.setAgent(agent, {
          toolsFactory: (currentAgent) => getAdditionalChatPanelTools(currentAgent),
          onApiKeyRequired: async (provider) => {
            try {
              return await promptForApiKey(provider, runtime)
            } catch (error) {
              logPiError('Failed to show API key prompt', error)
              return false
            }
          },
        })

        // ChatPanel forcibly injects the artifacts tool — strip it so the model
        // never attempts to create artifacts (we don't surface that UI).
        const currentTools = agent.state?.tools || []
        const withoutArtifacts = currentTools.filter((t) => String(t?.name || '') !== 'artifacts')
        if (withoutArtifacts.length !== currentTools.length) {
          agent.setTools(withoutArtifacts)
        }

        fixLitTree(chatPanelRef.current)
      }

      await refreshSessionState()

      const metadata = await runtime.sessions.getMetadata(nextSessionId)
      if (!metadata) {
        await persistCurrentSession()
      }
    }

    const switchSession = async (sessionId) => {
      if (!active || !sessionId || sessionId === sessionIdRef.current) return
      await persistCurrentSession()
      const session = await runtime.sessions.get(sessionId)
      if (!session) return
      await mountAgent(session)
    }

    const createNewSession = async () => {
      if (!active) return
      await persistCurrentSession()
      await mountAgent(null)
    }

    const unsubscribeActions = subscribePiSessionActions(panelId, {
      onSwitch: (sessionId) => {
        switchSession(sessionId).catch((error) => logPiError('Failed to switch session', error))
      },
      onNew: () => {
        createNewSession().catch((error) => logPiError('Failed to create new session', error))
      },
      onRequestState: () => {
        refreshSessionState().catch((error) => logPiError('Failed to refresh session state', error))
      },
    })

    void (async () => {
      // In dev mode, seed provider API keys from Vite env vars (VITE_PI_*_API_KEY).
      // In production, users enter keys manually via the UI prompt.
      if (import.meta.env.DEV) {
        for (const [envKey, provider] of [
          ['VITE_PI_OPENAI_API_KEY', 'openai'],
          ['VITE_PI_ANTHROPIC_API_KEY', 'anthropic'],
          ['VITE_PI_GOOGLE_API_KEY', 'google'],
        ]) {
          const key = String(import.meta.env[envKey] || '').trim()
          if (key) {
            await runtime.providerKeys.set(provider, key)
          }
        }
      }

      const sessions = await runtime.sessions.getAllMetadata()
      const sorted = sessions.slice().sort((a, b) => b.lastModified.localeCompare(a.lastModified))

      if (sessionBootstrap === 'new') {
        if (initialSessionId) {
          const seeded = await runtime.sessions.get(initialSessionId)
          await mountAgent(seeded || { id: initialSessionId })
        } else {
          await mountAgent(null)
        }
      } else if (sorted.length > 0) {
        const latest = await runtime.sessions.get(sorted[0].id)
        await mountAgent(latest)
      } else {
        await mountAgent(null)
      }
      await refreshSessionState()
    })().catch((error) => logPiError('Failed to initialize PI session', error))

    return () => {
      persistCurrentSession().catch((error) => logPiError('Failed to persist session on cleanup', error))
      active = false
      themeObserver.disconnect()
      observer.disconnect()
      unsubscribeActions()
      unsubscribeRef.current()
      agentRef.current = null
      chatPanelRef.current = null
      if (rootEl.contains(shadowHost)) {
        rootEl.removeChild(shadowHost)
      }
    }
  }, [defaultTools, panelId, sessionBootstrap, initialSessionId])

  return <div className="pi-native-wrapper" ref={rootRef} data-testid="pi-native-adapter" />
}
