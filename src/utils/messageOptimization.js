/**
 * Message Optimization Utilities
 *
 * Provides utilities for optimizing message rendering and interactions:
 * - Debouncing and throttling
 * - Memoization of message content
 * - Batch updates
 * - Lazy loading
 */

/**
 * Debounce function - delays execution until events stop
 * Used for: search input, resize events, scroll events
 *
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @param {Object} options - Options object
 * @returns {Function} Debounced function
 */
export function debounce(func, wait, options = {}) {
  let timeout
  let previous = 0
  const { leading = false, trailing = true, maxWait = null } = options

  const later = function () {
    const now = Date.now()
    if (!leading) previous = now
    timeout = null

    if (trailing) {
      func.apply(this, arguments)
    }
  }

  const debounced = function (...args) {
    const now = Date.now()

    if (!previous && !leading) previous = now

    const remaining = wait - (now - previous)

    if (remaining <= 0 || remaining > wait || (maxWait && now - previous >= maxWait)) {
      if (timeout) {
        clearTimeout(timeout)
        timeout = null
      }
      previous = now
      func.apply(this, args)
    } else if (!timeout && trailing) {
      timeout = setTimeout(later, remaining)
    }
  }

  debounced.cancel = () => {
    clearTimeout(timeout)
    previous = 0
    timeout = null
  }

  return debounced
}

/**
 * Throttle function - limits execution frequency
 * Used for: scroll events, animation frames
 *
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between calls in ms
 * @returns {Function} Throttled function
 */
export function throttle(func, limit) {
  let inThrottle
  let lastRan

  return function (...args) {
    if (!lastRan) {
      func.apply(this, args)
      lastRan = Date.now()
    } else {
      clearTimeout(inThrottle)
      inThrottle = setTimeout(() => {
        if (Date.now() - lastRan >= limit) {
          func.apply(this, args)
          lastRan = Date.now()
        }
      }, limit - (Date.now() - lastRan))
    }
  }
}

/**
 * Batch updates to reduce re-renders
 *
 * @param {Array} items - Items to batch
 * @param {number} batchSize - Size of each batch
 * @returns {Array<Array>} Batched arrays
 */
export function batchUpdates(items, batchSize = 10) {
  const batches = []

  for (let i = 0; i < items.length; i += batchSize) {
    batches.push(items.slice(i, i + batchSize))
  }

  return batches
}

/**
 * Memoize message content for rendering
 *
 * @param {Array} messages - Messages to memoize
 * @returns {Map} Map of message ID to memoized content
 */
export function memoizeMessages(messages) {
  const cache = new Map()

  messages.forEach((msg) => {
    const key = `${msg.id}-${msg.timestamp}`
    if (!cache.has(key)) {
      cache.set(key, {
        id: msg.id,
        content: msg.content,
        role: msg.role,
        timestamp: msg.timestamp,
        hash: hashContent(msg.content),
      })
    }
  })

  return cache
}

/**
 * Simple hash of content for change detection
 *
 * @param {string} content - Content to hash
 * @returns {number} Hash code
 */
function hashContent(content) {
  if (!content) return 0

  let hash = 0
  for (let i = 0; i < content.length; i++) {
    const char = content.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash // Convert to 32bit integer
  }

  return hash
}

/**
 * Detect changes between message arrays
 *
 * @param {Array} oldMessages - Previous messages
 * @param {Array} newMessages - New messages
 * @returns {Object} Change information
 */
export function detectMessageChanges(oldMessages, newMessages) {
  const changes = {
    added: [],
    removed: [],
    updated: [],
    moved: [],
  }

  const oldIds = new Set(oldMessages.map((m) => m.id))
  const newIds = new Set(newMessages.map((m) => m.id))

  // Detect added and updated
  newMessages.forEach((newMsg, newIdx) => {
    if (!oldIds.has(newMsg.id)) {
      changes.added.push(newMsg)
    } else {
      const oldMsg = oldMessages.find((m) => m.id === newMsg.id)
      if (oldMsg && hashContent(oldMsg.content) !== hashContent(newMsg.content)) {
        changes.updated.push(newMsg)
      }

      // Detect moved
      const oldIdx = oldMessages.findIndex((m) => m.id === newMsg.id)
      if (oldIdx !== newIdx) {
        changes.moved.push({ id: newMsg.id, from: oldIdx, to: newIdx })
      }
    }
  })

  // Detect removed
  oldMessages.forEach((oldMsg) => {
    if (!newIds.has(oldMsg.id)) {
      changes.removed.push(oldMsg)
    }
  })

  return changes
}

/**
 * Lazy load resources (images, embeds)
 *
 * @param {Array} messages - Messages to lazy load
 * @returns {Object} Lazy loader instance
 */
export function createLazyLoader(messages) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const img = entry.target
        if (img.dataset.src) {
          img.src = img.dataset.src
          img.removeAttribute('data-src')
          observer.unobserve(img)
        }
      }
    })
  })

  return {
    observe: (element) => observer.observe(element),
    unobserve: (element) => observer.unobserve(element),
    disconnect: () => observer.disconnect(),
  }
}

/**
 * Calculate optimal message batch size based on device performance
 *
 * @returns {number} Recommended batch size
 */
export function getOptimalBatchSize() {
  if (!navigator.deviceMemory) {
    return 10 // Default
  }

  const memory = navigator.deviceMemory

  if (memory <= 4) return 5
  if (memory <= 8) return 10
  return 20
}

/**
 * Compress message content for storage
 *
 * @param {string} content - Content to compress
 * @returns {string} Compressed content
 */
export function compressContent(content) {
  if (!content) return ''

  return content
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim()
}

/**
 * Extract metadata from message for indexing
 *
 * @param {Object} message - Message object
 * @returns {Object} Extracted metadata
 */
export function extractMessageMetadata(message) {
  const words = (message.content || '').split(/\s+/).length
  const hasCode = /```|<code>|`/.test(message.content)
  const hasLink = /https?:\/\//.test(message.content)

  return {
    id: message.id,
    role: message.role,
    wordCount: words,
    hasCode,
    hasLink,
    timestamp: message.timestamp,
    length: message.content?.length || 0,
  }
}

/**
 * Filter messages efficiently
 *
 * @param {Array} messages - Messages to filter
 * @param {Function} predicate - Filter predicate
 * @returns {Array} Filtered messages
 */
export function filterMessages(messages, predicate) {
  return messages.filter(predicate)
}

/**
 * Sort messages efficiently
 *
 * @param {Array} messages - Messages to sort
 * @param {string} sortBy - Sort key ('timestamp', 'role', etc.)
 * @param {string} order - Sort order ('asc', 'desc')
 * @returns {Array} Sorted messages
 */
export function sortMessages(messages, sortBy = 'timestamp', order = 'asc') {
  const sorted = [...messages].sort((a, b) => {
    const aVal = a[sortBy]
    const bVal = b[sortBy]

    if (typeof aVal === 'string') {
      return order === 'asc'
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal)
    }

    return order === 'asc' ? aVal - bVal : bVal - aVal
  })

  return sorted
}

/**
 * Request idle callback wrapper with fallback
 *
 * @param {Function} callback - Callback to execute
 * @param {Object} options - Options
 * @returns {number} Callback ID
 */
export function requestIdleWork(callback, options = {}) {
  if ('requestIdleCallback' in window) {
    return window.requestIdleCallback(callback, options)
  } else {
    // Fallback to setTimeout
    return setTimeout(callback, 1)
  }
}

/**
 * Cancel idle callback with fallback
 *
 * @param {number} id - Callback ID
 */
export function cancelIdleWork(id) {
  if ('cancelIdleCallback' in window) {
    window.cancelIdleCallback(id)
  } else {
    clearTimeout(id)
  }
}

export default {
  debounce,
  throttle,
  batchUpdates,
  memoizeMessages,
  detectMessageChanges,
  createLazyLoader,
  getOptimalBatchSize,
  compressContent,
  extractMessageMetadata,
  filterMessages,
  sortMessages,
  requestIdleWork,
  cancelIdleWork,
}
