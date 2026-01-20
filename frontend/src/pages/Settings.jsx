
import { useState, useEffect } from 'react'
import api from '../api'
import { Settings, Trash2, RotateCcw, AlertCircle, Check, Loader2, ChevronFirst, ChevronLeft, ChevronRight, ChevronLast, Database } from 'lucide-react'
import TableSkeleton from '../components/TableSkeleton'
import { getStatusColor } from '../constants/statuses'
import './RecycleBin.css' // We can reuse the table styles or import specific ones
import './Settings.css'

const PAGE_SIZE = 50

function SettingsPage() {
  const [activeTab, setActiveTab] = useState('recycle-bin')
  
  // Recycle Bin State
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
    if (activeTab === 'recycle-bin') {
      fetchDeleted(currentPage)
    }
  }, [currentPage, activeTab])

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
    <div className="settings-page">
      <div className="settings-header">
        <Settings size={28} />
        <h2>Settings</h2>
      </div>

      <div className="settings-section">
        <div className="settings-section-title">
          <Database size={20} />
          <span>Data Management</span>
        </div>

        <div className="settings-table-card">
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Trash2 size={18} />
            <span style={{ fontWeight: 500 }}>Recycle Bin</span>
            <span className="results-info" style={{ marginLeft: 'auto' }}>
              {totalCount} deleted items
            </span>
          </div>

          {statusMessage && (
            <div className={`status-toast ${statusMessage.type}`} style={{ position: 'fixed', bottom: '24px', right: '24px' }}>
              {statusMessage.type === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
              <span>{statusMessage.text}</span>
            </div>
          )}

          {loading ? (
            <div style={{ padding: '1rem' }}><TableSkeleton rows={5} /></div>
          ) : deletedShipments.length === 0 ? (
            <div className="empty-state" style={{ padding: '3rem' }}>
              <Trash2 size={40} />
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
                      <th>Desc</th>
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
                          {shipment['تاريخ الحذف'] ? new Date(shipment['تاريخ الحذف']).toLocaleDateString() : '-'}
                        </td>
                        <td className="client-cell">{shipment['العميل']}</td>
                        <td>
                          <span className={`badge badge-${getStatusColor(shipment['الحالة'])}`}>
                            {shipment['الحالة']}
                          </span>
                        </td>
                        <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {shipment['الوصف']}
                        </td>
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
    </div>
  )
}

export default SettingsPage
