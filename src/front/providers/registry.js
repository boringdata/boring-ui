/**
 * Chat Provider Registry - Manages chat UI provider registration.
 *
 * Mirrors the PaneRegistry pattern (src/front/registry/panes.js).
 * Each chat provider is a self-contained module that registers itself
 * with a component, label, and optional capability requirements.
 *
 * @module providers/registry
 */

/**
 * @typedef {Object} ChatProviderConfig
 * @property {string} id - Unique provider key (e.g. 'claude', 'sandbox', 'inspector')
 * @property {string} label - Display name shown in UI
 * @property {React.ComponentType} component - React component to render
 * @property {string[]} [requiresCapabilities] - Backend capabilities required (checked against /api/capabilities)
 */

class ChatProviderRegistry {
  constructor() {
    /** @type {Map<string, ChatProviderConfig>} */
    this._providers = new Map()
  }

  /**
   * Register a chat provider.
   * @param {ChatProviderConfig} config
   */
  register(config) {
    if (!config.id || !config.component) {
      throw new Error('Chat provider config must have id and component')
    }
    this._providers.set(config.id, {
      requiresCapabilities: [],
      ...config,
    })
  }

  /**
   * Get a provider by ID.
   * @param {string} id
   * @returns {ChatProviderConfig|undefined}
   */
  get(id) {
    return this._providers.get(id)
  }

  /**
   * Check if a provider is registered.
   * @param {string} id
   * @returns {boolean}
   */
  has(id) {
    return this._providers.has(id)
  }

  /**
   * List all registered providers.
   * @returns {ChatProviderConfig[]}
   */
  list() {
    return Array.from(this._providers.values())
  }

  /**
   * List provider IDs.
   * @returns {string[]}
   */
  listIds() {
    return Array.from(this._providers.keys())
  }

  /**
   * Check if a provider's capability requirements are met.
   * @param {string} id
   * @param {Object} capabilities - From /api/capabilities
   * @returns {boolean}
   */
  checkRequirements(id, capabilities) {
    const provider = this._providers.get(id)
    if (!provider) return false

    const features = capabilities?.features || {}
    for (const cap of provider.requiresCapabilities) {
      if (!features[cap]) return false
    }
    return true
  }

  /**
   * Get providers whose requirements are satisfied.
   * @param {Object} capabilities
   * @returns {ChatProviderConfig[]}
   */
  getAvailable(capabilities) {
    return this.list().filter((p) => this.checkRequirements(p.id, capabilities))
  }
}

export { ChatProviderRegistry }
export default ChatProviderRegistry
