import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { 
  ArrowLeft, MapPin, BarChart3, 
  Package, DollarSign, Percent, User, Loader2, AlertCircle 
} from 'lucide-react'
import './Analytics.css'

function AnalyticsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hoveredStatus, setHoveredStatus] = useState(null)
  const [hoveredTrend, setHoveredTrend] = useState(null)
  const [cursorPosition, setCursorPosition] = useState({ x: 0, y: 0 })

  useEffect(() => {
    fetchAnalytics()
  }, [])

  const fetchAnalytics = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get('/api/analytics')
      console.log('Analytics response:', response.data)
      
      // Handle response - create defaults if empty
      const responseData = response.data || {}
      setData({
        status_distribution: responseData.status_distribution || [],
        top_cities: responseData.top_cities || [],
        daily_trends: responseData.daily_trends || [],
        summary: responseData.summary || {
          total_shipments: 0,
          total_value: 0,
          delivery_rate: 0,
          delivered_count: 0,
          top_client: null,
          top_client_count: 0
        }
      })
    } catch (err) {
      console.error('Failed to fetch analytics:', err)
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to load analytics'
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // Calculate max for scaling charts
  const maxCityCount = useMemo(() => {
    if (!data?.top_cities || data.top_cities.length === 0) return 1
    return Math.max(...data.top_cities.map(c => c.count), 1)
  }, [data])

  const maxDailyCount = useMemo(() => {
    if (!data?.daily_trends || data.daily_trends.length === 0) return 1
    return Math.max(...data.daily_trends.map(d => d.count), 1)
  }, [data])

  // Helper to generate smooth SVG path from data points
  const getSmoothPath = (points, height, width) => {
    if (!points || points.length === 0) return ''

    // Helper to get coordinates
    const getCoords = (index) => {
      const point = points[index]
      const x = (index / (points.length - 1)) * width
      const y = height - (point.count / maxDailyCount) * height
      return [x, y]
    }

    // Start path
    const [startX, startY] = getCoords(0)
    let d = `M ${startX} ${startY}`

    // Add curve segments
    for (let i = 0; i < points.length - 1; i++) {
      const [x0, y0] = getCoords(i)
      const [x1, y1] = getCoords(i + 1)
      
      // Control points for smooth curve (cubic bezier)
      // Use 20% of the distance as control point offset
      const cp1x = x0 + (x1 - x0) * 0.2
      const cp1y = y0 
      const cp2x = x1 - (x1 - x0) * 0.2
      const cp2y = y1 

      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x1} ${y1}`
    }

    return d
  }

  // Status colors mapping
  const getStatusChartColor = (status) => {
    const colorMap = {
      'تم التسليم': '#22c55e',
      'تسليم جزئي': '#84cc16',
      'مرتجع': '#ef4444',
      'قيد التوصيل': '#3b82f6',
      'تم الاستلام بالمخزن': '#8b5cf6',
      'طلب شحن': '#f59e0b',
      'طلب الشحن': '#f59e0b',
      'مؤجل': '#6b7280'
    }
    return colorMap[status] || '#6b7280'
  }

  if (loading) {
    return (
      <div className="analytics-page">
        <div className="analytics-loading">
          <Loader2 size={48} className="spin" />
          <p>Loading analytics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="analytics-page">
        <div className="analytics-error">
          <AlertCircle size={48} />
          <p>{error}</p>
          <button onClick={fetchAnalytics}>Retry</button>
        </div>
      </div>
    )
  }

  return (
    <div className="analytics-page">
      {/* Header */}
      <div className="analytics-header">
        <button className="back-btn" onClick={() => navigate('/all-orders')}>
          <ArrowLeft size={20} />
          <span>Back to Orders</span>
        </button>
        <h1>
          <BarChart3 size={28} />
          Dashboard Analytics
        </h1>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-icon">
            <Package size={24} />
          </div>
          <div className="summary-info">
            <span className="summary-label">Total Shipments</span>
            <span className="summary-value">{(data?.summary?.total_shipments || 0).toLocaleString()}</span>
          </div>
        </div>
        
        <div className="summary-card">
          <div className="summary-icon accent">
            <DollarSign size={24} />
          </div>
          <div className="summary-info">
            <span className="summary-label">Total Value</span>
            <span className="summary-value">{(data?.summary?.total_value || 0).toLocaleString()} EGP</span>
          </div>
        </div>
        
        <div className="summary-card">
          <div className="summary-icon success">
            <Percent size={24} />
          </div>
          <div className="summary-info">
            <span className="summary-label">Delivery Rate</span>
            <span className="summary-value">{data?.summary?.delivery_rate || 0}%</span>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Status Distribution */}
        <div className="chart-card">
          <div className="chart-header">
            <h3>Status Distribution</h3>
            <span className="chart-subtitle">Shipments by status</span>
          </div>
          <div className="chart-content">
            {data?.status_distribution?.length > 0 ? (
              <>
                <div className="pie-chart-container donut-chart-container">
                  <svg viewBox="0 0 200 200" className="pie-chart donut-chart">
                    {(() => {
                      const total = data.status_distribution.reduce((sum, s) => sum + s.count, 0)
                      if (total === 0) return null
                      let currentAngle = 0
                      
                      // Sort by count for better visual
                      const sortedData = [...data.status_distribution].sort((a, b) => b.count - a.count)
                      
                      return sortedData.map((item, idx) => {
                        const percentage = (item.count / total) * 100
                        const angle = (percentage / 100) * 360
                        
                        const startAngle = currentAngle
                        const endAngle = currentAngle + angle
                        currentAngle = endAngle
                        
                        // Donut calculation
                        const innerRadius = 55
                        const outerRadius = 90
                        const hoverRadius = 95 // Expanded on hover
                        
                        const isHovered = hoveredStatus?.status === item.status
                        const radius = isHovered ? hoverRadius : outerRadius
                        
                        const startRad = (startAngle - 90) * (Math.PI / 180)
                        const endRad = (endAngle - 90) * (Math.PI / 180)
                        
                        // Outer arc
                        const x1 = 100 + radius * Math.cos(startRad)
                        const y1 = 100 + radius * Math.sin(startRad)
                        const x2 = 100 + radius * Math.cos(endRad)
                        const y2 = 100 + radius * Math.sin(endRad)
                        
                        // Inner arc
                        const x3 = 100 + innerRadius * Math.cos(endRad)
                        const y3 = 100 + innerRadius * Math.sin(endRad)
                        const x4 = 100 + innerRadius * Math.cos(startRad)
                        const y4 = 100 + innerRadius * Math.sin(startRad)
                        
                        const largeArc = angle > 180 ? 1 : 0
                        
                        const pathData = [
                          `M ${x1} ${y1}`,
                          `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
                          `L ${x3} ${y3}`,
                          `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${x4} ${y4}`,
                          'Z'
                        ].join(' ')
                        
                        return (
                          <g key={idx} 
                             onMouseEnter={() => setHoveredStatus({ ...item, percentage })}
                             onMouseLeave={() => setHoveredStatus(null)}
                             style={{ cursor: 'pointer' }}
                          >
                            <path 
                              d={pathData}
                              fill={getStatusChartColor(item.status)}
                              className="donut-segment"
                              style={{ 
                                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                filter: isHovered ? 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))' : 'none',
                                opacity: hoveredStatus && !isHovered ? 0.6 : 1
                              }}
                            />
                          </g>
                        )
                      })
                    })()}
                    
                    {/* Center Text */}
                    <foreignObject x="40" y="40" width="120" height="120" style={{ pointerEvents: 'none' }}>
                      <div className="donut-center-text">
                        {hoveredStatus ? (
                          <>
                            <span className="center-value">{Math.round(hoveredStatus.percentage)}%</span>
                            <span className="center-label">{hoveredStatus.status}</span>
                          </>
                        ) : (
                          <>
                            <span className="center-value">{data.status_distribution.reduce((a,b) => a + b.count, 0)}</span>
                            <span className="center-label">Total</span>
                          </>
                        )}
                      </div>
                    </foreignObject>
                  </svg>
                </div>
                <div className="chart-legend">
                  {data.status_distribution.slice(0, 5).map((item, idx) => (
                    <div 
                      key={idx} 
                      className="legend-item"
                      onMouseEnter={() => {
                        const total = data.status_distribution.reduce((sum, s) => sum + s.count, 0)
                        setHoveredStatus({ ...item, percentage: (item.count / total) * 100 })
                      }}
                      onMouseLeave={() => setHoveredStatus(null)}
                      style={{ 
                        opacity: hoveredStatus && hoveredStatus.status !== item.status ? 0.5 : 1,
                        cursor: 'pointer'
                      }}
                    >
                      <span 
                        className="legend-dot" 
                        style={{ background: getStatusChartColor(item.status) }}
                      />
                      <span className="legend-label">{item.status}</span>
                      <span className="legend-value">{item.count}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="no-data">No status data available</div>
            )}
          </div>
        </div>

        {/* Top Cities */}
        <div className="chart-card">
          <div className="chart-header">
            <h3>Top Shipping Cities</h3>
            <span className="chart-subtitle">Most frequent destinations</span>
          </div>
          <div className="chart-content">
            {data?.top_cities?.length > 0 ? (
              <div className="bar-chart">
                {data.top_cities.slice(0, 8).map((city, idx) => (
                  <div key={idx} className="bar-item">
                    <div className="bar-label">
                      <MapPin size={14} />
                      <span>{city.city}</span>
                    </div>
                    <div className="bar-track">
                      <div 
                        className="bar-fill"
                        style={{ 
                          width: `${(city.count / maxCityCount) * 100}%`,
                          background: `hsl(${220 - idx * 15}, 70%, 55%)`
                        }}
                      />
                    </div>
                    <span className="bar-value">{city.count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">No city data available</div>
            )}
          </div>
        </div>

        {/* Daily Trends - Area Chart */}
        <div className="chart-card wide">
          <div className="chart-header">
            <h3>Daily Shipment Trends</h3>
            <span className="chart-subtitle">
              {data?.daily_trends?.length > 0 
                ? `${new Date(data.daily_trends[0].date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${new Date(data.daily_trends[data.daily_trends.length - 1].date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
                : 'Last 30 days'}
            </span>
          </div>
          <div className="chart-content">
            <div className="trend-chart-container">
              {data?.daily_trends?.length > 0 ? (
                <div 
                  className="area-chart-wrapper"
                  onMouseMove={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect()
                    const x = e.clientX - rect.left
                    const totalPoints = data.daily_trends.length
                    const index = Math.min(
                      Math.max(0, Math.floor((x / rect.width) * totalPoints)),
                      totalPoints - 1
                    )
                    setHoveredTrend({ ...data.daily_trends[index], index })
                    setCursorPosition({ x, y: e.clientY - rect.top })
                  }}
                  onMouseLeave={() => setHoveredTrend(null)}
                >
                  <svg 
                    viewBox="0 0 800 200" 
                    className="area-chart" 
                    preserveAspectRatio="none"
                  >
                    <defs>
                      <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
                      </linearGradient>
                    </defs>

                    {/* Grid lines (horizontal) */}
                    {[0, 1, 2, 3, 4].map(i => (
                      <line 
                        key={i} 
                        x1="0" 
                        y1={i * 50} 
                        x2="800" 
                        y2={i * 50} 
                        stroke="hsl(var(--border))" 
                        strokeWidth="1" 
                        strokeDasharray="4 4" 
                        opacity="0.5"
                      />
                    ))}

                    {/* Area path */}
                    <path
                      d={`${getSmoothPath(data.daily_trends, 200, 800)} L 800 200 L 0 200 Z`}
                      fill="url(#chartGradient)"
                    />

                    {/* Line path */}
                    <path
                      d={getSmoothPath(data.daily_trends, 200, 800)}
                      fill="none"
                      stroke="hsl(var(--primary))"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />

                    {/* Active Point */}
                    {hoveredTrend && (
                      <circle
                        cx={(hoveredTrend.index / (data.daily_trends.length - 1)) * 800}
                        cy={200 - (hoveredTrend.count / maxDailyCount) * 200}
                        r="6"
                        fill="hsl(var(--background))"
                        stroke="hsl(var(--primary))"
                        strokeWidth="3"
                        className="chart-point active"
                      />
                    )}
                  </svg>
                  
                  {/* Tooltip */}
                  {hoveredTrend && (
                    <div 
                      className="chart-tooltip"
                      style={{ 
                        left: `${(hoveredTrend.index / (data.daily_trends.length - 1)) * 100}%`,
                        top: `${Math.max(10, 200 - (hoveredTrend.count / maxDailyCount) * 200 - 60)}px` 
                      }}
                    >
                      <div className="tooltip-date">
                        {new Date(hoveredTrend.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </div>
                      <div className="tooltip-value">
                        <div className="tooltip-dot"></div>
                        <span>Shipments:</span>
                        <span className="count">{hoveredTrend.count}</span>
                      </div>
                    </div>
                  )}

                  {/* X-Axis Labels */}
                  <div className="chart-x-axis">
                    {data.daily_trends.map((day, idx) => (
                      idx % Math.ceil(data.daily_trends.length / 8) === 0 && (
                        <div 
                          key={idx} 
                          className="x-label"
                          style={{ left: `${(idx / (data.daily_trends.length - 1)) * 100}%` }}
                        >
                          {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </div>
                      )
                    ))}
                  </div>
                </div>
              ) : (
                <div className="no-data">No trend data available for the last 30 days</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AnalyticsPage
