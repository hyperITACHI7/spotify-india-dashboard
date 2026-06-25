import { useState, useEffect } from 'react';
import axios from 'axios';
import API_URL from '../config';

export default function SentimentStats() {
  const [stats, setStats] = useState({ POSITIVE: 0, NEUTRAL: 0, NEGATIVE: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_URL}/api/discovery/stats`)
      .then(res => {
        setStats(res.data.data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) return <p className="loading">Loading stats...</p>;

  return (
    <div className="grid-3">
      <div className="card" style={{ borderTop: '4px solid var(--spotify-green)' }}>
        <p style={{ color: 'var(--text-subdued)', fontWeight: '700', fontSize: '14px' }}>POSITIVE FEEDBACK</p>
        <p className="stat-value" style={{ color: 'var(--text-base)' }}>{stats.POSITIVE}</p>
      </div>
      <div className="card" style={{ borderTop: '4px solid #f1c40f' }}>
        <p style={{ color: 'var(--text-subdued)', fontWeight: '700', fontSize: '14px' }}>NEUTRAL FEEDBACK</p>
        <p className="stat-value">{stats.NEUTRAL}</p>
      </div>
      <div className="card" style={{ borderTop: '4px solid #e74c3c' }}>
        <p style={{ color: 'var(--text-subdued)', fontWeight: '700', fontSize: '14px' }}>NEGATIVE FEEDBACK</p>
        <p className="stat-value">{stats.NEGATIVE}</p>
      </div>
    </div>
  );
}
