import { describe, it, expect } from 'vitest'
import {
  calculateFuzzyScore,
  fuzzySearchMessages,
  filterMessagesByType,
  filterMessagesByDateRange,
  filterMessagesByTool,
  applyQuickFilter,
  highlightSearchResults,
  searchMessages,
  getSearchSuggestions,
} from '../../utils/searchMessages'

const mockMessages = [
  {
    id: 'msg-1',
    content: 'Hello, how are you?',
    author: 'user',
    role: 'user',
    timestamp: new Date('2026-01-30'),
  },
  {
    id: 'msg-2',
    content: 'I am doing great, thanks for asking!',
    author: 'Claude',
    role: 'assistant',
    timestamp: new Date('2026-01-30'),
  },
  {
    id: 'msg-3',
    content: 'Can you search for information about React?',
    author: 'user',
    role: 'user',
    timestamp: new Date('2026-01-29'),
    toolsUsed: [{ toolName: 'SearchWeb' }],
  },
  {
    id: 'msg-4',
    content: 'Here is information about React library',
    author: 'Claude',
    role: 'assistant',
    timestamp: new Date('2026-01-29'),
  },
  {
    id: 'msg-5',
    content: 'Thanks for the React information!',
    author: 'user',
    role: 'user',
    timestamp: new Date('2026-01-28'),
  },
]

describe('searchMessages Utility Functions', () => {
  describe('calculateFuzzyScore', () => {
    it('should return 0 for empty query', () => {
      expect(calculateFuzzyScore('', 'test text')).toBe(0)
    })

    it('should return 0 for empty text', () => {
      expect(calculateFuzzyScore('test', '')).toBe(0)
    })

    it('should return perfect score for exact match', () => {
      const score = calculateFuzzyScore('hello', 'hello')
      expect(score).toBe(1)
    })

    it('should calculate score for fuzzy match', () => {
      const score = calculateFuzzyScore('hrw', 'hello react world')
      expect(score).toBeGreaterThan(0)
      expect(score).toBeLessThan(1)
    })

    it('should be case insensitive', () => {
      const score1 = calculateFuzzyScore('hello', 'HELLO')
      const score2 = calculateFuzzyScore('HELLO', 'hello')
      expect(score1).toBe(score2)
    })

    it('should return 0 if query too long', () => {
      expect(calculateFuzzyScore('abcdefgh', 'abcd')).toBe(0)
    })

    it('should give higher score for consecutive matches', () => {
      const score1 = calculateFuzzyScore('he', 'hello')
      const score2 = calculateFuzzyScore('h', 'hello e')
      expect(score1).toBeGreaterThan(score2)
    })
  })

  describe('fuzzySearchMessages', () => {
    it('should return empty array for empty query', () => {
      const results = fuzzySearchMessages(mockMessages, '')
      expect(results).toEqual([])
    })

    it('should find messages matching query', () => {
      const results = fuzzySearchMessages(mockMessages, 'hello')
      expect(results.length).toBeGreaterThan(0)
      expect(results[0].content).toContain('hello')
    })

    it('should sort by score (highest first)', () => {
      const results = fuzzySearchMessages(mockMessages, 'react')
      expect(results[0].searchScore).toBeGreaterThanOrEqual(
        results[results.length - 1].searchScore,
      )
    })

    it('should filter by threshold', () => {
      const results = fuzzySearchMessages(mockMessages, 'xyz', 0.1)
      expect(results.length).toBe(0)
    })

    it('should search multiple fields', () => {
      const results = fuzzySearchMessages(mockMessages, 'claude')
      expect(results.some((m) => m.author === 'Claude')).toBe(true)
    })
  })

  describe('filterMessagesByType', () => {
    it('should return all messages if no types specified', () => {
      const results = filterMessagesByType(mockMessages, [])
      expect(results).toEqual(mockMessages)
    })

    it('should filter by single type', () => {
      const results = filterMessagesByType(mockMessages, 'user')
      expect(results.every((m) => m.role === 'user')).toBe(true)
    })

    it('should filter by multiple types', () => {
      const results = filterMessagesByType(mockMessages, ['user', 'assistant'])
      expect(results.length).toEqual(mockMessages.length)
    })

    it('should handle string type parameter', () => {
      const results = filterMessagesByType(mockMessages, 'assistant')
      expect(results.every((m) => m.role === 'assistant')).toBe(true)
    })

    it('should return empty array for non-matching type', () => {
      const results = filterMessagesByType(mockMessages, 'invalid')
      expect(results).toEqual([])
    })
  })

  describe('filterMessagesByDateRange', () => {
    it('should return all messages if no dates specified', () => {
      const results = filterMessagesByDateRange(mockMessages)
      expect(results).toEqual(mockMessages)
    })

    it('should filter by start date', () => {
      const startDate = new Date('2026-01-29')
      const results = filterMessagesByDateRange(mockMessages, startDate)
      expect(results.every((m) => new Date(m.timestamp) >= startDate)).toBe(true)
    })

    it('should filter by end date', () => {
      const endDate = new Date('2026-01-29')
      const results = filterMessagesByDateRange(mockMessages, null, endDate)
      // All messages should be on or before end date
      expect(
        results.every(
          (m) => new Date(m.timestamp) <= new Date('2026-01-29 23:59:59'),
        ),
      ).toBe(true)
    })

    it('should filter by date range', () => {
      const startDate = new Date('2026-01-29')
      const endDate = new Date('2026-01-30')
      const results = filterMessagesByDateRange(mockMessages, startDate, endDate)
      expect(results.length).toBeGreaterThan(0)
      expect(results.length).toBeLessThanOrEqual(mockMessages.length)
    })

    it('should handle invalid dates gracefully', () => {
      const results = filterMessagesByDateRange(
        mockMessages,
        new Date('invalid'),
      )
      expect(results).toEqual([])
    })

    it('should accept string dates', () => {
      const results = filterMessagesByDateRange(
        mockMessages,
        '2026-01-29',
        '2026-01-30',
      )
      expect(results.length).toBeGreaterThan(0)
    })
  })

  describe('filterMessagesByTool', () => {
    it('should return all messages if no tools specified', () => {
      const results = filterMessagesByTool(mockMessages, [])
      expect(results).toEqual(mockMessages)
    })

    it('should filter by tool name', () => {
      const results = filterMessagesByTool(mockMessages, 'SearchWeb')
      expect(results.some((m) => m.toolsUsed?.length > 0)).toBe(true)
    })

    it('should be case insensitive', () => {
      const results1 = filterMessagesByTool(mockMessages, 'searchweb')
      const results2 = filterMessagesByTool(mockMessages, 'SearchWeb')
      expect(results1.length).toEqual(results2.length)
    })

    it('should handle partial tool names', () => {
      const results = filterMessagesByTool(mockMessages, 'Search')
      expect(results.some((m) => m.toolsUsed?.length > 0)).toBe(true)
    })

    it('should return empty array for non-matching tool', () => {
      const results = filterMessagesByTool(mockMessages, 'NonExistentTool')
      expect(results).toEqual([])
    })
  })

  describe('applyQuickFilter', () => {
    it('should return all messages for unknown preset', () => {
      const results = applyQuickFilter(mockMessages, 'invalid')
      expect(results).toEqual(mockMessages)
    })

    it('should filter last 24 hours', () => {
      const results = applyQuickFilter(mockMessages, 'last24h')
      expect(results.length).toBeGreaterThan(0)
    })

    it('should filter last 7 days', () => {
      const results = applyQuickFilter(mockMessages, 'last7d')
      expect(results.length).toEqual(mockMessages.length)
    })

    it('should filter user messages', () => {
      const results = applyQuickFilter(mockMessages, 'user')
      expect(results.every((m) => m.role === 'user')).toBe(true)
    })

    it('should filter assistant messages', () => {
      const results = applyQuickFilter(mockMessages, 'assistant')
      expect(results.every((m) => m.role === 'assistant')).toBe(true)
    })

    it('should filter tool usage', () => {
      const results = applyQuickFilter(mockMessages, 'tool')
      expect(results.some((m) => m.toolsUsed?.length > 0)).toBe(true)
    })
  })

  describe('highlightSearchResults', () => {
    it('should return original text for empty query', () => {
      const result = highlightSearchResults('test text', '')
      expect(result).toBe('test text')
    })

    it('should return original text for empty text', () => {
      const result = highlightSearchResults('', 'query')
      expect(result).toBe('')
    })

    it('should highlight exact matches', () => {
      const result = highlightSearchResults('hello world', 'hello')
      expect(result).toContain('<mark')
      expect(result).toContain('hello')
    })

    it('should highlight all occurrences', () => {
      const result = highlightSearchResults('hello hello hello', 'hello')
      const matches = (result.match(/<mark/g) || []).length
      expect(matches).toBe(3)
    })

    it('should use custom class name', () => {
      const result = highlightSearchResults('hello', 'hello', 'custom-class')
      expect(result).toContain('custom-class')
    })
  })

  describe('searchMessages', () => {
    it('should return empty results for empty query and filters', () => {
      const result = searchMessages(mockMessages, {})
      expect(result.results).toEqual([])
    })

    it('should search by query', () => {
      const result = searchMessages(mockMessages, { query: 'hello' })
      expect(result.results.length).toBeGreaterThan(0)
      expect(result.count).toBeGreaterThan(0)
    })

    it('should apply filters', () => {
      const result = searchMessages(mockMessages, { types: ['user'] })
      expect(result.results.every((m) => m.role === 'user')).toBe(true)
    })

    it('should combine query and filters', () => {
      const result = searchMessages(mockMessages, {
        query: 'react',
        types: ['user'],
      })
      expect(result.results.every((m) => m.role === 'user')).toBe(true)
      expect(result.results.some((m) => m.content.toLowerCase().includes('react'))).toBe(
        true,
      )
    })

    it('should return search metadata', () => {
      const result = searchMessages(mockMessages, { query: 'hello' })
      expect(result).toHaveProperty('results')
      expect(result).toHaveProperty('count')
      expect(result).toHaveProperty('query')
      expect(result).toHaveProperty('appliedFilters')
    })

    it('should track applied filters', () => {
      const result = searchMessages(mockMessages, {
        query: 'test',
        types: ['user'],
        quickFilter: 'last24h',
      })
      expect(result.appliedFilters.types).toEqual(['user'])
      expect(result.appliedFilters.quickFilter).toBe('last24h')
    })
  })

  describe('getSearchSuggestions', () => {
    it('should return empty array for empty partial', () => {
      const suggestions = getSearchSuggestions(mockMessages, '')
      expect(suggestions).toEqual([])
    })

    it('should return suggestions matching partial', () => {
      const suggestions = getSearchSuggestions(mockMessages, 'hello')
      expect(suggestions.length).toBeGreaterThan(0)
    })

    it('should limit suggestions', () => {
      const suggestions = getSearchSuggestions(mockMessages, 'a', 3)
      expect(suggestions.length).toBeLessThanOrEqual(3)
    })

    it('should be case insensitive', () => {
      const suggestions1 = getSearchSuggestions(mockMessages, 'hello')
      const suggestions2 = getSearchSuggestions(mockMessages, 'HELLO')
      expect(suggestions1.length).toEqual(suggestions2.length)
    })

    it('should return unique suggestions', () => {
      const suggestions = getSearchSuggestions(mockMessages, 'a')
      const uniqueSuggestions = new Set(suggestions)
      expect(suggestions.length).toEqual(uniqueSuggestions.size)
    })

    it('should sort suggestions alphabetically', () => {
      const suggestions = getSearchSuggestions(mockMessages, 'a', 10)
      for (let i = 1; i < suggestions.length; i++) {
        expect(suggestions[i] >= suggestions[i - 1]).toBe(true)
      }
    })
  })

  describe('Performance', () => {
    it('should handle large message lists', () => {
      const largeMessages = Array.from({ length: 1000 }, (_, i) => ({
        id: `msg-${i}`,
        content: `Message ${i} with some test content`,
        author: 'user',
        role: i % 2 === 0 ? 'user' : 'assistant',
        timestamp: new Date(),
      }))

      const startTime = performance.now()
      const result = searchMessages(largeMessages, {
        query: 'test',
        types: ['user'],
      })
      const endTime = performance.now()

      expect(result.count).toBeGreaterThan(0)
      expect(endTime - startTime).toBeLessThan(200) // Should complete in <200ms
    })

    it('should handle complex filters', () => {
      const startTime = performance.now()
      const result = searchMessages(mockMessages, {
        query: 'hello',
        types: ['user', 'assistant'],
        startDate: new Date('2026-01-28'),
        endDate: new Date('2026-01-30'),
        tools: ['SearchWeb'],
        quickFilter: 'last7d',
      })
      const endTime = performance.now()

      expect(endTime - startTime).toBeLessThan(100)
    })
  })

  describe('Edge Cases', () => {
    it('should handle null messages array', () => {
      const result = searchMessages(null, { query: 'test' })
      expect(result.results).toEqual([])
    })

    it('should handle undefined messages array', () => {
      const result = searchMessages(undefined, { query: 'test' })
      expect(result.results).toEqual([])
    })

    it('should handle messages without timestamp', () => {
      const messagesWithoutTimestamp = [
        { id: 'msg-1', content: 'test', author: 'user', role: 'user' },
      ]
      const result = filterMessagesByDateRange(messagesWithoutTimestamp)
      expect(result).toEqual(messagesWithoutTimestamp)
    })

    it('should handle messages without role/type', () => {
      const messagesWithoutRole = [
        { id: 'msg-1', content: 'test', author: 'user' },
      ]
      const result = filterMessagesByType(messagesWithoutRole, 'user')
      expect(result.length).toBe(0)
    })

    it('should handle special characters in search', () => {
      const specialMessages = [
        {
          id: 'msg-1',
          content: 'Test @#$%^&*()',
          author: 'user',
          role: 'user',
          timestamp: new Date(),
        },
      ]
      const result = fuzzySearchMessages(specialMessages, '@#')
      expect(result.length).toBeGreaterThanOrEqual(0)
    })
  })
})
