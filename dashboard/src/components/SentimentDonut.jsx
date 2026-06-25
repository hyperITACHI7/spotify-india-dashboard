import { useState } from 'react';

export default function SentimentDonut({ distribution }) {
  const { POSITIVE = 0, NEUTRAL = 0, NEGATIVE = 0 } = distribution;
  const total = POSITIVE + NEUTRAL + NEGATIVE;
  const [hoveredSegment, setHoveredSegment] = useState(null);

  if (total === 0) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '280px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No sentiment data available.</p>
      </div>
    );
  }

  const positivePercent = Math.round((POSITIVE / total) * 100);
  const neutralPercent = Math.round((NEUTRAL / total) * 100);
  const negativePercent = Math.round((NEGATIVE / total) * 100);

  // SVG parameters
  const size = 180;
  const strokeWidth = 24;
  const center = size / 2;
  const radius = (size - strokeWidth) / 2; // 78
  const circumference = 2 * Math.PI * radius; // ~490.09

  // Calculate segment details
  const segments = [
    { key: 'POSITIVE', label: 'Positive', count: POSITIVE, percent: positivePercent, color: 'var(--spotify-green)', value: POSITIVE },
    { key: 'NEUTRAL', label: 'Neutral', count: NEUTRAL, percent: neutralPercent, color: '#f1c40f', value: NEUTRAL },
    { key: 'NEGATIVE', label: 'Negative', count: NEGATIVE, percent: negativePercent, color: '#e74c3c', value: NEGATIVE }
  ];

  let accumulatedPercentage = 0;
  const renderSegments = segments.map((seg, i) => {
    if (seg.value === 0) return null;

    const strokeLength = (seg.value / total) * circumference;
    const strokeOffset = circumference - strokeLength + (accumulatedPercentage / total) * circumference;
    accumulatedPercentage += seg.value;

    return (
      <circle
        key={seg.key}
        cx={center}
        cy={center}
        r={radius}
        fill="transparent"
        stroke={seg.color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={strokeOffset}
        strokeLinecap="round"
        transform={`rotate(-90 ${center} ${center})`}
        style={{
          cursor: 'pointer',
          transition: 'stroke-width 0.2s ease, opacity 0.2s ease',
          opacity: hoveredSegment === null || hoveredSegment === seg.key ? 1 : 0.6,
          strokeWidth: hoveredSegment === seg.key ? strokeWidth + 4 : strokeWidth
        }}
        onMouseEnter={() => setHoveredSegment(seg.key)}
        onMouseLeave={() => setHoveredSegment(null)}
      />
    );
  });

  const activeSegment = segments.find(s => s.key === hoveredSegment) || { label: 'Overall', count: total, percent: 100, color: 'var(--text-base)' };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '300px' }}>
      <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>Sentiment Proportions</h3>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px' }}>Breakdown of review sentiment</p>
      
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', flex: 1, gap: '16px' }}>
        {/* SVG Donut Chart */}
        <div style={{ position: 'relative', width: `${size}px`, height: `${size}px` }}>
          <svg width={size} height={size}>
            {renderSegments}
          </svg>
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            pointerEvents: 'none'
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-subdued)', fontWeight: '700', textTransform: 'uppercase' }}>
              {activeSegment.label}
            </span>
            <span style={{ fontSize: '28px', fontWeight: '900', color: activeSegment.color, lineHeight: '1.1' }}>
              {activeSegment.percent}%
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-subdued)', marginTop: '2px' }}>
              {activeSegment.count} reviews
            </span>
          </div>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {segments.map(seg => (
            <div 
              key={seg.key} 
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                cursor: 'pointer',
                opacity: hoveredSegment === null || hoveredSegment === seg.key ? 1 : 0.5,
                transition: 'opacity 0.2s'
              }}
              onMouseEnter={() => setHoveredSegment(seg.key)}
              onMouseLeave={() => setHoveredSegment(null)}
            >
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: seg.color }} />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-base)' }}>{seg.label}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-subdued)' }}>{seg.count} reviews ({seg.percent}%)</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
