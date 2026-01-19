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
  DollarSign,
  CreditCard,
  Package,
  Filter,
  RefreshCw,
  Calculator,
  TrendingUp
} from 'lucide-react'
import { getStatusColor } from '../constants/statuses'
import './PaymentData.css'

const PAGE_SIZE = 20

function PaymentDataPage() {
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
  const [priceTypeFilter, setPriceTypeFilter] = useState('')
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [priceTypes, setPriceTypes] = useState([])
  
  // Stats state
  const [totals, setTotals] = useState({
    delivery_value: 0,
    due_fees: 0,
    net_package_price: 0,
    amount_due: 0,
    net_due: 0
  })

  const fetchData = async (page = 0, search = '') => {
    setLoading(true)
    setError(null)
    try {
      const params = { 
        limit: PAGE_SIZE, 
        offset: page * PAGE_SIZE 
      }
      if (search) params.search = search
      
      const response = await api.get(`/payments/files/${fileId}/data`, { params })
      setFilename(response.data.filename)
      setRecords(response.data.data || [])
      setTotalCount(response.data.total || 0)
      setTotals(response.data.totals || {
        delivery_value: 0,
        due_fees: 0,
        net_package_price: 0,
        amount_due: 0,
        net_due: 0
      })
      
      // Extract unique price types for filter
      const types = [...new Set(response.data.data.map(r => r['نوع السعر']).filter(Boolean))]
      setPriceTypes(prev => {
        const combined = [...new Set([...prev, ...types])]
        return combined
      })
    } catch (err) {
      console.error('Failed to fetch payment data:', err)
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
    setPriceTypeFilter('')
    setAmountMin('')
    setAmountMax('')
  }

  // Apply client-side filters
  const filteredRecords = useMemo(() => {
    return records.filter(r => {
      // Price type filter
      if (priceTypeFilter && r['نوع السعر'] !== priceTypeFilter) {
        return false
      }
      // Amount range filter (using قيمة الطرد)
      const amount = r['قيمة الطرد'] || 0
      if (amountMin && amount < parseFloat(amountMin)) {
        return false
      }
      if (amountMax && amount > parseFloat(amountMax)) {
        return false
      }
      return true
    })
  }, [records, priceTypeFilter, amountMin, amountMax])

  const hasActiveFilters = priceTypeFilter || amountMin || amountMax

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '0.00'
    return Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })
  }

  // Columns to hide from display
  const hiddenColumns = [
    'العميل',
    'سبب الإرجاع',
    'نوع الطلب',
    'تاريخ التسليم/الإلغاء',
    'قيمة المرتجع',
    'عدد المحاولات',
    'تاريخ التوصيل',
    'تم الإلغاء',
    'تاريخ أخر حركة',
    'سداد مستحقات العملاء',
    'ملاحظات',
    'نوع المرتجع للراسل',
    'مندوب الشحن',
    'تم التحصيل',
    'تم السداد للعميل',
    'الرمز البريدي للراسل',
    'الرقم المرجعي',
    'الرمز البريدي للمستلم',
    'هاتف المستلم',
    'الفرع',
    'فرع المنشأ',
    'الخدمة',
    'اسم الراسل'
  ]

  const getColumns = () => {
    if (records.length === 0) return []
    return Object.keys(records[0]).filter(col => !hiddenColumns.includes(col))
  }

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="payment-data-page">
      {/* Header */}
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate('/payment-processing')}>
          <ArrowLeft size={18} />
          <span>Back to Files</span>
        </button>
        <h1>{filename || 'Payment Data'}</h1>
      </div>

      {/* Stats Cards */}
      <div className="stats-row">
        <div className="stat-card delivery">
          <div className="stat-icon">
            <Package size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">قيمة التسليم</span>
            <span className="stat-value">{formatCurrency(totals.delivery_value)}</span>
          </div>
        </div>
        
        <div className="stat-card fees">
          <div className="stat-icon">
            <CreditCard size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">الرسوم المستحقة</span>
            <span className="stat-value">{formatCurrency(totals.due_fees)}</span>
          </div>
        </div>
        
        <div className="stat-card net">
          <div className="stat-icon">
            <DollarSign size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">صافي سعر الطرد</span>
            <span className="stat-value">{formatCurrency(totals.net_package_price)}</span>
          </div>
        </div>
        
        <div className="stat-card amount-due">
          <div className="stat-icon">
            <Calculator size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">المستحق</span>
            <span className="stat-value">{formatCurrency(totals.amount_due)}</span>
          </div>
        </div>
        
        <div className="stat-card net-due">
          <div className="stat-icon">
            <TrendingUp size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">صافي المستحق</span>
            <span className="stat-value">{formatCurrency(totals.net_due)}</span>
          </div>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="controls-bar">
        <form className="search-bar" onSubmit={handleSearch}>
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by code, recipient, sender, client..."
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
            <label>نوع السعر (Price Type)</label>
            <select 
              value={priceTypeFilter} 
              onChange={(e) => setPriceTypeFilter(e.target.value)}
            >
              <option value="">All</option>
              {priceTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>قيمة الطرد (Amount Range)</label>
            <div className="range-inputs">
              <input
                type="number"
                placeholder="Min"
                value={amountMin}
                onChange={(e) => setAmountMin(e.target.value)}
              />
              <span>-</span>
              <input
                type="number"
                placeholder="Max"
                value={amountMax}
                onChange={(e) => setAmountMax(e.target.value)}
              />
            </div>
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
                    {getColumns().map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.map((record, idx) => (
                    <tr key={idx}>
                      {getColumns().map((col) => (
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

export default PaymentDataPage
