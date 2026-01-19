import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { ChevronLeft, ChevronRight, ChevronFirst, ChevronLast, Package, DollarSign, Filter, X, Loader2, AlertCircle, Check, Calendar, ChevronDown, Trash2, Pencil, Edit3, BarChart3 } from 'lucide-react'
import { getStatusColor } from '../constants/statuses'
import TableSkeleton from '../components/TableSkeleton'
import SearchAutocomplete from '../components/SearchAutocomplete'
import './AllOrders.css'

const PAGE_SIZE = 100

function AllOrdersPage() {
  const navigate = useNavigate()
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentPage, setCurrentPage] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  
  // Filter states
  const [priceTypeFilter, setPriceTypeFilter] = useState('')
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  
  // Date filter states
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  
  // Stats
  const [stats, setStats] = useState({ totalOrders: 0, totalPrice: 0 })
  
  // Get unique price types for filter dropdown
  const [priceTypes, setPriceTypes] = useState([])
  
  // Status update state
  const [updatingStatus, setUpdatingStatus] = useState(null)
  const [openDropdown, setOpenDropdown] = useState(null) // Track which row has open dropdown
  
  // Stats popup state
  const [showStatsPopup, setShowStatsPopup] = useState(false)
  const [statusCounts, setStatusCounts] = useState({})
  const [statusMessage, setStatusMessage] = useState(null)

  // Row selection state
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [isEditMode, setIsEditMode] = useState(false)
  
  // Delete confirmation modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState({ code: '', amount: '', description: '' })

  const fetchShipments = async (page = 0, search = '', dateFromVal = '', dateToVal = '') => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE }
      if (search) params.search = search
      if (dateFromVal) params.date_from = dateFromVal
      if (dateToVal) params.date_to = dateToVal
      
      const response = await api.get('/shipments', { params })
      setShipments(response.data.data || [])
      setTotalCount(response.data.total || 0)
      
      // Extract unique price types
      const types = [...new Set(response.data.data.map(s => s['نوع السعر']).filter(Boolean))]
      setPriceTypes(prev => {
        const combined = [...new Set([...prev, ...types])]
        return combined
      })
    } catch (err) {
      console.error('Failed to fetch shipments:', err)
      setError(err.response?.data?.detail || 'Failed to load orders')
      setShipments([])
    } finally {
      setLoading(false)
    }
  }

  // Fetch stats (total orders and total price) - now respects date filters
  // Excludes "مرتجع" orders from total price calculation
  const fetchStats = async (dateFromVal = '', dateToVal = '') => {
    try {
      const params = { limit: 1 }
      if (dateFromVal) params.date_from = dateFromVal
      if (dateToVal) params.date_to = dateToVal
      
      // Get filtered shipments count
      const response = await api.get('/shipments', { params })
      setStats(prev => ({ ...prev, totalOrders: response.data.total || 0 }))
      
      // For total price, fetch more data with same filters
      const allParams = { limit: 1000 }
      if (dateFromVal) allParams.date_from = dateFromVal
      if (dateToVal) allParams.date_to = dateToVal
      
      const allData = await api.get('/shipments', { params: allParams })
      // Exclude "مرتجع" orders from total price
      const total = allData.data.data
        .filter(s => s['الحالة'] !== 'مرتجع')
        .reduce((sum, s) => sum + (s['قيمة الطرد'] || 0), 0)
      setStats(prev => ({ ...prev, totalPrice: total }))
      
      // Calculate status counts for popup
      const counts = {}
      allData.data.data.forEach(s => {
        const status = s['الحالة'] || 'غير معروف'
        counts[status] = (counts[status] || 0) + 1
      })
      setStatusCounts(counts)
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  // Available statuses for dropdown - fetched from backend
  const [availableStatuses, setAvailableStatuses] = useState([])

  // Fetch status constants from backend (single source of truth)
  const fetchStatuses = async () => {
    try {
      const response = await api.get('/statuses')
      setAvailableStatuses(response.data.target_statuses || [])
    } catch (err) {
      console.error('Failed to fetch statuses:', err)
      // Fallback to empty array - status dropdown will show nothing
    }
  }

  // Update shipment status
  const updateStatus = async (shipmentCode, newStatus, previousStatus, orderValue) => {
    setUpdatingStatus(shipmentCode)
    setStatusMessage(null)
    setOpenDropdown(null)
    try {
      await api.patch(`/shipments/${encodeURIComponent(shipmentCode)}/status?new_status=${encodeURIComponent(newStatus)}`)
      
      // Update local state
      setShipments(prev => prev.map(s => 
        s['الكود'] === shipmentCode ? { ...s, 'الحالة': newStatus } : s
      ))
      
      // Update stats: if changing TO "مرتجع", deduct value; if changing FROM "مرتجع", add value back
      if (newStatus === 'مرتجع' && previousStatus !== 'مرتجع') {
        setStats(prev => ({ ...prev, totalPrice: prev.totalPrice - (orderValue || 0) }))
      } else if (previousStatus === 'مرتجع' && newStatus !== 'مرتجع') {
        setStats(prev => ({ ...prev, totalPrice: prev.totalPrice + (orderValue || 0) }))
      }
      
      // Update status counts
      setStatusCounts(prev => ({
        ...prev,
        [previousStatus]: Math.max(0, (prev[previousStatus] || 0) - 1),
        [newStatus]: (prev[newStatus] || 0) + 1
      }))
      
      setStatusMessage({ type: 'success', text: `تم تحديث الحالة إلى "${newStatus}"` })
      setTimeout(() => setStatusMessage(null), 3000)
    } catch (err) {
      console.error('Failed to update status:', err)
      setStatusMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'فشل في تحديث الحالة' 
      })
    } finally {
      setUpdatingStatus(null)
    }
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.status-dropdown-container')) {
        setOpenDropdown(null)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  useEffect(() => {
    fetchShipments(currentPage, searchTerm, dateFrom, dateTo)
  }, [currentPage, searchTerm, dateFrom, dateTo])

  useEffect(() => {
    fetchStats(dateFrom, dateTo)
    fetchStatuses() // Fetch available statuses from backend
  }, [dateFrom, dateTo])

  // Handle search from autocomplete component
  const handleSearch = (value) => {
    setSearchTerm(value)
    setCurrentPage(0)
  }

  const clearFilters = () => {
    setPriceTypeFilter('')
    setAmountMin('')
    setAmountMax('')
    setDateFrom('')
    setDateTo('')
  }

  // Selection handlers
  const toggleSelect = (code) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(code)) {
        newSet.delete(code)
      } else {
        newSet.add(code)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredShipments.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredShipments.map(s => s['الكود'])))
    }
  }

  const clearSelection = () => {
    setSelectedIds(new Set())
  }

  // Delete handlers with single confirmation
  const handleDeleteClick = () => {
    setShowDeleteModal(true)
  }

  const handleConfirmDelete = async () => {
    setIsDeleting(true)
    try {
      const deletePromises = Array.from(selectedIds).map(code =>
        api.delete(`/shipments/${encodeURIComponent(code)}`)
      )
      await Promise.all(deletePromises)
      
      setStatusMessage({ type: 'success', text: `تم حذف ${selectedIds.size} طلبات بنجاح` })
      setTimeout(() => setStatusMessage(null), 3000)
      
      // Clear selection and refresh data
      clearSelection()
      fetchShipments(currentPage, searchTerm, dateFrom, dateTo)
      fetchStats(dateFrom, dateTo)
    } catch (err) {
      console.error('Failed to delete shipments:', err)
      setStatusMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'فشل في حذف الطلبات' 
      })
    } finally {
      setIsDeleting(false)
      setShowDeleteModal(false)
    }
  }

  const cancelDelete = () => {
    setShowDeleteModal(false)
  }

  // Edit handlers - only works when exactly 1 item is selected
  const handleEditClick = () => {
    if (selectedIds.size !== 1) return
    const code = Array.from(selectedIds)[0]
    const shipment = filteredShipments.find(s => s['الكود'] === code)
    if (shipment) {
      setEditData({
        code: code,
        amount: shipment['قيمة الطرد'] || '',
        description: shipment['الوصف'] || ''
      })
      setShowEditModal(true)
    }
  }

  const handleConfirmEdit = async () => {
    setIsEditing(true)
    try {
      const params = new URLSearchParams()
      if (editData.amount !== '') params.append('amount', editData.amount)
      if (editData.description !== '') params.append('description', editData.description)
      
      await api.patch(`/shipments/${encodeURIComponent(editData.code)}?${params.toString()}`)
      
      setStatusMessage({ type: 'success', text: 'تم تحديث الطلب بنجاح' })
      setTimeout(() => setStatusMessage(null), 3000)
      
      // Refresh data
      clearSelection()
      fetchShipments(currentPage, searchTerm, dateFrom, dateTo)
      fetchStats(dateFrom, dateTo)
    } catch (err) {
      console.error('Failed to edit shipment:', err)
      setStatusMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'فشل في تحديث الطلب' 
      })
    } finally {
      setIsEditing(false)
      setShowEditModal(false)
    }
  }

  const cancelEdit = () => {
    setShowEditModal(false)
  }

  // Apply client-side filters
  const filteredShipments = useMemo(() => {
    return shipments.filter(s => {
      // Price type filter
      if (priceTypeFilter && s['نوع السعر'] !== priceTypeFilter) {
        return false
      }
      // Amount range filter
      const amount = s['قيمة الطرد'] || 0
      if (amountMin && amount < parseFloat(amountMin)) {
        return false
      }
      if (amountMax && amount > parseFloat(amountMax)) {
        return false
      }
      return true
    })
  }, [shipments, priceTypeFilter, amountMin, amountMax])

  const hasActiveFilters = priceTypeFilter || amountMin || amountMax || dateFrom || dateTo

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="all-orders-page">
      {/* Status Message Toast */}
      {statusMessage && (
        <div className={`status-toast ${statusMessage.type}`}>
          {statusMessage.type === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Stats Popup */}
      {showStatsPopup && (
        <div className="stats-popup-overlay" onClick={() => setShowStatsPopup(false)}>
          <div className="stats-popup" onClick={(e) => e.stopPropagation()}>
            <div className="stats-popup-header">
              <h3>توزيع الطلبات حسب الحالة</h3>
              <button className="close-popup-btn" onClick={() => setShowStatsPopup(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="stats-popup-content">
              {Object.entries(statusCounts).map(([status, count]) => (
                <div key={status} className="status-count-row">
                  <span className={`badge badge-${getStatusColor(status)}`}>{status}</span>
                  <span className="status-count-value">{count.toLocaleString()}</span>
                </div>
              ))}
              {Object.keys(statusCounts).length > 0 && (
                <div className="status-count-row delivery-percentage">
                  <span className="percentage-label">نسبة التسليم</span>
                  <span className="percentage-value">
                    {(() => {
                      const totalOrders = Object.values(statusCounts).reduce((sum, c) => sum + c, 0)
                      const delivered = statusCounts['تم التسليم'] || 0
                      const percentage = totalOrders > 0 ? ((delivered / totalOrders) * 100).toFixed(1) : 0
                      return `${percentage}%`
                    })()}
                  </span>
                </div>
              )}
              {Object.keys(statusCounts).length === 0 && (
                <p className="no-data">لا توجد بيانات</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat-item clickable" onClick={() => setShowStatsPopup(true)}>
          <div className="stat-icon">
            <Package size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Total Orders</span>
            <span className="stat-value">{stats.totalOrders.toLocaleString()}</span>
          </div>
        </div>
        <div className="stat-item">
          <div className="stat-icon">
            <DollarSign size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Total Value</span>
            <span className="stat-value">{stats.totalPrice.toLocaleString()} EGP</span>
          </div>
        </div>
        <div className="stat-item clickable analytics-card" onClick={() => navigate('/analytics')}>
          <div className="stat-icon">
            <BarChart3 size={20} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Analytics</span>
            <span className="stat-value">View Dashboard</span>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="controls-bar">
        <SearchAutocomplete 
          onSearch={handleSearch}
          placeholder="Search by code, client, recipient, city..."
          debounceMs={200}
        />

        <button 
          className={`filter-toggle ${showFilters ? 'active' : ''}`}
          onClick={() => setShowFilters(!showFilters)}
        >
          <Filter size={16} />
          <span>Filters</span>
          {hasActiveFilters && <span className="filter-badge">•</span>}
        </button>

        <button 
          className={`edit-mode-btn ${isEditMode ? 'active' : ''}`}
          onClick={() => {
            setIsEditMode(!isEditMode)
            if (isEditMode) {
              clearSelection() // Clear selection when exiting edit mode
            }
          }}
          title={isEditMode ? 'Exit edit mode' : 'Enter edit mode'}
        >
          <Pencil size={16} />
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

          {/* Date Filter */}
          <div className="filter-group date-filter-group">
            <label>
              <Calendar size={14} />
              التاريخ (Date Filter)
            </label>
            <div className="date-inputs">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                title="From date"
              />
              <span>to</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                title="To date"
                min={dateFrom}
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

      {/* Error State */}
      {error && (
        <div className="error-message">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button onClick={() => fetchShipments(currentPage, searchTerm, dateFrom, dateTo)}>Retry</button>
        </div>
      )}

      {/* Table */}
      <div className="table-card">
        {loading ? (
          <TableSkeleton rows={8} />
        ) : filteredShipments.length === 0 ? (
          <div className="empty-state">
            <Package size={48} />
            <p>{hasActiveFilters ? 'No orders match your filters' : 'No orders found'}</p>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="orders-table">
                <thead>
                  <tr>
                    {isEditMode && (
                      <th className="checkbox-cell">
                        <input
                          type="checkbox"
                          className="row-checkbox"
                          checked={selectedIds.size > 0 && selectedIds.size === filteredShipments.length}
                          onChange={toggleSelectAll}
                        />
                      </th>
                    )}
                    <th>الكود</th>
                    <th>التاريخ</th>
                    <th>العميل</th>
                    <th>الوصف</th>
                    <th>الحالة</th>
                    <th>المستلم</th>
                    <th>المدينة</th>
                    <th>قيمة الطرد</th>
                    <th>نوع السعر</th>
                    <th>الوزن</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredShipments.map((shipment) => (
                    <tr 
                      key={shipment['الكود'] || Math.random()}
                      className={selectedIds.has(shipment['الكود']) ? 'row-selected' : ''}
                    >
                      {isEditMode && (
                        <td className="checkbox-cell">
                          <input
                            type="checkbox"
                            className="row-checkbox"
                            checked={selectedIds.has(shipment['الكود'])}
                            onChange={() => toggleSelect(shipment['الكود'])}
                          />
                        </td>
                      )}
                      <td><span className="code">{shipment['الكود']}</span></td>
                      <td className="date-cell">{shipment['التاريخ']}</td>
                      <td className="client-cell">{shipment['العميل']}</td>
                      <td>{shipment['الوصف']}</td>
                      <td className="status-cell">
                        <div className="status-dropdown-container">
                          {updatingStatus === shipment['الكود'] ? (
                            <Loader2 size={16} className="spin" />
                          ) : (
                            <>
                              <button
                                className={`status-dropdown-trigger badge badge-${getStatusColor(shipment['الحالة'])}`}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setOpenDropdown(openDropdown === shipment['الكود'] ? null : shipment['الكود'])
                                }}
                              >
                                {shipment['الحالة']}
                                <ChevronDown size={14} />
                              </button>
                              {openDropdown === shipment['الكود'] && (
                                <div className="status-dropdown-menu">
                                  {availableStatuses
                                    .filter(status => status !== shipment['الحالة'])
                                    .map(status => (
                                      <button
                                        key={status}
                                        className={`status-dropdown-item badge-${getStatusColor(status)}`}
                                        onClick={() => updateStatus(
                                          shipment['الكود'], 
                                          status, 
                                          shipment['الحالة'], 
                                          shipment['قيمة الطرد']
                                        )}
                                      >
                                        {status}
                                      </button>
                                    ))}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                      <td>{shipment['المستلم']}</td>
                      <td>{shipment['مدينة المستلم']}</td>
                      <td className="amount-cell">{shipment['قيمة الطرد']}</td>
                      <td>{shipment['نوع السعر']}</td>
                      <td className="weight-cell">{shipment['الوزن']}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="table-footer">
              <div className="pagination">
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(0)}
                  disabled={currentPage === 0}
                >
                  <ChevronFirst size={18} strokeWidth={2} color="#ffffff" />
                </button>
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                >
                  <ChevronLeft size={18} strokeWidth={2} color="#ffffff" />
                </button>
                <span className="page-info">
                  Page {currentPage + 1} of {totalPages}
                </span>
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={currentPage >= totalPages - 1}
                >
                  <ChevronRight size={18} strokeWidth={2} color="#ffffff" />
                </button>
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(totalPages - 1)}
                  disabled={currentPage >= totalPages - 1}
                >
                  <ChevronLast size={18} strokeWidth={2} color="#ffffff" />
                </button>
              </div>
              <span className="results-info">
                {currentPage * PAGE_SIZE + 1}-{Math.min((currentPage + 1) * PAGE_SIZE, totalCount)} of {totalCount}
                {hasActiveFilters && ` (${filteredShipments.length} shown after filters)`}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Floating Selection Action Bar */}
      {selectedIds.size > 0 && (
        <div className="selection-action-bar">
          <button className="close-selection-btn" onClick={clearSelection}>
            <X size={18} />
          </button>
          <span className="selection-count">{selectedIds.size}</span>
          <span className="selection-text">items selected</span>
          {selectedIds.size === 1 && (
            <button className="edit-selected-btn" onClick={handleEditClick}>
              <Edit3 size={16} />
              Edit
            </button>
          )}
          <button className="delete-selected-btn" onClick={handleDeleteClick}>
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="delete-modal-overlay" onClick={cancelDelete}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="delete-modal-header danger">
              <Trash2 size={24} className="danger-icon" />
              <h3>تأكيد الحذف</h3>
            </div>
            <div className="delete-modal-content">
              <p>هل أنت متأكد من حذف <strong>{selectedIds.size}</strong> طلبات؟</p>
              <p className="warning-text">هذا الإجراء لا يمكن التراجع عنه.</p>
            </div>
            <div className="delete-modal-actions">
              <button className="cancel-btn" onClick={cancelDelete} disabled={isDeleting}>إلغاء</button>
              <button className="danger-btn" onClick={handleConfirmDelete} disabled={isDeleting}>
                {isDeleting ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}
                حذف
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && (
        <div className="delete-modal-overlay" onClick={cancelEdit}>
          <div className="delete-modal edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="delete-modal-header edit">
              <Edit3 size={24} className="edit-icon" />
              <h3>تعديل الطلب</h3>
            </div>
            <div className="delete-modal-content">
              <p className="edit-code">الكود: <strong>{editData.code}</strong></p>
              <div className="edit-form">
                <label>
                  قيمة الطرد (Amount)
                  <input 
                    type="number" 
                    value={editData.amount} 
                    onChange={(e) => setEditData(prev => ({ ...prev, amount: e.target.value }))}
                    placeholder="0.00"
                  />
                </label>
                <label>
                  الوصف (Description)
                  <textarea 
                    value={editData.description} 
                    onChange={(e) => setEditData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Enter description..."
                    rows={3}
                  />
                </label>
              </div>
            </div>
            <div className="delete-modal-actions">
              <button className="cancel-btn" onClick={cancelEdit} disabled={isEditing}>إلغاء</button>
              <button className="primary-btn" onClick={handleConfirmEdit} disabled={isEditing}>
                {isEditing ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
                حفظ
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AllOrdersPage
