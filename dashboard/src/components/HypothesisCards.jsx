import { useState, useEffect } from 'react';
import axios from 'axios';
import { Lightbulb, FlaskConical, BarChart3, TestTube, Wrench, TrendingUp } from 'lucide-react';
import API_URL from '../config';

export default function HypothesisCards({ dateRange, version, rating, platform, search, dataMode, refreshTrigger }) {
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
      data_mode: dataMode,
    };
    axios.get(`${API_URL}/api/discovery/hypotheses`, { params })
      .then(res => setData(res.data.data))
      .catch(err => console.error("Failed to fetch hypotheses:", err))
      .finally(() => setLoading(false));
  }, [dateRange, version, rating, platform, search, dataMode, refreshTrigger]);

  if (loading) return <p className="loading">Generating hypotheses...</p>;

  if (!data || !data.hypotheses || data.hypotheses.length === 0) {
    const source = data?.source;
    const msg    = data?.error || 'No hypotheses generated.';
    const isPending = source === 'topics_pending';
    const isLimit   = !isPending && (msg.toLowerCase().includes('limit') || msg.toLowerCase().includes('token'));
    const icon  = isPending ? '⏳' : isLimit ? '⏳' : '⚠️';
    const color = isPending ? 'rgba(29,185,84,0.06)'   : isLimit ? 'rgba(241,196,15,0.06)' : 'rgba(231,76,60,0.06)';
    const border= isPending ? 'rgba(29,185,84,0.2)'    : isLimit ? 'rgba(241,196,15,0.2)'  : 'rgba(231,76,60,0.2)';
    return (
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Lightbulb size={18} color="#f1c40f" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>AI Product Hypotheses</h3>
        </div>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '12px',
          padding: '16px', borderRadius: '8px',
          backgroundColor: color, border: `1px solid ${border}`,
        }}>
          <span style={{ fontSize: '18px', flexShrink: 0 }}>{icon}</span>
          <p style={{ fontSize: '13px', color: 'var(--text-subdued)', margin: 0, lineHeight: '1.5' }}>{msg}</p>
        </div>
      </div>
    );
  }

  const getConfidenceStyle = (confidence) => {
    const base = { fontSize: '10px', fontWeight: '700', padding: '2px 10px', borderRadius: '500px' };
    switch (confidence) {
      case 'High': return { ...base, color: 'var(--spotify-green)', backgroundColor: 'rgba(29,185,84,0.12)' };
      case 'Medium': return { ...base, color: '#f1c40f', backgroundColor: 'rgba(241,196,15,0.12)' };
      default: return { ...base, color: 'var(--text-subdued)', backgroundColor: 'rgba(255,255,255,0.05)' };
    }
  };

  const summary = data.intelligence_summary || {};

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Lightbulb size={18} color="#f1c40f" />
          <h3 style={{ fontSize: '16px', fontWeight: '700' }}>AI Product Hypotheses</h3>
        </div>
        <span style={{
          fontSize: '10px', fontWeight: '700', padding: '3px 10px', borderRadius: '500px',
          color: 'var(--spotify-green)', backgroundColor: 'rgba(29,185,84,0.12)',
        }}>
          LLM Generated
        </span>
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '20px' }}>
        From {summary.total_reviews} reviews · {summary.topics_count} topics · {summary.priority_issues_count} priority issues · {summary.clusters_found} clusters · {summary.trends_tracked} trends
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {data.hypotheses.map((h, idx) => (
          <div key={idx} style={{
            padding: '16px', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '8px',
            border: '1px solid var(--divider)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '4px',
                  backgroundColor: 'rgba(29,185,84,0.15)', color: 'var(--spotify-green)'
                }}>
                  H{idx + 1}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-subdued)', textTransform: 'capitalize' }}>
                  {h.topic?.replace(/_/g, ' ')}
                </span>
              </div>
              <span style={getConfidenceStyle(h.confidence)}>{h.confidence} confidence</span>
            </div>

            <p style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-base)', lineHeight: '1.5', marginBottom: '10px' }}>
              {h.hypothesis}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', flex: '1 1 200px' }}>
                  <BarChart3 size={12} color="var(--spotify-green)" style={{ marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Evidence</span>
                    <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: '2px 0 0', lineHeight: '1.4' }}>{h.evidence}</p>
                  </div>
                </div>
                {h.expected_impact && (
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', flex: '1 1 200px' }}>
                    <TrendingUp size={12} color="rgba(29,185,84,0.8)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Expected Impact</span>
                      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: '2px 0 0', lineHeight: '1.4' }}>{h.expected_impact}</p>
                    </div>
                  </div>
                )}
              </div>
              {h.solution && (
                <div style={{
                  display: 'flex', alignItems: 'flex-start', gap: '6px',
                  padding: '10px 12px', borderRadius: '6px',
                  backgroundColor: 'rgba(29,185,84,0.05)', border: '1px solid rgba(29,185,84,0.15)',
                }}>
                  <Wrench size={12} color="var(--spotify-green)" style={{ marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--spotify-green)', textTransform: 'uppercase' }}>Recommended Solution</span>
                    <p style={{ fontSize: '12px', color: 'var(--text-base)', margin: '2px 0 0', lineHeight: '1.5' }}>{h.solution}</p>
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                <TestTube size={12} color="#f1c40f" style={{ marginTop: '2px', flexShrink: 0 }} />
                <div>
                  <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Experiment Design</span>
                  <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: '2px 0 0', lineHeight: '1.4' }}>{h.recommended_test}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
