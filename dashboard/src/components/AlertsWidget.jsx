import { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertTriangle, Info, Bell, RefreshCw, Zap, TrendingUp } from 'lucide-react';
import API_URL from '../config';

export default function AlertsWidget({ dateRange, version, rating, platform, search, onRefresh, refreshTrigger }) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [alerts,    setAlerts]    = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [activeTab, setActiveTab] = useState('alerts');

  const params = {
    date_range: dateRange || 'All',
    version:    version   || 'All',
    rating:     rating    || 'All',
    platform:   platform  || 'All',
    search:     search    || '',
  };

  const fetchAll = () => {
    setIsRefreshing(true);
    Promise.all([
      axios.get(`${API_URL}/api/discovery/alerts`,    { params }),
      axios.get(`${API_URL}/api/discovery/anomalies`, { params: { ...params, window_days: 14 } }),
    ])
      .then(([alertsRes, anomaliesRes]) => {
        setAlerts(alertsRes.data.data || []);
        setAnomalies(anomaliesRes.data.data?.anomalies || []);
      })
      .catch(err => console.error('Failed to fetch alerts/anomalies', err))
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => { fetchAll(); }, [dateRange, version, rating, platform, search, refreshTrigger]);

  const handleRefresh = () => {
    if (onRefresh) onRefresh();
    fetchAll();
  };

  const severityBorderColor = (sev) =>
    sev === 'CRITICAL' || sev === 'High' ? '#e74c3c'
    : sev === 'WARNING' || sev === 'Medium' ? '#f1c40f'
    : 'var(--spotify-green)';

  const criticalCount = alerts.filter(a => a.severity === 'CRITICAL').length
    + anomalies.filter(a => a.severity === 'High').length;

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Bell size={18} color="var(--spotify-green)" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Alerts & Anomalies</h3>
          {criticalCount > 0 && (
            <span style={{
              fontSize: '10px', fontWeight: '900', padding: '2px 8px',
              borderRadius: '500px', background: 'rgba(231,76,60,0.15)',
              color: '#e74c3c', border: '1px solid rgba(231,76,60,0.3)',
            }}>
              {criticalCount} critical
            </span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: isRefreshing ? 'var(--spotify-green)' : 'var(--text-subdued)',
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '11px', fontWeight: '700', textTransform: 'uppercase',
            padding: '4px 8px', borderRadius: '4px', transition: 'color 0.2s',
          }}
          onMouseOver={e => { if (!isRefreshing) e.currentTarget.style.color = 'var(--text-base)'; }}
          onMouseOut={e => { if (!isRefreshing) e.currentTarget.style.color = 'var(--text-subdued)'; }}
        >
          <RefreshCw size={12} style={{ animation: isRefreshing ? 'spin-refresh 0.8s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px' }}>
        {[
          { key: 'alerts',    label: 'Signals',   count: alerts.length,    icon: Bell  },
          { key: 'anomalies', label: 'Anomalies', count: anomalies.length, icon: Zap   },
        ].map(({ key, label, count, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '5px 14px', borderRadius: '500px', border: 'none',
              cursor: 'pointer', fontSize: '12px', fontWeight: '700',
              transition: 'all 0.2s',
              backgroundColor: activeTab === key ? 'rgba(29,185,84,0.15)' : 'transparent',
              color: activeTab === key ? 'var(--spotify-green)' : 'var(--text-subdued)',
            }}
          >
            <Icon size={13} />
            {label}
            <span style={{
              fontSize: '10px', padding: '1px 6px', borderRadius: '500px',
              background: activeTab === key ? 'rgba(29,185,84,0.2)' : 'rgba(255,255,255,0.06)',
            }}>
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* ── Alerts tab ─────────────────────────────────────────────── */}
      {activeTab === 'alerts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {alerts.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 16px', background: 'rgba(29,185,84,0.06)', borderRadius: '8px', border: '1px solid rgba(29,185,84,0.15)' }}>
              <TrendingUp size={18} color="var(--spotify-green)" />
              <p style={{ fontSize: '13px', color: 'var(--spotify-green)', margin: 0, fontWeight: '600' }}>No signals detected — metrics look stable.</p>
            </div>
          ) : alerts.map((al) => (
            <div key={al.id} style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              padding: '10px 14px', backgroundColor: 'rgba(255,255,255,0.02)',
              borderRadius: '6px', borderLeft: `3px solid ${severityBorderColor(al.severity)}`,
            }}>
              <div style={{ marginTop: '2px' }}>
                {al.severity === 'INFO'
                  ? <Info size={15} color="var(--spotify-green)" />
                  : <AlertTriangle size={15} color={al.severity === 'CRITICAL' ? '#e74c3c' : '#f1c40f'} />}
              </div>
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-base)' }}>{al.message}</span>
                <div style={{ fontSize: '10px', color: 'var(--text-subdued)', marginTop: '2px' }}>{al.time}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Anomalies tab ──────────────────────────────────────────── */}
      {activeTab === 'anomalies' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {anomalies.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 16px', background: 'rgba(29,185,84,0.06)', borderRadius: '8px', border: '1px solid rgba(29,185,84,0.15)' }}>
              <TrendingUp size={18} color="var(--spotify-green)" />
              <p style={{ fontSize: '13px', color: 'var(--spotify-green)', margin: 0, fontWeight: '600' }}>No anomalies — sentiment patterns are within normal range.</p>
            </div>
          ) : anomalies.slice(0, 8).map((a, idx) => (
            <div key={idx} style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              padding: '10px 14px', backgroundColor: 'rgba(255,255,255,0.02)',
              borderRadius: '6px', borderLeft: `3px solid ${severityBorderColor(a.severity)}`,
            }}>
              <AlertTriangle size={15} color={a.severity === 'High' ? '#e74c3c' : '#f1c40f'} style={{ marginTop: '2px', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                  <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-base)' }}>
                    {a.topic?.replace(/_/g, ' ')}
                  </span>
                  <span style={{
                    fontSize: '10px', fontWeight: '700', padding: '1px 7px', borderRadius: '500px',
                    color: a.severity === 'High' ? '#e74c3c' : '#f1c40f',
                    backgroundColor: a.severity === 'High' ? 'rgba(231,76,60,0.12)' : 'rgba(241,196,15,0.12)',
                  }}>
                    {a.severity}
                  </span>
                </div>
                <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: 0 }}>{a.description}</p>
                <span style={{ fontSize: '10px', color: 'var(--text-subdued)' }}>{a.date}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
