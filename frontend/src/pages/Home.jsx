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
import './Home.css'

const MAX_FILE_SIZE_MB = 10

function HomePage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  
  // Files grid state
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [loadingFiles, setLoadingFiles] = useState(false)

  // Fetch all uploaded shipment files on mount
  const fetchUploadedFiles = async () => {
    setLoadingFiles(true)
    try {
      const response = await api.get('/upload/files')
      setUploadedFiles(response.data.files || [])
    } catch (error) {
      console.error('Failed to fetch uploaded files:', error)
    } finally {
      setLoadingFiles(false)
    }
  }

  useEffect(() => {
    fetchUploadedFiles()
  }, [])

  // Navigate to file data page
  const handleFileClick = (fileId) => {
    navigate(`/shipment-data/${fileId}`)
  }

  // Delete file handler
  const handleDeleteFile = async (e, fileId, filename) => {
    e.stopPropagation() // Prevent card click
    
    // Using native confirm for simplicity, can be replaced with custom modal
    if (!window.confirm(`Are you sure you want to delete "${filename}"?\n\nThis will permanently remove the file and all its associated shipments.`)) {
      return
    }
    
    try {
      await api.delete(`/upload/files/${fileId}`)
      setStatus({ type: 'success', message: `Deleted ${filename}` })
      fetchUploadedFiles() // Refresh list
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
      const response = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      // Check if the backend returned an error status
      if (response.data.status === 'error') {
        setStatus({
          type: 'error',
          message: response.data.message || 'Upload failed. Please try again.'
        })
        return
      }

      const msg = response.data.duplicates_skipped > 0
        ? `${response.data.rows_inserted} rows inserted, ${response.data.duplicates_skipped} duplicates skipped`
        : `${response.data.rows_inserted} rows inserted successfully`

      setStatus({ type: 'success', message: msg })
      setFile(null)
      
      const fileInput = document.getElementById('shipment-file-upload')
      if (fileInput) fileInput.value = ''
      
      // Refresh the files grid
      fetchUploadedFiles()
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.response?.data?.detail || error.response?.data?.message || 'Upload failed. Please try again.',
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
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="home-page">
      <div className="upload-card">
        <div 
          className={`upload-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <UploadCloud className="upload-icon" size={40} />
          <h3>Upload Shipment Excel File</h3>
          <p className="upload-hint">Drag & drop or click to browse</p>
          
          <input 
            type="file" 
            accept=".xlsx" 
            onChange={handleFileChange}
            id="shipment-file-upload"
            style={{ display: 'none' }} 
          />
          
          <label htmlFor="shipment-file-upload" className="btn btn-outline">
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

      <div className="data-card">
        <div className="data-header">
          <h2>Shipment Files</h2>
        </div>

        {loadingFiles ? (
          <FilesGridSkeleton count={4} />
        ) : uploadedFiles.length === 0 ? (
          <div className="empty-state">
            <FileSpreadsheet size={48} className="empty-icon" />
            <p>No shipment files uploaded yet.</p>
            <p className="hint">Upload an Excel file to see it here.</p>
          </div>
        ) : (
          <div className="files-grid">
            {uploadedFiles.map((pf) => (
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
                    {pf.record_count} shipments
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
  )
}

export default HomePage
