import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { 
  UploadCloud, 
  CheckCircle, 
  AlertCircle, 
  Loader2, 
  FileSpreadsheet,
  Trash2
} from 'lucide-react'
import FilesGridSkeleton from '../components/FilesGridSkeleton'
import './PaymentProcessing.css'

const MAX_FILE_SIZE_MB = 10

function PaymentProcessingPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  
  // Files grid state
  const [paymentFiles, setPaymentFiles] = useState([])
  const [loadingFiles, setLoadingFiles] = useState(false)

  // Fetch all payment files on mount
  const fetchPaymentFiles = async () => {
    setLoadingFiles(true)
    try {
      const response = await api.get('/payments/files')
      setPaymentFiles(response.data.files || [])
    } catch (error) {
      console.error('Failed to fetch payment files:', error)
    } finally {
      setLoadingFiles(false)
    }
  }

  useEffect(() => {
    fetchPaymentFiles()
  }, [])

  // Navigate to file data page
  const handleFileClick = (fileId) => {
    navigate(`/payment-data/${fileId}`)
  }

  // Delete file handler
  const handleDeleteFile = async (e, fileId, filename) => {
    e.stopPropagation() // Prevent card click
    
    if (!window.confirm(`Are you sure you want to delete "${filename}"?\n\nThis will permanently remove the file and all its records.`)) {
      return
    }
    
    try {
      await api.delete(`/payments/files/${fileId}`)
      setStatus({ type: 'success', message: `Deleted ${filename}` })
      fetchPaymentFiles() // Refresh list
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to delete file'
      })
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      handleFileSelection(droppedFile)
    }
  }

  const handleFileSelection = (selectedFile) => {
    const fileSizeMB = selectedFile.size / (1024 * 1024)
    if (fileSizeMB > MAX_FILE_SIZE_MB) {
      setStatus({
        type: 'error',
        message: `File too large (${fileSizeMB.toFixed(1)}MB). Maximum size is ${MAX_FILE_SIZE_MB}MB.`
      })
      return
    }
    
    if (!selectedFile.name.endsWith('.xlsx')) {
      setStatus({
        type: 'error',
        message: 'Invalid file type. Only .xlsx files are allowed.'
      })
      return
    }
    
    setFile(selectedFile)
    setStatus(null)
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setLoading(true)
    setStatus(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await api.post('/payments/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      setStatus({ 
        type: 'success', 
        message: `${response.data.rows_inserted} rows uploaded successfully!` 
      })
      setFile(null)
      
      const fileInput = document.getElementById('payment-file-upload')
      if (fileInput) fileInput.value = ''
      
      // Refresh the files grid
      fetchPaymentFiles()
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Upload failed. Please try again.',
      })
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleDateString('ar-EG', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    })
  }

  return (
    <div className="payment-page">
      <h1 className="page-title">💳 Payment Processing</h1>
      
      {/* Upload Section */}
      <div className="upload-card">
        <div 
          className={`upload-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <UploadCloud className="upload-icon" size={40} />
          <h3>Upload Payment Excel File</h3>
          <p className="upload-hint">Drag & drop or click to browse</p>
          
          <input 
            type="file" 
            accept=".xlsx" 
            onChange={handleFileChange}
            id="payment-file-upload"
            style={{ display: 'none' }} 
          />
          
          <label htmlFor="payment-file-upload" className="btn btn-outline">
            {file ? `${file.name}` : "Browse Files"}
          </label>
          <p className="upload-limit">Maximum size: {MAX_FILE_SIZE_MB}MB • .xlsx only</p>
        </div>

        {file && (
          <button className="btn btn-primary btn-large" onClick={handleUpload} disabled={loading}>
            {loading ? <><Loader2 className="spin" size={16}/> Uploading...</> : 'Upload to Database'}
          </button>
        )}

        {status && (
          <div className={`alert ${status.type}`}>
            {status.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            <span>{status.message}</span>
          </div>
        )}
      </div>

      {/* Files Grid */}
      <div className="content-section">
        <div className="files-section">
          <h2>📁 Uploaded Files</h2>
          
          {loadingFiles ? (
            <FilesGridSkeleton count={4} />
          ) : paymentFiles.length === 0 ? (
            <div className="empty-state">
              <FileSpreadsheet size={48} className="empty-icon" />
              <p>No payment files uploaded yet.</p>
              <p className="hint">Upload an Excel file to get started.</p>
            </div>
          ) : (
            <div className="files-grid">
              {paymentFiles.map((pf) => (
                <div 
                  key={pf.id} 
                  className="file-card"
                  onClick={() => handleFileClick(pf.id)}
                >
                  <div className="file-icon">
                    <FileSpreadsheet size={40} />
                  </div>
                  <div className="file-info">
                    <h4 className="file-name" title={pf.filename}>
                      {pf.filename}
                    </h4>
                    <p className="file-meta">
                      {pf.record_count} records
                    </p>
                    <p className="file-date">
                      {formatDate(pf.upload_date)}
                    </p>
                  </div>
                  <button 
                    className="delete-btn"
                    onClick={(e) => handleDeleteFile(e, pf.id, pf.filename)}
                    title="Delete file"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PaymentProcessingPage
