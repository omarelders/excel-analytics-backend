
import { useState, useEffect } from 'react'
import api from '../api'
import { Trash2, RotateCcw, AlertCircle, Check, Loader2, ChevronFirst, ChevronLeft, ChevronRight, ChevronLast, Package } from 'lucide-react'
import TableSkeleton from '../components/TableSkeleton'
import { getStatusColor } from '../constants/statuses'
import './RecycleBin.css'

const PAGE_SIZE = 50

function RecycleBinPage() {
  const [deletedShipments, setDeletedShipments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentPage, setCurrentPage] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [restoringId, setRestoringId] = useState(null)
  const [statusMessage, setStatusMessage] = useState(null)

  const fetchDeleted = async (page = 0) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE }
      const response = await api.get('/shipments/deleted', { params })
      setDeletedShipments(response.data.data || [])
      setTotalCount(response.data.total || 0)
    } catch (err) {
      console.error('Failed to fetch deleted shipments:', err)
      setError('Failed to load deleted items')
      setDeletedShipments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDeleted(currentPage)
  }, [currentPage])

  const handleRestore = async (code) => {
    setRestoringId(code)
    try {
      await api.post(`/shipments/${encodeURIComponent(code)}/restore`)
      
      setStatusMessage({ type: 'success', text: `Shipment ${code} restored successfully` })
      setTimeout(() => setStatusMessage(null), 3000)
      
      // Refresh list
      fetchDeleted(currentPage)
    } catch (err) {
      console.error('Failed to restore shipment:', err)
      setStatusMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'Failed to restore shipment' 
      })
    } finally {
      setRestoringId(null)
    }
  }

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="recycle-bin-page">
      <div className="page-header">
        <h2>
          <Trash2 className="icon" size={24} />
          Recycle Bin
        </h2>
        <span className="results-info">
          {totalCount} deleted items found
        </span>
      </div>

      {statusMessage && (
        <div className={`status-toast ${statusMessage.type}`}>
          {statusMessage.type === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      <div className="table-card">
        {loading ? (
          <TableSkeleton rows={8} />
        ) : deletedShipments.length === 0 ? (
          <div className="empty-state">
            <Trash2 size={48} />
            <p>Recycle bin is empty</p>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="orders-table">
                <thead>
                  <tr>
                    <th>Actions</th>
                    <th>Code</th>
                    <th>Deleted At</th>
                    <th>Client</th>
                    <th>Status</th>
                    <th>Recipient</th>
                    <th>City</th>
                    <th>Amount</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {deletedShipments.map((shipment) => (
                    <tr key={shipment['الكود']}>
                      <td style={{ width: '100px' }}>
                        <button 
                          className="restore-btn"
                          onClick={() => handleRestore(shipment['الكود'])}
                          disabled={restoringId === shipment['الكود']}
                        >
                          {restoringId === shipment['الكود'] ? (
                            <Loader2 size={14} className="spin" />
                          ) : (
                            <RotateCcw size={14} />
                          )}
                          Restore
                        </button>
                      </td>
                      <td><span className="code">{shipment['الكود']}</span></td>
                      <td className="date-cell">
                        {shipment['تاريخ الحذف'] ? new Date(shipment['تاريخ الحذف']).toLocaleString() : '-'}
                      </td>
                      <td className="client-cell">{shipment['العميل']}</td>
                      <td>
                        <span className={`badge badge-${getStatusColor(shipment['الحالة'])}`}>
                          {shipment['الحالة']}
                        </span>
                      </td>
                      <td>{shipment['المستلم']}</td>
                      <td>{shipment['مدينة المستلم']}</td>
                      <td className="amount-cell">{shipment['قيمة الطرد']}</td>
                      <td>{shipment['الوصف']}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="table-footer">
                <div className="pagination">
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
                  <span className="page-info">
                    Page {currentPage + 1} of {totalPages}
                  </span>
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
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default RecycleBinPage
