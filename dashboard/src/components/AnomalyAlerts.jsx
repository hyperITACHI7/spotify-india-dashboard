import { useState, useEffect } from 'react';
import axios from 'axios';
import { Zap, AlertTriangle, TrendingUp } from 'lucide-react';
import API_URL from '../config';

export default function AnomalyAlerts({ dateRange, version, rating, platform, search }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {
      date_range: dateRange || 'All',
      version: version || 'All',
      rating: rating || 'All',
      platform: platform || 'All',
      search: search || '',
      window_days: 14
    };
    axios.get(`${API_URL}/api/discovery/anomalies`, { params })
      .then(res => setData(res.data.data))
      .catch(err => console.error("Failed to fetch anomalies:", err))
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search]);

  if (loading) return <p className="loading">Detecting anomalies...</p>;

  const anomalies = data?.anomalies || [];
  const topicsAnalyzed = data?.topics_analyzed || 0;

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <Zap size={18} color="#f1c40f" />
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Sentiment Anomalies</h3>
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px' }}>
        Z-score analysis across {topicsAnalyzed} topics · {anomalies.length} anomalies detected
      </p>

      {anomalies.length === 0 ? (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '16px', backgroundColor: 'rgba(29,185,84,0.06)', borderRadius: '8px',
          border: '1px solid rgba(29,185,84,0.15)'
        }}>
          <TrendingUp size={20} color="var(--spotify-green)" />
          <div>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--spotify-green)' }}>No anomalies detected</span>
            <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: 0 }}>Sentiment patterns are within normal range.</p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {anomalies.slice(0, 6).map((anomaly, idx) => (
            <div key={idx} style={{
              display: 'flex', alignItems: 'flex-start', gap: '10px',
              padding: '10px 14px', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px',
              borderLeft: `3px solid ${anomaly.severity === 'High' ? '#e74c3c' : '#f1c40f'}`
            }}>
              <AlertTriangle size={14} color={anomaly.severity === 'High' ? '#e74c3c' : '#f1c40f'} style={{ marginTop: '2px' }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-base)' }}>
                    {anomaly.topic.replace(/_/g, ' ')}
                  </span>
                  <span style={{
                    fontSize: '10px', fontWeight: '700', padding: '1px 6px', borderRadius: '500px',
                    color: anomaly.severity === 'High' ? '#e74c3c' : '#f1c40f',
                    backgroundColor: anomaly.severity === 'High' ? 'rgba(231,76,60,0.12)' : 'rgba(241,196,15,0.12)'
                  }}>
                    {anomaly.severity}
                  </span>
                </div>
                <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: '2px 0 0' }}>{anomaly.description}</p>
                <span style={{ fontSize: '10px', color: 'var(--text-subdued)' }}>{anomaly.date}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
