import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { ArrowLeft, ArrowRight, Download, MessageSquare, Star, Search, X } from 'lucide-react';
import API_URL from '../config';

export default function DrillDownReviews({
  dateRange,
  version,
  rating,
  platform,
  selectedTopic,
  onSelectTopic,
  selectedTopicLabel,
  selectedKeyword,
  refreshTrigger,
  modeReady,
}) {
  const [reviewsData, setReviewsData] = useState({ total: 0, reviews: [] });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [localSearch, setLocalSearch] = useState('');
  const debounceRef = useRef(null);
  const pageSize = 5;

  const handleSearchInput = (value) => {
    setLocalSearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(value), 300);
  };

  useEffect(() => {
    setPage(1);
  }, [dateRange, version, rating, platform, search, selectedTopic, selectedKeyword, refreshTrigger]);

  useEffect(() => {
    // Wait for mode to be confirmed server-side before fetching
    if (modeReady === false) return;

    setLoading(true);

    // selectedKeyword comes from the keyword cloud (NLP issue label) — match via
    // issue_keyword so the backend filters by r['issues'], not by text substring.
    // Local search is a plain text search against the review body.
    const params = {
      date_range: dateRange,
      version,
      rating,
      platform: platform || 'All',
      topic: selectedTopic || 'All',
      page,
      page_size: pageSize,
    };
    if (selectedKeyword) {
      params.issue_keyword = selectedKeyword;
    } else {
      params.search = search;
    }

    axios.get(`${API_URL}/api/discovery/reviews`, { params })
    .then(res => {
      setReviewsData(res.data.data);
      setLoading(false);
    })
    .catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, [dateRange, version, rating, platform, search, selectedTopic, selectedKeyword, page, refreshTrigger, modeReady]);

  const handleExport = () => {
    const searchParam = selectedKeyword || search;
    const params = new URLSearchParams({
      date_range: dateRange,
      version,
      rating,
      platform: platform || 'All',
      search: searchParam,
    });
    window.location.href = `${API_URL}/api/discovery/export?${params.toString()}`;
  };

  const totalPages = Math.ceil(reviewsData.total / pageSize);

  const getSentimentColor = (label) => {
    if (label === 'POSITIVE') return 'var(--spotify-green)';
    if (label === 'NEGATIVE') return '#e74c3c';
    return '#f1c40f';
  };

  return (
    <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ marginBottom: '16px', borderBottom: '1px solid var(--divider)', paddingBottom: '16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={18} color="var(--spotify-green)" />
            <h3 style={{ fontSize: '16px', fontWeight: '700' }}>
              Review Excerpts {selectedTopicLabel ? `— ${selectedTopicLabel}` : ''}{selectedKeyword ? ` · "${selectedKeyword}"` : ''}
            </h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-subdued)', fontWeight: '700' }}>
              {reviewsData.total} reviews found
            </span>
            <button onClick={handleExport} className="pill-button" style={{ padding: '6px 16px', fontSize: '12px' }}>
              <Download size={14} />
              Export CSV
            </button>
          </div>
        </div>
        {/* Search input — scoped to this review list only */}
        <div style={{ position: 'relative', maxWidth: '360px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-subdued)', pointerEvents: 'none' }} />
          <input
            type="text"
            value={localSearch}
            onChange={(e) => handleSearchInput(e.target.value)}
            placeholder="Search reviews by keyword..."
            className="filter-search-input"
            style={{ paddingLeft: '32px' }}
          />
          {localSearch && (
            <button
              onClick={() => { setLocalSearch(''); setSearch(''); }}
              style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-subdued)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Active topic breadcrumb */}
      {selectedTopic && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '4px 10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '16px', color: 'var(--text-base)', flexShrink: 0 }}>
          <span>Topic: {selectedTopicLabel}</span>
          <button onClick={() => onSelectTopic(null)} style={{ background: 'none', border: 'none', color: 'var(--spotify-green)', cursor: 'pointer', fontWeight: '700', marginLeft: '4px' }}>×</button>
        </div>
      )}

      {/* Fixed-height scrollable review area — never collapses during page load */}
      <div style={{ minHeight: '480px', maxHeight: '580px', overflowY: 'auto', flex: 1 }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '480px' }}>
            <p className="loading">Loading reviews...</p>
          </div>
        ) : reviewsData.reviews.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '480px' }}>
            <p style={{ color: 'var(--text-subdued)', textAlign: 'center' }}>
              No reviews match the active filter criteria.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '4px 0' }}>
            {reviewsData.reviews.map((r, i) => (
              <div
                key={i}
                style={{
                  padding: '16px',
                  backgroundColor: 'rgba(255,255,255,0.02)',
                  borderRadius: '6px',
                  borderLeft: `4px solid ${getSentimentColor(r.sentiment)}`,
                  transition: 'background-color 0.2s',
                  flexShrink: 0,
                }}
                onMouseOver={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)'}
                onMouseOut={e  => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)'}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '10px', fontSize: '12px', color: 'var(--text-subdued)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ display: 'flex', gap: '2px' }}>
                      {Array.from({ length: 5 }).map((_, idx) => (
                        <Star key={idx} size={11}
                          fill={idx < r.rating ? '#f1c40f' : 'none'}
                          color={idx < r.rating ? '#f1c40f' : 'var(--divider)'}
                        />
                      ))}
                    </div>
                    <span>{r.date}</span>
                    <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '500px', backgroundColor: `${getSentimentColor(r.sentiment)}18`, color: getSentimentColor(r.sentiment) }}>
                      {r.sentiment}
                    </span>
                  </div>
                  <div>
                    <span>Version: {r.version || 'Unknown'}</span>
                    <span style={{ marginLeft: '12px', textTransform: 'capitalize' }}>Platform: {r.platform} ({r.source})</span>
                  </div>
                </div>
                <p style={{ fontSize: '14px', lineHeight: '1.6', color: 'var(--text-base)' }}>{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination — always rendered outside the scroll area so it stays visible */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', borderTop: '1px solid var(--divider)', paddingTop: '16px', flexShrink: 0 }}>
          <button
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: page === 1 ? 'var(--text-subdued)' : 'var(--text-base)', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: '700' }}
          >
            <ArrowLeft size={16} />
            Previous
          </button>
          <span style={{ fontSize: '12px', color: 'var(--text-subdued)' }}>
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page === totalPages}
            onClick={() => setPage(page + 1)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: page === totalPages ? 'var(--text-subdued)' : 'var(--text-base)', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: '700' }}
          >
            Next
            <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
