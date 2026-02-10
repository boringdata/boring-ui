/**
 * Default chat provider registry with all built-in providers.
 */
import ChatProviderRegistry from './registry'
import claudeConfig from './claude'
import sandboxConfig from './sandbox'
import inspectorConfig from './inspector'

const chatProviders = new ChatProviderRegistry()

chatProviders.register(claudeConfig)
chatProviders.register(sandboxConfig)
chatProviders.register(inspectorConfig)

export default chatProviders
