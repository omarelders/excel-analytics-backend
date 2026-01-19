function TableSkeleton({ rows = 5 }) {
  return (
    <div className="table-wrapper">
      <table className="modern-table">
        <thead>
          <tr>
            <th><div className="skeleton" style={{ width: '60px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '80px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '90px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '100px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '70px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '85px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '75px', height: '12px' }}></div></th>
            <th><div className="skeleton" style={{ width: '60px', height: '12px' }}></div></th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i}>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '70px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '110px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '95px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '150px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '80px', borderRadius: '12px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '90px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '85px' }}></div></td>
              <td><div className="skeleton" style={{ width: '100%', height: '14px', maxWidth: '65px' }}></div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default TableSkeleton
