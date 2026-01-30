/**
 * searchMessages - Utility functions for searching and filtering messages
 *
 * Provides:
 * - Fuzzy search with scoring
 * - Filter by message type
 * - Filter by date range
 * - Filter by tool usage
 * - Search result highlighting
 * - Debounced search
 */

/**
 * Fuzzy search scoring algorithm
 * Returns score between 0 and 1, where 1 is a perfect match
 *
 * @param {string} query - Search query
 * @param {string} text - Text to search in
 * @returns {number} Score from 0 to 1
 */
export function calculateFuzzyScore(query, text) {
  if (!query || !text) return 0
  if (query.length > text.length) return 0

  query = query.toLowerCase()
  text = text.toLowerCase()

  let queryIndex = 0
  let textIndex = 0
  let score = 0
  let consecutiveMatches = 0

  while (queryIndex < query.length && textIndex < text.length) {
    if (query[queryIndex] === text[textIndex]) {
      queryIndex++
      consecutiveMatches++
      score += Math.pow(2, consecutiveMatches - 1) // Bonus for consecutive matches
    } else {
      consecutiveMatches = 0
    }
    textIndex++
  }

  // If not all query characters were matched, return 0
  if (queryIndex < query.length) return 0

  // Normalize score (higher score for shorter text with matches)
  const matchRatio = queryIndex / query.length
  const lengthRatio = queryIndex / text.length

  return (matchRatio + lengthRatio) / 2
}

/**
 * Search messages with fuzzy matching
 *
 * @param {Array} messages - Array of message objects
 * @param {string} query - Search query
 * @param {number} threshold - Minimum score (0-1) to include result
 * @returns {Array} Filtered and scored messages
 */
export function fuzzySearchMessages(
  messages = [],
  query = '',
  threshold = 0.3,
) {
  if (!query.trim()) return []

  return messages
    .map((message) => {
      const contentScore = calculateFuzzyScore(query, message.content || '')
      const authorScore = calculateFuzzyScore(query, message.author || '')

      const score = Math.max(contentScore, authorScore)

      return {
        ...message,
        searchScore: score,
      }
    })
    .filter((message) => message.searchScore >= threshold)
    .sort((a, b) => b.searchScore - a.searchScore)
}

/**
 * Filter messages by type
 *
 * @param {Array} messages - Array of messages
 * @param {Array|string} types - Message types to include
 * @returns {Array} Filtered messages
 */
export function filterMessagesByType(messages = [], types = []) {
  if (!types || types.length === 0) return messages

  const typeArray = Array.isArray(types) ? types : [types]
  return messages.filter((msg) => typeArray.includes(msg.role || msg.type))
}

/**
 * Filter messages by date range
 *
 * @param {Array} messages - Array of messages
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date
 * @returns {Array} Filtered messages
 */
export function filterMessagesByDateRange(
  messages = [],
  startDate = null,
  endDate = null,
) {
  if (!startDate && !endDate) return messages

  return messages.filter((msg) => {
    const msgDate = msg.timestamp instanceof Date ? msg.timestamp : new Date(msg.timestamp)

    if (isNaN(msgDate.getTime())) return false

    if (startDate) {
      const start = startDate instanceof Date ? startDate : new Date(startDate)
      if (msgDate < start) return false
    }

    if (endDate) {
      const end = endDate instanceof Date ? endDate : new Date(endDate)
      // Include messages from the entire end day
      end.setHours(23, 59, 59, 999)
      if (msgDate > end) return false
    }

    return true
  })
}

/**
 * Filter messages by tool usage
 *
 * @param {Array} messages - Array of messages
 * @param {Array|string} tools - Tool names to filter by
 * @returns {Array} Filtered messages
 */
export function filterMessagesByTool(messages = [], tools = []) {
  if (!tools || tools.length === 0) return messages

  const toolArray = Array.isArray(tools) ? tools : [tools]

  return messages.filter((msg) => {
    if (!msg.toolsUsed && !msg.tools) return false

    const msgTools = msg.toolsUsed || msg.tools || []
    const msgToolNames = msgTools.map((t) =>
      typeof t === 'string' ? t : t.toolName || t.name,
    )

    return toolArray.some((tool) =>
      msgToolNames.some((t) => t.toLowerCase().includes(tool.toLowerCase())),
    )
  })
}

/**
 * Quick filter presets
 *
 * @param {Array} messages - Array of messages
 * @param {string} preset - Filter preset name
 * @returns {Array} Filtered messages
 */
export function applyQuickFilter(messages = [], preset = '') {
  if (!preset) return messages

  const now = new Date()
  const msPerDay = 1000 * 60 * 60 * 24

  switch (preset.toLowerCase()) {
    case 'today':
    case 'last24h': {
      const yesterday = new Date(now - msPerDay)
      return filterMessagesByDateRange(messages, yesterday, now)
    }

    case 'thisweek':
    case 'last7d': {
      const weekAgo = new Date(now - msPerDay * 7)
      return filterMessagesByDateRange(messages, weekAgo, now)
    }

    case 'thismonth':
    case 'last30d': {
      const monthAgo = new Date(now - msPerDay * 30)
      return filterMessagesByDateRange(messages, monthAgo, now)
    }

    case 'user':
      return filterMessagesByType(messages, 'user')

    case 'assistant':
      return filterMessagesByType(messages, 'assistant')

    case 'tool':
      return messages.filter((msg) => msg.toolsUsed?.length > 0 || msg.tools?.length > 0)

    default:
      return messages
  }
}

/**
 * Highlight search results in text
 *
 * @param {string} text - Text to highlight
 * @param {string} query - Search query
 * @param {string} className - CSS class for highlights
 * @returns {string} HTML with highlighted matches
 */
export function highlightSearchResults(text = '', query = '', className = 'highlight') {
  if (!query.trim() || !text) return text

  const queryLower = query.toLowerCase()
  const textLower = text.toLowerCase()
  const parts = []

  let lastIndex = 0
  let searchIndex = 0

  while (searchIndex < textLower.length) {
    const matchIndex = textLower.indexOf(queryLower, searchIndex)

    if (matchIndex === -1) {
      parts.push(text.substring(lastIndex))
      break
    }

    parts.push(text.substring(lastIndex, matchIndex))
    parts.push(
      `<mark class="${className}">${text.substring(matchIndex, matchIndex + query.length)}</mark>`,
    )

    lastIndex = matchIndex + query.length
    searchIndex = lastIndex
  }

  return parts.join('')
}

/**
 * Combined search and filter
 *
 * @param {Array} messages - Array of messages
 * @param {Object} options - Search options
 * @returns {Object} Search results with metadata
 */
export function searchMessages(messages = [], options = {}) {
  const {
    query = '',
    types = [],
    startDate = null,
    endDate = null,
    tools = [],
    quickFilter = '',
    threshold = 0.3,
  } = options

  let results = [...messages]

  // Apply quick filter first
  if (quickFilter) {
    results = applyQuickFilter(results, quickFilter)
  }

  // Apply type filter
  if (types.length > 0) {
    results = filterMessagesByType(results, types)
  }

  // Apply date range filter
  if (startDate || endDate) {
    results = filterMessagesByDateRange(results, startDate, endDate)
  }

  // Apply tool filter
  if (tools.length > 0) {
    results = filterMessagesByTool(results, tools)
  }

  // Apply fuzzy search
  if (query.trim()) {
    results = fuzzySearchMessages(results, query, threshold)
  }

  return {
    results,
    count: results.length,
    query,
    appliedFilters: {
      types: types.length > 0 ? types : null,
      dateRange: startDate || endDate ? { startDate, endDate } : null,
      tools: tools.length > 0 ? tools : null,
      quickFilter: quickFilter || null,
    },
  }
}

/**
 * Debounce search function
 *
 * @param {Function} searchFn - Search function to debounce
 * @param {number} delay - Debounce delay in ms
 * @returns {Function} Debounced function
 */
export function debounceSearch(searchFn, delay = 300) {
  let timeoutId = null

  return function (...args) {
    return new Promise((resolve) => {
      if (timeoutId) clearTimeout(timeoutId)

      timeoutId = setTimeout(() => {
        resolve(searchFn(...args))
      }, delay)
    })
  }
}

/**
 * Get search suggestions based on partial query
 *
 * @param {Array} messages - Array of messages
 * @param {string} partial - Partial search query
 * @param {number} limit - Max suggestions to return
 * @returns {Array} Suggestion strings
 */
export function getSearchSuggestions(
  messages = [],
  partial = '',
  limit = 5,
) {
  if (!partial.trim()) return []

  const suggestions = new Set()

  messages.forEach((msg) => {
    if (msg.content) {
      const words = msg.content.toLowerCase().split(/\s+/)
      words.forEach((word) => {
        if (word.startsWith(partial.toLowerCase())) {
          suggestions.add(word)
        }
      })
    }
  })

  return Array.from(suggestions)
    .sort()
    .slice(0, limit)
}

export default {
  calculateFuzzyScore,
  fuzzySearchMessages,
  filterMessagesByType,
  filterMessagesByDateRange,
  filterMessagesByTool,
  applyQuickFilter,
  highlightSearchResults,
  searchMessages,
  debounceSearch,
  getSearchSuggestions,
}
