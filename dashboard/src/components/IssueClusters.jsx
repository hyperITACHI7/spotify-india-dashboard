import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layers } from 'lucide-react';
import API_URL from '../config';

export default function IssueClusters({ dateRange, version, rating, platform, search }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {
      date_range: dateRange || 'All',
      version: version || 'All',
      rating: rating || 'All',
      platform: platform || 'All',
      search: search || ''
    };
    axios.get(`${API_URL}/api/discovery/clusters`, { params })
      .then(res => setData(res.data.data))
      .catch(err => console.error("Failed to fetch clusters:", err))
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search]);

  if (loading) return <p className="loading">Loading issue clusters...</p>;
  if (!data || !data.clusters || data.clusters.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No issue clusters detected.</p>
      </div>
    );
  }

  const topClusters = data.clusters.slice(0, 5);
  const maxVolume = topClusters[0]?.volume || 1;

  const getSentimentBar = (dist) => {
    const total = Object.values(dist).reduce((a, b) => a + b, 0);
    if (total === 0) return null;
    const negPct = ((dist.NEGATIVE || 0) / total) * 100;
    const posPct = ((dist.POSITIVE || 0) / total) * 100;
    const neuPct = 100 - negPct - posPct;
    return (
      <div style={{ display: 'flex', width: '100%', height: '6px', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{ width: `${negPct}%`, backgroundColor: '#e74c3c' }} />
        <div style={{ width: `${neuPct}%`, backgroundColor: '#f1c40f' }} />
        <div style={{ width: `${posPct}%`, backgroundColor: 'var(--spotify-green)' }} />
      </div>
    );
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <Layers size={18} color="var(--spotify-green)" />
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Issue Clusters</h3>
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px' }}>
        {data.total_issues_clustered} issues grouped into {data.clusters.length} clusters
        {data.noise_issues > 0 && ` (${data.noise_issues} noise)`}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {topClusters.map((cluster) => {
          const widthPct = (cluster.volume / maxVolume) * 100;
          return (
            <div key={cluster.cluster_id} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-base)', fontWeight: '600' }}>{cluster.representative_issue}</span>
                <span style={{ color: 'var(--text-subdued)' }}>{cluster.volume} mentions · {cluster.issues.length} issues</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-subdued)', flexShrink: 0, width: '80px' }}>Volume</span>
                <div style={{ flex: 1, height: '6px', backgroundColor: 'var(--divider)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${widthPct}%`, height: '100%',
                    backgroundColor: '#e74c3c',
                    borderRadius: '3px', transition: 'width 0.6s ease'
                  }} />
                </div>
              </div>
              {cluster.sentiment_distribution && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '10px', color: 'var(--text-subdued)', flexShrink: 0, width: '80px' }}>Sentiment mix</span>
                  <div style={{ flex: 1 }}>{getSentimentBar(cluster.sentiment_distribution)}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
