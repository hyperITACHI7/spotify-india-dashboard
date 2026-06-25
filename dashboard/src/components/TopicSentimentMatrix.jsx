import { useState } from 'react';
import { AlertTriangle, ArrowDownCircle } from 'lucide-react';

export default function TopicSentimentMatrix({ matrix, selectedTopic, onSelectTopic }) {
  const [hoveredRow, setHoveredRow] = useState(null);

  const getSentimentColor = (val) => {
    if (val > 0.15)  return 'var(--spotify-green)';
    if (val < -0.15) return '#e74c3c';
    return '#f1c40f';
  };

  const getTrendColor = (trend) => {
    if (trend.startsWith('+') && trend.includes('neg')) return '#e74c3c';
    if (trend.startsWith('-') && trend.includes('neg')) return 'var(--spotify-green)';
    return 'var(--text-subdued)';
  };

  const maxCount = Math.max(...matrix.map(r => r.reviews_count), 1);

  const getPriority = (row) => {
    const normNeg = row.pct_negative / 100;
    const normVol = row.reviews_count / maxCount;
    if (normNeg > 0.6 && normVol > 0.5) return { label: 'CRITICAL', color: '#e74c3c' };
    if (normNeg > 0.6)                  return { label: 'HIGH SEV', color: '#e67e22' };
    if (normVol > 0.5)                  return { label: 'HIGH VOL', color: '#f1c40f' };
    return { label: 'MONITOR', color: 'var(--text-subdued)' };
  };

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '24px' }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--divider)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '18px', fontWeight: '700' }}>Topic Sentiment Matrix</h3>
          <p style={{ fontSize: '12px', color: 'var(--text-subdued)', marginTop: '2px' }}>
            Click a row to filter the review list below to that topic
          </p>
        </div>
        {selectedTopic && (
          <button
            onClick={() => onSelectTopic(null)}
            style={{
              background: 'none',
              border: '1px solid rgba(29,185,84,0.3)',
              borderRadius: '500px',
              color: 'var(--spotify-green)',
              fontWeight: '700',
              fontSize: '12px',
              cursor: 'pointer',
              padding: '5px 14px',
            }}
          >
            Clear selection
          </button>
        )}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="table-container" style={{ width: '100%', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th style={{ paddingLeft: '24px', width: '16%' }}>Category Topic</th>
              <th style={{ textAlign: 'center', width: '60px'  }}>Reviews</th>
              <th style={{ textAlign: 'center', width: '90px' }}>Avg Sentiment</th>
              <th style={{ textAlign: 'center', width: '72px' }}>% Pos</th>
              <th style={{ textAlign: 'center', width: '72px' }}>% Neg</th>
              <th style={{ textAlign: 'center', width: '82px' }}>Trend (±Δ)</th>
              <th style={{ textAlign: 'center', width: '82px' }}>Priority</th>
              <th style={{ paddingRight: '24px' }}>Core Issue Summary</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((row) => {
              const isSelected = selectedTopic === row.id;
              const isHovered  = hoveredRow === row.id;
              const highlight  = isSelected || isHovered;
              const priority   = getPriority(row);

              return (
                <tr
                  key={row.id}
                  className={`table-row ${isSelected ? 'active-row' : ''}`}
                  onClick={() => onSelectTopic(isSelected ? null : row.id)}
                  onMouseEnter={() => setHoveredRow(row.id)}
                  onMouseLeave={() => setHoveredRow(null)}
                  title="Click to filter reviews to this topic"
                  style={{
                    cursor: 'pointer',
                    backgroundColor: isSelected
                      ? 'rgba(29, 185, 84, 0.08)'
                      : isHovered
                        ? 'rgba(255,255,255,0.03)'
                        : 'transparent',
                    borderLeft: isSelected
                      ? '4px solid var(--spotify-green)'
                      : '4px solid transparent',
                    transition: 'background-color 0.15s',
                  }}
                >
                  <td className="highlight-text" style={{ paddingLeft: '20px', border: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', maxWidth: '100%' }}>
                      {row.pct_negative >= 50 && (
                        <AlertTriangle size={14} color="#e74c3c" style={{ flexShrink: 0 }} title="High priority — majority of reviews are negative" />
                      )}
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.label}>
                        {row.label}
                      </span>
                    </span>
                  </td>

                  <td style={{ textAlign: 'center', fontWeight: '500' }}>
                    {row.reviews_count}
                  </td>

                  <td style={{ textAlign: 'center', color: getSentimentColor(row.avg_sentiment), fontWeight: '700' }}>
                    {row.avg_sentiment > 0 ? `+${row.avg_sentiment.toFixed(2)}` : row.avg_sentiment.toFixed(2)}
                  </td>

                  <td style={{ textAlign: 'center', color: 'var(--spotify-green)', fontWeight: '700' }}>
                    {row.pct_positive}%
                  </td>

                  <td style={{ textAlign: 'center', color: '#e74c3c', fontWeight: '700' }}>
                    {row.pct_negative}%
                  </td>

                  <td style={{ textAlign: 'center', color: getTrendColor(row.trend), fontWeight: '700' }}>
                    {row.trend}
                  </td>

                  <td style={{ textAlign: 'center' }}>
                    <span style={{
                      fontSize: '10px', fontWeight: '700', padding: '2px 8px',
                      borderRadius: '500px', whiteSpace: 'nowrap',
                      color: priority.color,
                      backgroundColor: `${priority.color}18`,
                    }}>
                      {priority.label}
                    </span>
                  </td>

                  <td style={{ paddingRight: '24px', border: 'none', maxWidth: '280px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                      <span
                        style={{
                          flex: 1,
                          minWidth: 0,
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: '13px',
                          color: highlight ? 'var(--text-base)' : 'var(--text-subdued)',
                        }}
                        title={row.summary}
                      >
                        {row.summary}
                      </span>
                      <span style={{
                        flexShrink: 0,
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        fontSize: '11px', fontWeight: '700', whiteSpace: 'nowrap',
                        color: isSelected ? 'var(--spotify-green)' : isHovered ? 'var(--text-subdued)' : 'transparent',
                        transition: 'color 0.15s', userSelect: 'none',
                      }}>
                        <ArrowDownCircle size={13} />
                        <span className="matrix-btn-label">{isSelected ? 'Showing reviews' : 'View reviews'}</span>
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
