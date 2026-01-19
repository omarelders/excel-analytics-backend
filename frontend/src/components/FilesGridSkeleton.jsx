function FilesGridSkeleton({ count = 6 }) {
  return (
    <div className="files-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="file-card-skeleton">
          <div className="skeleton" style={{ width: '40px', height: '40px', borderRadius: '8px' }}></div>
          <div style={{ flex: 1 }}>
            <div className="skeleton" style={{ width: '80%', height: '16px', marginBottom: '8px' }}></div>
            <div className="skeleton" style={{ width: '60%', height: '12px', marginBottom: '8px' }}></div>
            <div className="skeleton" style={{ width: '40%', height: '12px' }}></div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default FilesGridSkeleton
