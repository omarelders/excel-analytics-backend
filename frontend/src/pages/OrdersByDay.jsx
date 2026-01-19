import { useState, useEffect } from 'react'
import api from '../api'
import { Calendar, Search, Loader2, AlertCircle, X } from 'lucide-react'
import { getStatusColor } from '../constants/statuses'
import TableSkeleton from '../components/TableSkeleton'
import './OrdersByDay.css'

function OrdersByDayPage() {
  const [days, setDays] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(false)
  const [daysLoading, setDaysLoading] = useState(true)
  const [daysError, setDaysError] = useState(null)
  const [ordersError, setOrdersError] = useState(null)
  const [searchDate, setSearchDate] = useState('')
  const [searchError, setSearchError] = useState('')
  
  // Global search state
  const [globalSearch, setGlobalSearch] = useState('')
  const [globalSearchInput, setGlobalSearchInput] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [isSearchMode, setIsSearchMode] = useState(false)

  // Fetch available days on mount
  useEffect(() => {
    fetchDays()
  }, [])

  // Fetch orders when date changes (only if not in search mode)
  useEffect(() => {
    if (selectedDate && !isSearchMode) {
      fetchOrders(selectedDate)
    }
  }, [selectedDate, isSearchMode])

  const fetchDays = async () => {
    setDaysLoading(true)
    setDaysError(null)
    try {
      const res = await api.get('/shipments/days')
      const daysList = res.data.days || []
      setDays(daysList)
      // Auto-select most recent day
      if (daysList.length > 0) {
        setSelectedDate(daysList[0])
      }
    } catch (err) {
      console.error('Failed to fetch days:', err)
      setDaysError(err.response?.data?.detail || 'Failed to load shipping days')
    } finally {
      setDaysLoading(false)
    }
  }

  const fetchOrders = async (date) => {
    setLoading(true)
    setOrdersError(null)
    try {
      const res = await api.get(`/shipments/by-day?date=${date}`)
      setOrders(res.data.data || [])
    } catch (err) {
      console.error('Failed to fetch orders:', err)
      setOrdersError(err.response?.data?.detail || 'Failed to load orders')
      setOrders([])
    } finally {
      setLoading(false)
    }
  }

  // Global search function
  const handleGlobalSearch = async (e) => {
    e.preventDefault()
    if (!globalSearchInput || globalSearchInput.length < 2) {
      setSearchError('Search must be at least 2 characters')
      return
    }
    
    setSearchError('')
    setGlobalSearch(globalSearchInput)
    setIsSearchMode(true)
    setSearchLoading(true)
    
    try {
      const res = await api.get(`/shipments/search?query=${encodeURIComponent(globalSearchInput)}`)
      setSearchResults(res.data.data || [])
    } catch (err) {
      console.error('Search failed:', err)
      setSearchError(err.response?.data?.detail || 'Search failed')
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }

  const clearSearch = () => {
    setGlobalSearch('')
    setGlobalSearchInput('')
    setSearchResults([])
    setIsSearchMode(false)
    setSearchError('')
    // Re-fetch orders for selected date
    if (selectedDate) {
      fetchOrders(selectedDate)
    }
  }

  // Validate date format (YYYY-MM-DD)
  const isValidDate = (dateStr) => {
    if (!dateStr) return false
    const regex = /^\d{4}-\d{2}-\d{2}$/
    if (!regex.test(dateStr)) return false
    
    const date = new Date(dateStr)
    return date instanceof Date && !isNaN(date)
  }

  const handleDateSearch = (e) => {
    e.preventDefault()
    setSearchError('')
    
    if (!searchDate) {
      setSearchError('Please enter a date')
      return
    }
    
    if (!isValidDate(searchDate)) {
      setSearchError('Invalid date format. Use YYYY-MM-DD')
      return
    }
    
    setIsSearchMode(false)
    setSelectedDate(searchDate)
  }

  const handleDayClick = (day) => {
    setIsSearchMode(false)
    setGlobalSearch('')
    setGlobalSearchInput('')
    setSelectedDate(day)
  }

  const formatDisplayDate = (dateStr) => {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
  }

  // Determine which data to display
  const displayData = isSearchMode ? searchResults : orders
  const isDataLoading = isSearchMode ? searchLoading : loading

  return (
    <div className="orders-page">
      <div className="page-header">
        <h1>Orders by Day</h1>
        
        <div className="header-controls">
          {/* Global Search */}
          <form className="global-search" onSubmit={handleGlobalSearch}>
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search all orders..."
              value={globalSearchInput}
              onChange={(e) => {
                setGlobalSearchInput(e.target.value)
                setSearchError('')
              }}
            />
            {isSearchMode && (
              <button type="button" className="clear-btn" onClick={clearSearch}>
                <X size={16} />
              </button>
            )}
            <button type="submit" className="search-btn">Search</button>
          </form>
          
          {/* Day Search */}
          <form className="day-search" onSubmit={handleDateSearch}>
            <input
              type="date"
              value={searchDate}
              onChange={(e) => {
                setSearchDate(e.target.value)
                setSearchError('')
              }}
            />
            <button type="submit">
              <Calendar size={16} />
            </button>
          </form>
        </div>
      </div>
      
      {searchError && (
        <div className="search-error">
          <AlertCircle size={14} />
          <span>{searchError}</span>
        </div>
      )}
      
      {isSearchMode && (
        <div className="search-mode-banner">
          <span>Showing results for: <strong>"{globalSearch}"</strong></span>
          <button onClick={clearSearch}>Clear Search</button>
        </div>
      )}

      {/* Day Tabs - hide when in search mode */}
      {!isSearchMode && (
        <div className="day-tabs">
          {daysLoading ? (
            <div className="loading-days">
              <Loader2 size={16} className="spin" />
              <span>Loading days...</span>
            </div>
          ) : daysError ? (
            <div className="days-error">
              <AlertCircle size={16} />
              <span>{daysError}</span>
              <button onClick={fetchDays} className="retry-btn">Retry</button>
            </div>
          ) : days.length === 0 ? (
            <div className="no-days">No shipping days found</div>
          ) : (
            days.map((day) => (
              <button
                key={day}
                className={`day-tab ${selectedDate === day ? 'active' : ''}`}
                onClick={() => handleDayClick(day)}
              >
                <Calendar size={14} />
                <span>{formatDisplayDate(day)}</span>
              </button>
            ))
          )}
        </div>
      )}

      {/* Orders Table */}
      <div className="orders-section">
        {isDataLoading ? (
          <TableSkeleton rows={10} />
        ) : ordersError && !isSearchMode ? (
          <div className="error-state">
            <AlertCircle size={24} />
            <p>{ordersError}</p>
            <button onClick={() => fetchOrders(selectedDate)} className="retry-btn">
              Retry
            </button>
          </div>
        ) : displayData.length === 0 ? (
          <div className="empty-state">
            <Calendar size={48} />
            <p>
              {isSearchMode 
                ? `No orders found for "${globalSearch}"` 
                : `No orders for ${selectedDate || 'selected date'}`
              }
            </p>
          </div>
        ) : (
          <div className="table-container">
            <table className="orders-table">
              <thead>
                <tr>
                  {Object.keys(displayData[0]).map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayData.map((order) => (
                  <tr key={order['الكود'] || Math.random()}>
                    {Object.entries(order).map(([key, val], i) => (
                      <td key={i}>
                        {key === 'الحالة' ? (
                          <span className={`badge badge-${getStatusColor(val)}`}>{val}</span>
                        ) : (
                          val
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        
        {!isDataLoading && displayData.length > 0 && (
          <div className="orders-count">
            {displayData.length} orders {isSearchMode ? 'found' : ''}
          </div>
        )}
      </div>
    </div>
  )
}

export default OrdersByDayPage
