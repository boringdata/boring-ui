import React, { useState, useCallback, useEffect, useRef } from 'react'
import {
  Search,
  X,
  Clock,
  MessageSquare,
  Settings,
  AlertCircle,
} from 'lucide-react'
import {
  searchMessages,
  debounceSearch,
  getSearchSuggestions,
} from '../../utils/searchMessages'
import '../../styles/search.css'

/**
 * SearchBar Component - Search and filter messages
 *
 * Provides:
 * - Real-time search with fuzzy matching
 * - Quick filters (last 24h, week, month, user, assistant, tool)
 * - Advanced filters (type, date range, tools)
 * - Search history
 * - Search suggestions
 * - Keyboard shortcuts (Cmd+F to focus)
 * - Clear filters and results
 *
 * @param {Object} props
 * @param {Array} props.messages - Array of messages to search
 * @param {Function} props.onSearch - Callback with search results
 * @param {boolean} props.inline - Inline layout (horizontal)
 * @param {boolean} props.compact - Compact mode (fewer options visible)
 * @param {string} props.placeholder - Search placeholder text
 * @returns {React.ReactElement}
 */
const SearchBar = React.forwardRef(
  (
    {
      messages = [],
      onSearch,
      inline = false,
      compact = false,
      placeholder = 'Search messages...',
      className = '',
    },
    ref,
  ) => {
    const [query, setQuery] = useState('')
    const [isOpen, setIsOpen] = useState(false)
    const [results, setResults] = useState([])
    const [suggestions, setSuggestions] = useState([])
    const [showSuggestions, setShowSuggestions] = useState(false)
    const [searchHistory, setSearchHistory] = useState([])
    const [selectedFilters, setSelectedFilters] = useState({
      types: [],
      startDate: null,
      endDate: null,
      tools: [],
      quickFilter: '',
    })
    const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
    const searchInputRef = useRef(null)
    const debounceSearchRef = useRef(null)

    // Initialize debounced search
    useEffect(() => {
      const handleSearch = async (searchQuery, filters) => {
        if (!searchQuery.trim() && !Object.values(filters).some((v) => v)) {
          setResults([])
          onSearch?.({ results: [], query: searchQuery })
          return
        }

        const searchResult = searchMessages(messages, {
          query: searchQuery,
          ...filters,
        })

        setResults(searchResult.results)
        onSearch?.(searchResult)

        // Update suggestions
        const sugg = getSearchSuggestions(messages, searchQuery, 5)
        setSuggestions(sugg)
      }

      debounceSearchRef.current = debounceSearch(handleSearch, 300)
    }, [messages, onSearch])

    // Handle search input change
    const handleQueryChange = useCallback(
      (e) => {
        const newQuery = e.target.value
        setQuery(newQuery)
        setShowSuggestions(true)

        // Perform debounced search
        debounceSearchRef.current?.(newQuery, selectedFilters)
      },
      [selectedFilters],
    )

    // Handle quick filter
    const handleQuickFilter = useCallback((filterName) => {
      const newFilters = {
        ...selectedFilters,
        quickFilter: selectedFilters.quickFilter === filterName ? '' : filterName,
      }
      setSelectedFilters(newFilters)

      if (debounceSearchRef.current) {
        debounceSearchRef.current(query, newFilters)
      }
    }, [query, selectedFilters])

    // Handle type filter
    const handleTypeFilter = useCallback((type) => {
      const newTypes = selectedFilters.types.includes(type)
        ? selectedFilters.types.filter((t) => t !== type)
        : [...selectedFilters.types, type]

      const newFilters = {
        ...selectedFilters,
        types: newTypes,
      }
      setSelectedFilters(newFilters)

      if (debounceSearchRef.current) {
        debounceSearchRef.current(query, newFilters)
      }
    }, [query, selectedFilters])

    // Clear all filters and search
    const handleClear = useCallback(() => {
      setQuery('')
      setSelectedFilters({
        types: [],
        startDate: null,
        endDate: null,
        tools: [],
        quickFilter: '',
      })
      setResults([])
      setShowSuggestions(false)
      onSearch?.({ results: [], query: '' })
      searchInputRef.current?.focus()
    }, [onSearch])

    // Add search to history
    const handleSaveSearch = useCallback(() => {
      if (!query.trim()) return

      setSearchHistory((prev) => {
        const filtered = prev.filter((s) => s.query !== query)
        return [{ query, timestamp: new Date() }, ...filtered].slice(0, 10)
      })
    }, [query])

    // Handle suggestion click
    const handleSuggestionClick = useCallback((suggestion) => {
      setQuery(suggestion)
      setShowSuggestions(false)
      handleSaveSearch()

      if (debounceSearchRef.current) {
        debounceSearchRef.current(suggestion, selectedFilters)
      }
    }, [selectedFilters, handleSaveSearch])

    // Keyboard shortcuts
    useEffect(() => {
      const handleKeydown = (e) => {
        // Cmd+F or Ctrl+F to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
          e.preventDefault()
          searchInputRef.current?.focus()
        }

        // Escape to close
        if (e.key === 'Escape') {
          setIsOpen(false)
          setShowSuggestions(false)
        }
      }

      window.addEventListener('keydown', handleKeydown)
      return () => window.removeEventListener('keydown', handleKeydown)
    }, [])

    const hasFilters = Object.values(selectedFilters).some(
      (v) => v && (Array.isArray(v) ? v.length > 0 : v),
    )
    const hasResults = results.length > 0

    return (
      <div ref={ref} className={`search-bar ${inline ? 'search-bar-inline' : ''} ${className}`.trim()}>
        {/* Search Input */}
        <div className="search-bar-input-container">
          <Search size={18} className="search-bar-icon" />
          <input
            ref={searchInputRef}
            type="text"
            className="search-bar-input"
            placeholder={placeholder}
            value={query}
            onChange={handleQueryChange}
            onFocus={() => {
              setIsOpen(true)
              if (query) setShowSuggestions(true)
            }}
            aria-label="Search messages"
            aria-expanded={isOpen}
          />
          {query && (
            <button
              className="search-bar-clear"
              onClick={handleClear}
              title="Clear search"
              aria-label="Clear search"
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Results Counter */}
        {hasResults && (
          <div className="search-bar-counter">
            {results.length} result{results.length !== 1 ? 's' : ''}
          </div>
        )}

        {/* Quick Filters */}
        {!compact && (
          <div className="search-bar-quick-filters">
            <button
              className={`search-bar-filter ${
                selectedFilters.quickFilter === 'last24h' ? 'active' : ''
              }`}
              onClick={() => handleQuickFilter('last24h')}
              title="Last 24 hours"
            >
              <Clock size={14} />
              <span>24h</span>
            </button>
            <button
              className={`search-bar-filter ${
                selectedFilters.quickFilter === 'last7d' ? 'active' : ''
              }`}
              onClick={() => handleQuickFilter('last7d')}
              title="Last 7 days"
            >
              <Clock size={14} />
              <span>Week</span>
            </button>
            <button
              className={`search-bar-filter ${
                selectedFilters.types.includes('user') ? 'active' : ''
              }`}
              onClick={() => handleTypeFilter('user')}
              title="Your messages"
            >
              <span>👤 You</span>
            </button>
            <button
              className={`search-bar-filter ${
                selectedFilters.types.includes('assistant') ? 'active' : ''
              }`}
              onClick={() => handleTypeFilter('assistant')}
              title="Assistant messages"
            >
              <span>🤖 Assistant</span>
            </button>
            {!compact && (
              <button
                className="search-bar-advanced-toggle"
                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                title="Advanced filters"
              >
                <Settings size={14} />
              </button>
            )}
          </div>
        )}

        {/* Suggestions Dropdown */}
        {isOpen && showSuggestions && suggestions.length > 0 && (
          <div className="search-bar-suggestions">
            <div className="search-bar-suggestions-label">Suggestions</div>
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                className="search-bar-suggestion-item"
                onClick={() => handleSuggestionClick(suggestion)}
              >
                <Search size={14} />
                <span>{suggestion}</span>
              </button>
            ))}
          </div>
        )}

        {/* Search History */}
        {isOpen && !query && searchHistory.length > 0 && (
          <div className="search-bar-history">
            <div className="search-bar-history-label">Recent Searches</div>
            {searchHistory.map((item) => (
              <button
                key={item.timestamp}
                className="search-bar-history-item"
                onClick={() => {
                  setQuery(item.query)
                  if (debounceSearchRef.current) {
                    debounceSearchRef.current(item.query, selectedFilters)
                  }
                  setShowSuggestions(false)
                }}
              >
                <Clock size={14} />
                <span>{item.query}</span>
              </button>
            ))}
          </div>
        )}

        {/* Advanced Filters (Expandable) */}
        {showAdvancedFilters && !compact && (
          <div className="search-bar-advanced-filters">
            <div className="search-bar-filter-group">
              <label className="search-bar-filter-label">Message Type</label>
              <div className="search-bar-filter-options">
                <button
                  className={`search-bar-filter-option ${
                    selectedFilters.types.includes('user') ? 'active' : ''
                  }`}
                  onClick={() => handleTypeFilter('user')}
                >
                  User
                </button>
                <button
                  className={`search-bar-filter-option ${
                    selectedFilters.types.includes('assistant') ? 'active' : ''
                  }`}
                  onClick={() => handleTypeFilter('assistant')}
                >
                  Assistant
                </button>
              </div>
            </div>

            <div className="search-bar-filter-group">
              <label className="search-bar-filter-label">Quick Filters</label>
              <div className="search-bar-filter-options">
                <button
                  className={`search-bar-filter-option ${
                    selectedFilters.quickFilter === 'today' ? 'active' : ''
                  }`}
                  onClick={() => handleQuickFilter('today')}
                >
                  Today
                </button>
                <button
                  className={`search-bar-filter-option ${
                    selectedFilters.quickFilter === 'thisweek' ? 'active' : ''
                  }`}
                  onClick={() => handleQuickFilter('thisweek')}
                >
                  This Week
                </button>
                <button
                  className={`search-bar-filter-option ${
                    selectedFilters.quickFilter === 'thismonth' ? 'active' : ''
                  }`}
                  onClick={() => handleQuickFilter('thismonth')}
                >
                  This Month
                </button>
              </div>
            </div>

            {hasFilters && (
              <button
                className="search-bar-clear-filters"
                onClick={handleClear}
              >
                <AlertCircle size={14} />
                Clear all filters
              </button>
            )}
          </div>
        )}

        {/* No Results Message */}
        {isOpen && query && !hasResults && (
          <div className="search-bar-no-results">
            <MessageSquare size={16} />
            <span>No messages match your search</span>
          </div>
        )}
      </div>
    )
  },
)

SearchBar.displayName = 'SearchBar'

export default SearchBar
