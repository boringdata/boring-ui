import { clearApiProviders, registerApiProvider } from '@mariozechner/pi-ai/dist/api-registry.js'
import { streamAnthropic, streamSimpleAnthropic } from '@mariozechner/pi-ai/dist/providers/anthropic.js'
import { streamGoogle, streamSimpleGoogle } from '@mariozechner/pi-ai/dist/providers/google.js'
import {
  streamOpenAICompletions,
  streamSimpleOpenAICompletions,
} from '@mariozechner/pi-ai/dist/providers/openai-completions.js'
import {
  streamOpenAIResponses,
  streamSimpleOpenAIResponses,
} from '@mariozechner/pi-ai/dist/providers/openai-responses.js'

// Browser-safe registry for PI web embedding.
// Intentionally excludes Node-centric providers (Bedrock, Codex, Gemini CLI, Vertex).
export function registerBuiltInApiProviders() {
  registerApiProvider({
    api: 'anthropic-messages',
    stream: streamAnthropic,
    streamSimple: streamSimpleAnthropic,
  })
  registerApiProvider({
    api: 'google-generative-ai',
    stream: streamGoogle,
    streamSimple: streamSimpleGoogle,
  })
  registerApiProvider({
    api: 'openai-completions',
    stream: streamOpenAICompletions,
    streamSimple: streamSimpleOpenAICompletions,
  })
  registerApiProvider({
    api: 'openai-responses',
    stream: streamOpenAIResponses,
    streamSimple: streamSimpleOpenAIResponses,
  })
}

export function resetApiProviders() {
  clearApiProviders()
  registerBuiltInApiProviders()
}

registerBuiltInApiProviders()
