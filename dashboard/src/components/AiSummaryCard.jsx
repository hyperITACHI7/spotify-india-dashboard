import { useState, useEffect } from 'react';
import axios from 'axios';
import { Sparkles } from 'lucide-react';
import API_URL from '../config';

export default function AiSummaryCard({ dateRange, version, rating, platform, search, dataMode, refreshTrigger }) {
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError('');
    setSummary('');
    const paramsObj = {
      date_range: dateRange || 'All',
      version: version || 'All',
      rating: rating || 'All',
      platform: platform || 'All',
      search: search || '',
    };
    if (dataMode) paramsObj.data_mode = dataMode;
    const params = new URLSearchParams(paramsObj);

    axios.post(`${API_URL}/api/discovery/ai-synthesis?${params.toString()}`)
      .then(res => {
        if (res.data.error) {
          setError(res.data.error);
        } else {
          setSummary(res.data.summary);
        }
      })
      .catch(() => {
        setError('Could not reach the server. Make sure the backend is running.');
      })
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search, dataMode, refreshTrigger]);

  const isLimit = error.toLowerCase().includes('limit') || error.toLowerCase().includes('token');

  return (
    <div className="card" style={{ marginBottom: '32px', borderTop: '2px solid var(--spotify-green)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <Sparkles size={18} color="var(--spotify-green)" />
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>AI Synthesis</h3>
        <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '500px', backgroundColor: 'rgba(29,185,84,0.12)', color: 'var(--spotify-green)', marginLeft: '4px' }}>
          LLM
        </span>
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px' }}>
        Deep narrative summary generated from review intelligence
      </p>

      {loading ? (
        <p className="loading">Analysing reviews…</p>
      ) : error ? (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '12px',
          padding: '16px', borderRadius: '8px',
          backgroundColor: isLimit ? 'rgba(241,196,15,0.06)' : 'rgba(231,76,60,0.06)',
          border: `1px solid ${isLimit ? 'rgba(241,196,15,0.2)' : 'rgba(231,76,60,0.2)'}`,
        }}>
          <span style={{ fontSize: '18px', flexShrink: 0 }}>{isLimit ? '⏳' : '⚠️'}</span>
          <p style={{ fontSize: '13px', color: 'var(--text-subdued)', margin: 0, lineHeight: '1.5' }}>{error}</p>
        </div>
      ) : (
        <div style={{ fontSize: '14px', lineHeight: '1.8', color: 'var(--text-subdued)' }}>
          {summary.split('\n').map((line, i) => (
            <p key={i} style={{ marginBottom: '8px', color: line.trim() ? 'var(--text-base)' : 'transparent' }}>
              {line.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
                part.startsWith('**') && part.endsWith('**')
                  ? <strong key={j}>{part.slice(2, -2)}</strong>
                  : part
              )}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
