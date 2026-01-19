import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api'
import { Search, X, Loader2, Package, User, MapPin, Building2 } from 'lucide-react'
import './SearchAutocomplete.css'

/**
 * Premium Search Autocomplete Component
 * Features:
 * - Debounced API calls
 * - Categorized suggestions with icons
 * - Keyboard navigation
 * - Animated dropdown
 * - Click outside to close
 */
function SearchAutocomplete({ 
  onSearch, 
  placeholder = "Search orders...",
  debounceMs = 250 
}) {
  const [inputValue, setInputValue] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [categories, setCategories] = useState({})
  
  const inputRef = useRef(null)
  const dropdownRef = useRef(null)
  const debounceTimer = useRef(null)

  // Category icons and labels
  const categoryConfig = {
    code: { icon: Package, label: 'الكود', color: '#6366f1' },
    client: { icon: User, label: 'العميل', color: '#10b981' },
    recipient: { icon: MapPin, label: 'المستلم', color: '#f59e0b' },
    city: { icon: Building2, label: 'المدينة', color: '#8b5cf6' }
  }

  // Fetch suggestions with debounce
  const fetchSuggestions = useCallback(async (query) => {
    if (!query || query.length < 1) {
      setSuggestions([])
      setCategories({})
      setIsOpen(false)
      return
    }

    setIsLoading(true)
    try {
      const response = await api.get('/shipments/autocomplete', {
        params: { query, limit: 8 }
      })
      setSuggestions(response.data.suggestions || [])
      setCategories(response.data.categories || {})
      setIsOpen(true)
      setActiveIndex(-1)
    } catch (err) {
      console.error('Autocomplete error:', err)
      setSuggestions([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Handle input change with debounce
  const handleInputChange = (e) => {
    const value = e.target.value
    setInputValue(value)

    // Clear previous timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
    }

    // Set new debounce timer
    debounceTimer.current = setTimeout(() => {
      fetchSuggestions(value)
    }, debounceMs)
  }

  // Handle suggestion selection
  const handleSelect = (suggestion) => {
    setInputValue(suggestion.value)
    setIsOpen(false)
    setSuggestions([])
    onSearch(suggestion.value)
  }

  // Handle form submit
  const handleSubmit = (e) => {
    e.preventDefault()
    setIsOpen(false)
    onSearch(inputValue)
  }

  // Handle clear
  const handleClear = () => {
    setInputValue('')
    setSuggestions([])
    setIsOpen(false)
    onSearch('')
    inputRef.current?.focus()
  }

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) {
      if (e.key === 'Enter') {
        e.preventDefault()
        onSearch(inputValue)
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex(prev => 
          prev < suggestions.length - 1 ? prev + 1 : 0
        )
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex(prev => 
          prev > 0 ? prev - 1 : suggestions.length - 1
        )
        break
      case 'Enter':
        e.preventDefault()
        if (activeIndex >= 0 && suggestions[activeIndex]) {
          handleSelect(suggestions[activeIndex])
        } else {
          setIsOpen(false)
          onSearch(inputValue)
        }
        break
      case 'Escape':
        setIsOpen(false)
        setActiveIndex(-1)
        break
      default:
        break
    }
  }

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        dropdownRef.current && 
        !dropdownRef.current.contains(e.target) &&
        !inputRef.current?.contains(e.target)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Cleanup debounce timer
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
    }
  }, [])

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex >= 0 && dropdownRef.current) {
      const activeItem = dropdownRef.current.querySelector('.suggestion-item.active')
      if (activeItem) {
        activeItem.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [activeIndex])

  // Group suggestions by type for rendering
  const groupedSuggestions = suggestions.reduce((acc, suggestion) => {
    if (!acc[suggestion.type]) {
      acc[suggestion.type] = []
    }
    acc[suggestion.type].push(suggestion)
    return acc
  }, {})

  return (
    <div className="search-autocomplete">
      <form className="autocomplete-form" onSubmit={handleSubmit}>
        <div className="autocomplete-input-wrapper">
          <Search size={18} className="search-icon" />
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setIsOpen(true)}
            placeholder={placeholder}
            autoComplete="off"
            spellCheck="false"
          />
          {isLoading && (
            <Loader2 size={16} className="loading-spinner" />
          )}
          {inputValue && !isLoading && (
            <button 
              type="button" 
              className="clear-input-btn"
              onClick={handleClear}
            >
              <X size={14} />
            </button>
          )}
        </div>
        <button type="submit" className="search-submit-btn">
          Search
        </button>
      </form>

      {/* Suggestions Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div 
          ref={dropdownRef}
          className="suggestions-dropdown"
        >
          {Object.entries(groupedSuggestions).map(([type, items]) => {
            const config = categoryConfig[type]
            const Icon = config?.icon || Package
            
            return (
              <div key={type} className="suggestion-category">
                <div className="category-header">
                  <Icon size={14} style={{ color: config?.color }} />
                  <span>{config?.label || type}</span>
                </div>
                {items.map((suggestion, idx) => {
                  const globalIndex = suggestions.findIndex(s => s === suggestion)
                  return (
                    <button
                      key={`${type}-${idx}`}
                      className={`suggestion-item ${globalIndex === activeIndex ? 'active' : ''}`}
                      onClick={() => handleSelect(suggestion)}
                      onMouseEnter={() => setActiveIndex(globalIndex)}
                    >
                      <span className="suggestion-value">{suggestion.value}</span>
                      <span className="suggestion-count">{suggestion.count}</span>
                    </button>
                  )
                })}
              </div>
            )
          })}
          
          {/* Quick tip */}
          <div className="dropdown-tip">
            <kbd>↑</kbd><kbd>↓</kbd> Navigate • <kbd>Enter</kbd> Select • <kbd>Esc</kbd> Close
          </div>
        </div>
      )}

      {/* No results */}
      {isOpen && inputValue.length >= 1 && !isLoading && suggestions.length === 0 && (
        <div ref={dropdownRef} className="suggestions-dropdown no-results">
          <div className="no-results-message">
            <Search size={20} />
            <span>No suggestions for "{inputValue}"</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default SearchAutocomplete
