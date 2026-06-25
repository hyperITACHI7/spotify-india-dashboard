import { useState } from 'react';

export default function TrendLineChart({ trend }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!trend || trend.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', marginBottom: '24px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No trend data available.</p>
      </div>
    );
  }

  // Dimensions
  const width = 700;
  const height = 260;
  const paddingLeft = 40;
  const paddingRight = 30;
  const paddingTop = 30;
  const paddingBottom = 40;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  const N = trend.length;

  // X & Y scalers
  // Sentiment ranges from -1.0 to +1.0
  const getX = (index) => {
    if (N <= 1) return paddingLeft + chartWidth / 2;
    return paddingLeft + (index / (N - 1)) * chartWidth;
  };

  const getY = (score) => {
    // Clamp score
    const clamped = Math.max(-1, Math.min(1, score));
    // -1 is at bottom (paddingTop + chartHeight), +1 is at top (paddingTop)
    return paddingTop + chartHeight - ((clamped - (-1)) / 2) * chartHeight;
  };

  // Build SVG path strings
  let pathD = '';
  let areaD = '';
  const points = [];

  trend.forEach((point, i) => {
    const x = getX(i);
    const y = getY(point.avg_sentiment);
    points.push({ x, y, ...point, index: i });

    if (i === 0) {
      pathD = `M ${x} ${y}`;
      areaD = `M ${x} ${paddingTop + chartHeight} L ${x} ${y}`;
    } else {
      pathD += ` L ${x} ${y}`;
      areaD += ` L ${x} ${y}`;
    }

    if (i === N - 1) {
      areaD += ` L ${x} ${paddingTop + chartHeight} Z`;
    }
  });

  return (
    <div className="card" style={{ marginBottom: '24px', display: 'flex', flexDirection: 'column', minHeight: '320px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Sentiment Trend Over Time</h3>
          <p style={{ fontSize: '11px', color: 'var(--text-subdued)' }}>Track release performance across active updates</p>
        </div>
        
        {/* Sentiment Scale Legend */}
        <div style={{ display: 'flex', gap: '16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
          <span style={{ color: 'var(--spotify-green)' }}>+1.0 Positive</span>
          <span style={{ color: '#f1c40f' }}>0.0 Neutral</span>
          <span style={{ color: '#e74c3c' }}>-1.0 Negative</span>
        </div>
      </div>

      <div style={{ position: 'relative', width: '100%', flex: 1 }}>
        <svg 
          viewBox={`0 0 ${width} ${height}`} 
          width="100%" 
          height="100%"
          style={{ overflow: 'visible' }}
        >
          {/* Gradients */}
          <defs>
            <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--spotify-green)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--spotify-green)" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={paddingLeft} y1={getY(1)} x2={width - paddingRight} y2={getY(1)} stroke="var(--divider)" strokeWidth={1} strokeDasharray="4 4" />
          <line x1={paddingLeft} y1={getY(0)} x2={width - paddingRight} y2={getY(0)} stroke="var(--divider)" strokeWidth={1.5} />
          <line x1={paddingLeft} y1={getY(-1)} x2={width - paddingRight} y2={getY(-1)} stroke="var(--divider)" strokeWidth={1} strokeDasharray="4 4" />

          {/* Grid Labels */}
          <text x={paddingLeft - 10} y={getY(1) + 4} fill="var(--text-subdued)" fontSize="10" textAnchor="end">+1.0</text>
          <text x={paddingLeft - 10} y={getY(0) + 4} fill="var(--text-subdued)" fontSize="10" textAnchor="end">0.0</text>
          <text x={paddingLeft - 10} y={getY(-1) + 4} fill="var(--text-subdued)" fontSize="10" textAnchor="end">-1.0</text>

          {/* Release Date Markers (Vertical dashed lines and text labels) */}
          {points.map((p) => {
            if (p.is_release) {
              return (
                <g key={`release-${p.date}`}>
                  <line 
                    x1={p.x} 
                    y1={paddingTop - 10} 
                    x2={p.x} 
                    y2={paddingTop + chartHeight} 
                    stroke="var(--spotify-green)" 
                    strokeWidth={1.5} 
                    strokeDasharray="2 2" 
                  />
                  <rect
                    x={p.x - 45}
                    y={paddingTop - 20}
                    width={90}
                    height={16}
                    rx={3}
                    fill="var(--spotify-green)"
                  />
                  <text
                    x={p.x}
                    y={paddingTop - 9}
                    fill="#000"
                    fontSize="9"
                    fontWeight="900"
                    textAnchor="middle"
                  >
                    {p.is_release.split(' ')[0]} {/* e.g. v9.0.2 */}
                  </text>
                </g>
              );
            }
            return null;
          })}

          {/* Area under the line */}
          {N > 1 && (
            <path d={areaD} fill="url(#area-gradient)" />
          )}

          {/* Line Path */}
          {N > 1 && (
            <path d={pathD} fill="none" stroke="var(--spotify-green)" strokeWidth={3} />
          )}

          {/* Interactive Node Circles */}
          {points.map((p) => (
            <circle
              key={p.date}
              cx={p.x}
              cy={p.y}
              r={hoveredPoint && hoveredPoint.date === p.date ? 6 : 4}
              fill={p.is_release ? 'var(--spotify-green)' : 'var(--text-base)'}
              stroke="var(--bg-base)"
              strokeWidth={1.5}
              style={{ cursor: 'pointer', transition: 'r 0.1s ease' }}
              onMouseEnter={() => setHoveredPoint(p)}
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}

          {/* Date Axis (Shows first, middle, last dates for spacing) */}
          {points.length > 0 && (
            <>
              <text x={paddingLeft} y={height - 15} fill="var(--text-subdued)" fontSize="10" textAnchor="middle">
                {points[0].date}
              </text>
              {points.length > 2 && (
                <text x={paddingLeft + chartWidth / 2} y={height - 15} fill="var(--text-subdued)" fontSize="10" textAnchor="middle">
                  {points[Math.floor(points.length / 2)].date}
                </text>
              )}
              <text x={width - paddingRight} y={height - 15} fill="var(--text-subdued)" fontSize="10" textAnchor="middle">
                {points[points.length - 1].date}
              </text>
            </>
          )}
        </svg>

        {/* Hover Tooltip Widget */}
        {hoveredPoint && (
          <div style={{
            position: 'absolute',
            left: `${((hoveredPoint.x) / width) * 100}%`,
            top: `${((hoveredPoint.y - 65) / height) * 100}%`,
            transform: 'translateX(-50%)',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--divider)',
            borderRadius: '6px',
            padding: '8px 12px',
            boxShadow: '0 8px 16px rgba(0,0,0,0.5)',
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: '120px'
          }}>
            <p style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', marginBottom: '4px' }}>
              {hoveredPoint.date}
            </p>
            <p style={{ fontSize: '13px', fontWeight: '900', color: 'var(--text-base)' }}>
              Sentiment: <span style={{ color: hoveredPoint.avg_sentiment > 0.15 ? 'var(--spotify-green)' : (hoveredPoint.avg_sentiment < -0.15 ? '#e74c3c' : '#f1c40f') }}>
                {hoveredPoint.avg_sentiment > 0 ? `+${hoveredPoint.avg_sentiment}` : hoveredPoint.avg_sentiment}
              </span>
            </p>
            <p style={{ fontSize: '11px', color: 'var(--text-subdued)' }}>
              Avg Rating: ⭐ {hoveredPoint.avg_rating.toFixed(1)}
            </p>
            {hoveredPoint.is_release && (
              <p style={{ fontSize: '10px', color: 'var(--spotify-green)', fontWeight: '700', marginTop: '4px' }}>
                🚀 {hoveredPoint.is_release}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
