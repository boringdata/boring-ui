import { Type } from '@sinclair/typebox'
import '@mariozechner/pi-ai/dist/providers/register-builtins.js'
import { getApiProvider } from '@mariozechner/pi-ai/dist/api-registry.js'

// Browser-safe shim for @mariozechner/pi-ai used by pi-web-ui and pi-agent-core.
// This avoids importing the package root, which re-exports Node-only providers/utilities.
export { Type }
export { getModel, getModels, getProviders, modelsAreEqual } from '@mariozechner/pi-ai/dist/models.js'
export {
  EventStream,
  AssistantMessageEventStream,
  createAssistantMessageEventStream,
} from '@mariozechner/pi-ai/dist/utils/event-stream.js'
export { parseStreamingJson } from '@mariozechner/pi-ai/dist/utils/json-parse.js'
export { validateToolArguments, validateToolCall } from '@mariozechner/pi-ai/dist/utils/validation.js'
export { StringEnum } from '@mariozechner/pi-ai/dist/utils/typebox-helpers.js'

function resolveApiProvider(api) {
  const provider = getApiProvider(api)
  if (!provider) throw new Error(`No API provider registered for api: ${api}`)
  return provider
}

export function stream(model, context, options) {
  const provider = resolveApiProvider(model.api)
  return provider.stream(model, context, options)
}

export async function complete(model, context, options) {
  const s = stream(model, context, options)
  return s.result()
}

export function streamSimple(model, context, options) {
  const provider = resolveApiProvider(model.api)
  return provider.streamSimple(model, context, options)
}

export async function completeSimple(model, context, options) {
  const s = streamSimple(model, context, options)
  return s.result()
}
