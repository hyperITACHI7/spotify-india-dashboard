import { useState } from 'react';
import axios from 'axios';
import { GitBranch, ChevronDown, ChevronRight, Layers } from 'lucide-react';
import API_URL from '../config';

export default function TopicHierarchy({ matrix, dateRange, version, rating, platform, search, dataMode }) {
  const [expandedTopic, setExpandedTopic] = useState(null);
  const [subtopics,    setSubtopics]    = useState({});
  const [summary,      setSummary]      = useState({});
  const [loadingSub,   setLoadingSub]   = useState({});

  const params = {
    date_range: dateRange || 'All',
    version:    version   || 'All',
    rating:     rating    || 'All',
    platform:   platform  || 'All',
    search:     search    || '',
    data_mode:  dataMode,
  };

  const toggleTopic = (topicId) => {
    if (expandedTopic === topicId) {
      setExpandedTopic(null);
      return;
    }
    setExpandedTopic(topicId);

    if (!subtopics[topicId]) {
      setLoadingSub(prev => ({ ...prev, [topicId]: true }));
      axios.get(`${API_URL}/api/discovery/topics/${topicId}/subtopics`, { params })
        .then(res => setSubtopics(prev => ({ ...prev, [topicId]: res.data.data.subtopics || [] })))
        .catch(err => console.error('Failed to fetch subtopics:', err))
        .finally(() => setLoadingSub(prev => ({ ...prev, [topicId]: false })));
    }

    if (!summary[topicId]) {
      axios.get(`${API_URL}/api/discovery/topics/${topicId}/summary`)
        .then(res => setSummary(prev => ({ ...prev, [topicId]: res.data.data })))
        .catch(() => {});
    }
  };

  if (!matrix || matrix.length === 0) return null;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '24px' }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitBranch size={18} color="var(--spotify-green)" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Topic Hierarchy Explorer</h3>
        </div>
        <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginTop: '4px' }}>
          Click a topic to drill down into sub-topics
        </p>
      </div>

      <div className="topic-hierarchy-body">
        {matrix.slice(0, 8).map((row) => {
          const isExpanded  = expandedTopic === row.id;
          const subData     = subtopics[row.id];
          const summaryData = summary[row.id];
          const isLoadingSub = loadingSub[row.id];
          const subCount = row.subtopic_count ?? 0;

          return (
            <div key={row.id} style={{ borderBottom: '1px solid var(--divider)' }}>
              {/* ── Topic header row ───────────────────────────────── */}
              <div
                className="topic-row-header"
                onClick={() => toggleTopic(row.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 24px',
                  cursor: 'pointer',
                  transition: 'background-color 0.15s',
                  backgroundColor: isExpanded ? 'rgba(29,185,84,0.06)' : 'transparent',
                }}
                onMouseOver={(e) => {
                  if (!isExpanded) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)';
                }}
                onMouseOut={(e) => {
                  if (!isExpanded) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {/* Left: chevron + label + review count + sub-topic badge */}
                <div className="topic-row-left" style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1, overflow: 'hidden' }}>
                  {isExpanded
                    ? <ChevronDown size={16} color="var(--spotify-green)" style={{ flexShrink: 0 }} />
                    : <ChevronRight size={16} color="var(--text-subdued)" style={{ flexShrink: 0 }} />}

                  <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-base)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.label}
                  </span>

                  <span className="topic-review-count" style={{ fontSize: '11px', color: 'var(--text-subdued)', flexShrink: 0 }}>
                    ({row.reviews_count})
                  </span>

                  <span
                    className="topic-subtopic-badge"
                    title={subCount > 0
                      ? `${subCount} sub-topic${subCount !== 1 ? 's' : ''} found in reviews — click to explore`
                      : 'Sub-topics available — click to explore'}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 8px',
                      borderRadius: '500px',
                      fontSize: '11px',
                      fontWeight: '700',
                      flexShrink: 0,
                      backgroundColor: subCount > 0
                        ? 'rgba(29,185,84,0.12)'
                        : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${subCount > 0 ? 'rgba(29,185,84,0.25)' : 'var(--divider)'}`,
                      color: subCount > 0 ? 'var(--spotify-green)' : 'var(--text-subdued)',
                      cursor: 'default',
                    }}
                  >
                    <Layers size={10} />
                    <span className="topic-subtopic-badge-text">
                      {subCount > 0 ? `${subCount} sub-topics` : 'sub-topics'}
                    </span>
                  </span>
                </div>

                {/* Right: quick sentiment read — fixed-width columns, always flush right */}
                <div className="topic-row-right" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, marginLeft: '12px' }}>
                  <span style={{ fontSize: '12px', color: '#e74c3c', fontWeight: '600', minWidth: '50px', textAlign: 'right' }}>
                    {row.pct_negative}% neg
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--spotify-green)', fontWeight: '600', minWidth: '48px', textAlign: 'right' }}>
                    {row.pct_positive}% pos
                  </span>
                </div>
              </div>

              {/* ── Expanded drill-down ────────────────────────────── */}
              {isExpanded && (
                <div className="topic-drilldown-body" style={{ padding: '0 24px 16px 48px' }}>
                  {/* AI summary banner */}
                  {summaryData && summaryData.summary && (
                    <div style={{
                      padding: '12px 16px',
                      marginBottom: '12px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(29,185,84,0.06)',
                      border: '1px solid rgba(29,185,84,0.15)',
                    }}>
                      <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--spotify-green)', textTransform: 'uppercase' }}>
                        AI Summary
                      </span>
                      <p style={{ fontSize: '12px', color: 'var(--text-base)', margin: '4px 0 0', lineHeight: '1.5' }}>
                        {summaryData.summary}
                      </p>
                    </div>
                  )}

                  {/* Sub-topic list */}
                  {isLoadingSub ? (
                    <p className="loading" style={{ fontSize: '12px' }}>Loading sub-topics...</p>
                  ) : subData && subData.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {subData.map((sub, idx) => {
                        const hasReviews = (sub.reviews_count || 0) > 0;
                        return (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 12px',
                              borderRadius: '6px',
                              backgroundColor: hasReviews
                                ? 'rgba(255,255,255,0.03)'
                                : 'transparent',
                              borderLeft: hasReviews
                                ? '3px solid rgba(29,185,84,0.3)'
                                : '3px solid var(--divider)',
                              opacity: hasReviews ? 1 : 0.45,
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1, overflow: 'hidden' }}>
                              <GitBranch size={12} color={hasReviews ? 'var(--spotify-green)' : 'var(--text-subdued)'} style={{ flexShrink: 0 }} />
                              <span style={{ fontSize: '12px', fontWeight: '500', color: 'var(--text-base)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {sub.sub_topic || sub.label}
                              </span>
                              {!hasReviews && (
                                <span style={{ fontSize: '10px', color: 'var(--text-subdued)', fontStyle: 'italic', flexShrink: 0 }}>
                                  no data yet
                                </span>
                              )}
                            </div>

                            {hasReviews && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', flexShrink: 0, marginLeft: '8px' }}>
                                <span className="subtopic-review-count" style={{ color: 'var(--text-subdued)' }}>{sub.reviews_count} reviews</span>
                                <span style={{
                                  color: sub.pct_negative > 50 ? '#e74c3c' : sub.pct_negative > 25 ? '#f1c40f' : 'var(--spotify-green)',
                                  fontWeight: '600',
                                  minWidth: '50px',
                                  textAlign: 'right',
                                }}>
                                  {sub.pct_negative}% neg
                                </span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p style={{ fontSize: '12px', color: 'var(--text-subdued)' }}>
                      No sub-topic data available for this category.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
