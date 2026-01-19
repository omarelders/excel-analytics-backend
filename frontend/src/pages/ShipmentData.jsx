import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import { 
  ArrowLeft, 
  Search, 
  Loader2, 
  AlertCircle, 
  X,
  ChevronLeft,
  ChevronRight,
  ChevronFirst,
  ChevronLast,
  Package,
  Filter,
  RefreshCw,
} from 'lucide-react'
import { getStatusColor } from '../constants/statuses'
import './ShipmentData.css'

const PAGE_SIZE = 20

function ShipmentDataPage() {
  const { fileId } = useParams()
  const navigate = useNavigate()
  
  // Data state
  const [filename, setFilename] = useState('')
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  
  // Search state
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  
  // Filter states
  const [statusFilter, setStatusFilter] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [statuses, setStatuses] = useState([])
  
  const fetchData = async (page = 0, search = '') => {
    setLoading(true)
    setError(null)
    try {
      const params = { 
        limit: PAGE_SIZE, 
        offset: page * PAGE_SIZE 
      }
      if (search) params.search = search
      
      const response = await api.get(`/shipments/file/${fileId}`, { params })
      setFilename(response.data.filename)
      setRecords(response.data.data || [])
      setTotalCount(response.data.total || 0)
      
      // Extract unique statuses for filter
      const uniqueStatuses = [...new Set(response.data.data.map(r => r['الحالة']).filter(Boolean))]
      setStatuses(prev => {
        const combined = [...new Set([...prev, ...uniqueStatuses])]
        return combined
      })
    } catch (err) {
      console.error('Failed to fetch shipment data:', err)
      setError(err.response?.data?.detail || 'Failed to load data')
      setRecords([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(currentPage, searchTerm)
  }, [fileId, currentPage, searchTerm])

  const handleSearch = (e) => {
    e.preventDefault()
    setSearchTerm(searchInput)
    setCurrentPage(0)
  }

  const clearSearch = () => {
    setSearchInput('')
    setSearchTerm('')
    setCurrentPage(0)
  }

  const clearFilters = () => {
    setStatusFilter('')
  }

  // Apply client-side filters
  const filteredRecords = useMemo(() => {
    return records.filter(r => {
      // Status filter
      if (statusFilter && r['الحالة'] !== statusFilter) {
        return false
      }
      return true
    })
  }, [records, statusFilter])

  const hasActiveFilters = statusFilter

  // Columns to display
  const columns = [
    'الكود',
    'التاريخ',
    'العميل',
    'الوصف',
    'الحالة',
    'المستلم',
    'مدينة المستلم',
    'قيمة الطرد',
    'الوزن',
    'نوع السعر'
  ]

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="shipment-data-page">
      {/* Header */}
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate('/')}>
          <ArrowLeft size={18} />
          <span>Back to Files</span>
        </button>
        <h1>{filename || 'Shipment Data'}</h1>
      </div>

      {/* Controls Bar */}
      <div className="controls-bar">
        <form className="search-bar" onSubmit={handleSearch}>
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by code, client, recipient..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          {searchTerm && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearSearch}>
              <X size={16} />
            </button>
          )}
          <button type="submit" className="btn btn-primary btn-sm">Search</button>
        </form>
        
        <button 
          className={`filter-toggle ${showFilters ? 'active' : ''}`}
          onClick={() => setShowFilters(!showFilters)}
        >
          <Filter size={16} />
          <span>Filters</span>
          {hasActiveFilters && <span className="filter-badge">•</span>}
        </button>

        <button 
          className="refresh-btn" 
          onClick={() => fetchData(currentPage, searchTerm)}
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="filter-panel">
          <div className="filter-group">
            <label>الحالة (Status)</label>
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All</option>
              {statuses.map(status => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </div>

          {hasActiveFilters && (
            <button className="clear-filters-btn" onClick={clearFilters}>
              <X size={14} />
              Clear Filters
            </button>
          )}
        </div>
      )}
        
      {searchTerm && (
        <div className="search-info">
          Showing results for: <strong>"{searchTerm}"</strong>
        </div>
      )}

      {/* Data Table */}
      <div className="data-section">
        {error && (
          <div className="alert error">
            <AlertCircle size={16} />
            <span>{error}</span>
            <button className="btn btn-outline btn-sm" onClick={() => fetchData(currentPage, searchTerm)}>
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <div className="loading-state">
            <Loader2 className="spin" size={32} />
            <p>Loading data...</p>
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="empty-state">
            <Package size={48} />
            <p>{hasActiveFilters ? 'No records match your filters' : (searchTerm ? `No records match "${searchTerm}"` : 'No records in this file')}</p>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="modern-table">
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.map((record, idx) => (
                    <tr key={idx}>
                      {columns.map((col) => (
                        <td key={col}>
                          {col === 'الحالة' && record[col] ? (
                            <span className={`badge badge-${getStatusColor(record[col])}`}>
                              {record[col]}
                            </span>
                          ) : (
                            record[col] ?? '-'
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 0 && (
              <div className="table-footer">
                <div className="table-pagination">
                  <button 
                    className="pagination-btn"
                    onClick={() => setCurrentPage(0)}
                    disabled={currentPage === 0}
                  >
                    <ChevronFirst size={18} />
                  </button>
                  <button 
                    className="pagination-btn"
                    onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                    disabled={currentPage === 0}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <button 
                    className="pagination-btn"
                    onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={currentPage >= totalPages - 1}
                  >
                    <ChevronRight size={18} />
                  </button>
                  <button 
                    className="pagination-btn"
                    onClick={() => setCurrentPage(totalPages - 1)}
                    disabled={currentPage >= totalPages - 1}
                  >
                    <ChevronLast size={18} />
                  </button>
                </div>
                <span className="table-info">
                  {currentPage * PAGE_SIZE + 1}-{Math.min((currentPage + 1) * PAGE_SIZE, totalCount)} من {totalCount}
                  {hasActiveFilters && ` (${filteredRecords.length} shown after filters)`}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default ShipmentDataPage
