import { useState, useEffect } from 'react';
import axios from 'axios';
import { Target } from 'lucide-react';
import API_URL from '../config';

export default function PriorityMatrix({ dateRange, version, rating, platform, search }) {
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
      limit: 10
    };
    axios.get(`${API_URL}/api/discovery/priority-issues`, { params })
      .then(res => setData(res.data.data))
      .catch(err => console.error("Failed to fetch priority issues:", err))
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search]);

  if (loading) return <p className="loading">Loading priority matrix...</p>;
  if (!data || !data.issues || data.issues.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No priority issues found.</p>
      </div>
    );
  }

  const maxScore = data.issues[0]?.priority_score || 1;

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'Critical': return '#e74c3c';
      case 'High': return '#e67e22';
      case 'Medium': return '#f1c40f';
      default: return 'var(--text-subdued)';
    }
  };

  const getQuadrant = (score, volume) => {
    const normScore = score / maxScore;
    const maxVol = Math.max(...data.issues.map(i => i.volume));
    const normVol = volume / (maxVol || 1);
    if (normScore > 0.6 && normVol > 0.5) return { label: 'CRITICAL', color: '#e74c3c' };
    if (normScore > 0.6) return { label: 'HIGH SEV', color: '#e67e22' };
    if (normVol > 0.5) return { label: 'HIGH VOL', color: '#f1c40f' };
    return { label: 'MONITOR', color: 'var(--text-subdued)' };
  };

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={18} color="#e74c3c" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Priority Matrix</h3>
        </div>
        <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginTop: '4px' }}>
          Severity × Volume ranking · {data.total_issues_analyzed} issues analyzed
        </p>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="table-container" style={{ minWidth: '600px' }}>
          <thead>
            <tr>
              <th style={{ paddingLeft: '24px', width: '40px' }}>#</th>
              <th>Issue</th>
              <th style={{ textAlign: 'center', width: '90px' }}>Severity</th>
              <th style={{ textAlign: 'center', width: '80px' }}>Volume</th>
              <th style={{ textAlign: 'center', width: '80px' }}>Score</th>
              <th style={{ textAlign: 'center', width: '90px', paddingRight: '24px' }}>Quadrant</th>
            </tr>
          </thead>
          <tbody>
            {data.issues.slice(0, 8).map((issue, idx) => {
              const quadrant = getQuadrant(issue.priority_score, issue.volume);
              return (
                <tr key={idx} className="table-row">
                  <td style={{ paddingLeft: '24px', textAlign: 'center', fontWeight: '700', color: 'var(--text-subdued)' }}>{idx + 1}</td>
                  <td className="highlight-text" style={{ fontWeight: '500' }}>{issue.issue}</td>
                  <td style={{ textAlign: 'center' }}>
                    <span style={{
                      fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '500px',
                      color: getSeverityColor(issue.severity),
                      backgroundColor: `${getSeverityColor(issue.severity)}18`
                    }}>
                      {issue.severity}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center', fontWeight: '600', fontSize: '13px' }}>{issue.volume}</td>
                  <td style={{ textAlign: 'center', fontWeight: '700', color: 'var(--spotify-green)', fontSize: '13px' }}>
                    {issue.priority_score.toFixed(1)}
                  </td>
                  <td style={{ textAlign: 'center', paddingRight: '24px' }}>
                    <span style={{
                      fontSize: '9px', fontWeight: '700', padding: '2px 6px', borderRadius: '500px',
                      color: quadrant.color, backgroundColor: `${quadrant.color}18`
                    }}>
                      {quadrant.label}
                    </span>
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
