import { useState } from 'react';
import axios from 'axios';
import { GitBranch, ChevronDown, ChevronRight, Layers } from 'lucide-react';
import API_URL from '../config';

export default function TopicHierarchy({ matrix, dateRange, version, rating, platform, search }) {
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
          // subtopic_count from the matrix tells us how many distinct sub-topics
          // appeared in reviews for this topic — use it for the badge.
          const subCount = row.subtopic_count ?? 0;

          return (
            <div key={row.id} style={{ borderBottom: '1px solid var(--divider)' }}>
              {/* ── Topic header row ───────────────────────────────── */}
              <div
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
                {/* Left: chevron + label + sub-topic count badge */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {isExpanded
                    ? <ChevronDown size={16} color="var(--spotify-green)" />
                    : <ChevronRight size={16} color="var(--text-subdued)" />}

                  <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-base)' }}>
                    {row.label}
                  </span>

                  <span style={{ fontSize: '11px', color: 'var(--text-subdued)' }}>
                    ({row.reviews_count} reviews)
                  </span>

                  {/* Sub-topic count badge — green dot + number when there's data,
                      grey when no data tagged yet but taxonomy defines some */}
                  <span
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
                      backgroundColor: subCount > 0
                        ? 'rgba(29,185,84,0.12)'
                        : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${subCount > 0 ? 'rgba(29,185,84,0.25)' : 'var(--divider)'}`,
                      color: subCount > 0 ? 'var(--spotify-green)' : 'var(--text-subdued)',
                      cursor: 'default',
                    }}
                  >
                    <Layers size={10} />
                    {subCount > 0 ? `${subCount} sub-topics` : 'sub-topics'}
                  </span>
                </div>

                {/* Right: quick sentiment read */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '12px', color: '#e74c3c', fontWeight: '600' }}>
                    {row.pct_negative}% neg
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--spotify-green)', fontWeight: '600' }}>
                    {row.pct_positive}% pos
                  </span>
                </div>
              </div>

              {/* ── Expanded drill-down ────────────────────────────── */}
              {isExpanded && (
                <div style={{ padding: '0 24px 16px 48px' }}>
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
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <GitBranch size={12} color={hasReviews ? 'var(--spotify-green)' : 'var(--text-subdued)'} />
                              <span style={{ fontSize: '12px', fontWeight: '500', color: 'var(--text-base)' }}>
                                {sub.sub_topic || sub.label}
                              </span>
                              {!hasReviews && (
                                <span style={{ fontSize: '10px', color: 'var(--text-subdued)', fontStyle: 'italic' }}>
                                  no data yet
                                </span>
                              )}
                            </div>

                            {hasReviews && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px' }}>
                                <span style={{ color: 'var(--text-subdued)' }}>{sub.reviews_count} reviews</span>
                                <span style={{
                                  color: sub.pct_negative > 50 ? '#e74c3c' : sub.pct_negative > 25 ? '#f1c40f' : 'var(--spotify-green)',
                                  fontWeight: '600',
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
