import { useState, useEffect } from 'react';
import axios from 'axios';
import { TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import API_URL from '../config';

export default function TrendArrows({ dateRange, version, rating, platform, search }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    setLoading(true);
    const params = {
      date_range: dateRange || 'All',
      version: version || 'All',
      rating: rating || 'All',
      platform: platform || 'All',
      search: search || '',
      lookback_days: 7
    };
    axios.get(`${API_URL}/api/discovery/trends`, { params })
      .then(res => setData(res.data.data))
      .catch(err => console.error("Failed to fetch trends:", err))
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search]);

  if (loading) return <p className="loading">Loading trends...</p>;
  if (!data || !data.trends || data.trends.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No trend data available.</p>
      </div>
    );
  }

  const filtered = activeTab === 'all' ? data.trends : data.trends.filter(t => t.trend === activeTab);
  const displayTrends = filtered.slice(0, 10);

  const counts = {
    emerging: data.trends.filter(t => t.trend === 'emerging').length,
    stable: data.trends.filter(t => t.trend === 'stable').length,
    declining: data.trends.filter(t => t.trend === 'declining').length,
  };

  const getIcon = (trend) => {
    switch (trend) {
      case 'emerging': return <ArrowUpRight size={14} color="#e74c3c" />;
      case 'declining': return <ArrowDownRight size={14} color="var(--spotify-green)" />;
      default: return <Minus size={14} color="var(--text-subdued)" />;
    }
  };

  const getBadgeStyle = (trend) => {
    const base = { fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '500px', textTransform: 'uppercase' };
    switch (trend) {
      case 'emerging': return { ...base, color: '#e74c3c', backgroundColor: 'rgba(231,76,60,0.12)' };
      case 'declining': return { ...base, color: 'var(--spotify-green)', backgroundColor: 'rgba(29,185,84,0.12)' };
      default: return { ...base, color: 'var(--text-subdued)', backgroundColor: 'rgba(255,255,255,0.05)' };
    }
  };

  const tabs = [
    { key: 'all', label: 'All', count: data.trends.length },
    { key: 'emerging', label: 'Emerging', count: counts.emerging },
    { key: 'stable', label: 'Stable', count: counts.stable },
    { key: 'declining', label: 'Declining', count: counts.declining },
  ];

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <TrendingUp size={18} color="var(--spotify-green)" />
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Issue Trends</h3>
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '12px' }}>
        {data.period_current || 'Current vs previous period'} · {data.total_issues_tracked} issues tracked
      </p>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '4px 12px', fontSize: '11px', fontWeight: '600', borderRadius: '500px',
              border: 'none', cursor: 'pointer', transition: 'all 0.2s',
              backgroundColor: activeTab === tab.key ? 'rgba(29,185,84,0.15)' : 'transparent',
              color: activeTab === tab.key ? 'var(--spotify-green)' : 'var(--text-subdued)',
            }}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {displayTrends.map((trend, idx) => (
          <div key={idx} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '8px 12px', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {getIcon(trend.trend)}
              <span style={{ fontSize: '12px', fontWeight: '500', color: 'var(--text-base)' }}>{trend.issue}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-subdued)' }}>
                {trend.volume_current} → prev {trend.volume_previous}
              </span>
              <span style={getBadgeStyle(trend.trend)}>
                {trend.growth_rate === 999 ? 'NEW' : `${trend.growth_rate > 0 ? '+' : ''}${trend.growth_rate}%`}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
