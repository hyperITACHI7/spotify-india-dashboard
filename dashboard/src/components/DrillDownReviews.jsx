import { useState, useEffect } from 'react';
import axios from 'axios';
import { ArrowLeft, ArrowRight, Download, MessageSquare, Star } from 'lucide-react';
import API_URL from '../config';

export default function DrillDownReviews({
  dateRange,
  version,
  rating,
  search,
  selectedTopic,
  onSelectTopic,
  selectedTopicLabel,
  selectedKeyword,
  refreshTrigger
}) {
  const [reviewsData, setReviewsData] = useState({ total: 0, reviews: [] });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const pageSize = 5;

  useEffect(() => {
    // Reset page to 1 when filters change
    setPage(1);
  }, [dateRange, version, rating, search, selectedTopic, selectedKeyword, refreshTrigger]);

  useEffect(() => {
    setLoading(true);
    
    // Combine base search with selected keyword hash tag
    let searchParam = search;
    if (selectedKeyword) {
      searchParam = selectedKeyword;
    }

    axios.get(`${API_URL}/api/discovery/reviews`, {
      params: {
        date_range: dateRange,
        version: version,
        rating: rating,
        search: searchParam,
        topic: selectedTopic || 'All',
        page: page,
        page_size: pageSize
      }
    })
    .then(res => {
      setReviewsData(res.data.data);
      setLoading(false);
    })
    .catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, [dateRange, version, rating, search, selectedTopic, selectedKeyword, page, refreshTrigger]);

  const handleExport = () => {
    let searchParam = search;
    if (selectedKeyword) searchParam = selectedKeyword;
    
    const params = new URLSearchParams({
      date_range: dateRange,
      version: version,
      rating: rating,
      search: searchParam
    });
    
    window.location.href = `${API_URL}/api/discovery/export?${params.toString()}`;
  };

  const totalPages = Math.ceil(reviewsData.total / pageSize);

  const getSentimentLabelColor = (label) => {
    if (label === 'POSITIVE') return 'var(--spotify-green)';
    if (label === 'NEGATIVE') return '#e74c3c';
    return '#f1c40f';
  };

  return (
    <div className="card" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '20px', borderBottom: '1px solid var(--divider)', paddingBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MessageSquare size={18} color="var(--spotify-green)" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>
            Review Excerpts {selectedTopicLabel ? `— ${selectedTopicLabel}` : ''} {selectedKeyword ? `· "${selectedKeyword}"` : ''}
          </h3>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-subdued)', fontWeight: '700' }}>
            {reviewsData.total} reviews found
          </span>
          <button 
            onClick={handleExport}
            className="pill-button"
            style={{ padding: '6px 16px', fontSize: '12px' }}
          >
            <Download size={14} />
            Export Selected to CSV
          </button>
        </div>
      </div>

      {/* Selected Filters Breadcrumbs */}
      {selectedTopic && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '4px 10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '16px', color: 'var(--text-base)', marginRight: '8px' }}>
          <span>Topic: {selectedTopicLabel}</span>
          <button 
            onClick={() => onSelectTopic(null)}
            style={{ background: 'none', border: 'none', color: 'var(--spotify-green)', cursor: 'pointer', fontWeight: '700', marginLeft: '4px' }}
          >
            ×
          </button>
        </div>
      )}

      {loading ? (
        <p className="loading">Loading review details...</p>
      ) : reviewsData.reviews.length === 0 ? (
        <p style={{ color: 'var(--text-subdued)', textAlign: 'center', padding: '40px 0' }}>
          No reviews match the active filter criteria. Try expanding your filters.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {reviewsData.reviews.map((r, i) => (
            <div 
              key={i} 
              style={{ 
                padding: '16px', 
                backgroundColor: 'rgba(255,255,255,0.02)', 
                borderRadius: '6px',
                borderLeft: `4px solid ${getSentimentLabelColor(r.sentiment)}`,
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)'}
            >
              {/* Review Header Metadata */}
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
                  <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '500px', backgroundColor: `${getSentimentLabelColor(r.sentiment)}18`, color: getSentimentLabelColor(r.sentiment) }}>
                    {r.sentiment}
                  </span>
                </div>
                <div>
                  <span>Version: {r.version || 'Unknown'}</span>
                  <span style={{ marginLeft: '12px', textTransform: 'capitalize' }}>Platform: {r.platform} ({r.source})</span>
                </div>
              </div>

              {/* Review Content */}
              <p style={{ fontSize: '14px', lineHeight: '1.6', color: 'var(--text-base)' }}>
                {r.text}
              </p>
            </div>
          ))}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', borderTop: '1px solid var(--divider)', paddingTop: '16px' }}>
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'none',
                  border: 'none',
                  color: page === 1 ? 'var(--text-subdued)' : 'var(--text-base)',
                  cursor: page === 1 ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: '700'
                }}
              >
                <ArrowLeft size={16} />
                Previous Page
              </button>
              
              <span style={{ fontSize: '12px', color: 'var(--text-subdued)' }}>
                Page {page} of {totalPages}
              </span>

              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'none',
                  border: 'none',
                  color: page === totalPages ? 'var(--text-subdued)' : 'var(--text-base)',
                  cursor: page === totalPages ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: '700'
                }}
              >
                Next Page
                <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
