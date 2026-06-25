import { useState } from 'react';
import { Smile, Frown } from 'lucide-react';

export default function KeywordCloud({ keywords, selectedKeyword, onSelectKeyword }) {
  const [activeTab, setActiveTab] = useState('negative');
  const { positive = [], negative = [] } = keywords;

  const tabs = [
    { key: 'negative', label: 'Frustrations', icon: Frown,  color: '#e74c3c', list: negative },
    { key: 'positive', label: 'Praise',        icon: Smile,  color: 'var(--spotify-green)', list: positive },
  ];

  const active = tabs.find(t => t.key === activeTab);

  return (
    <div className="card" style={{ height: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Keyword Buzz</h3>
        <div style={{ display: 'flex', gap: '4px' }}>
          {tabs.map(({ key, label, icon: Icon, color, list }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                padding: '4px 12px', borderRadius: '500px', border: 'none',
                cursor: 'pointer', fontSize: '11px', fontWeight: '700',
                transition: 'all 0.2s',
                backgroundColor: activeTab === key ? `${color}18` : 'transparent',
                color: activeTab === key ? color : 'var(--text-subdued)',
              }}
            >
              <Icon size={12} />
              {label}
              <span style={{
                fontSize: '10px', padding: '1px 5px', borderRadius: '500px',
                background: activeTab === key ? `${color}25` : 'rgba(255,255,255,0.06)',
              }}>
                {list.length}
              </span>
            </button>
          ))}
        </div>
      </div>

      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px' }}>
        Click a word to filter reviews
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {active.list.map((kw, i) => {
          const isSelected = selectedKeyword === kw.text;
          const c = active.color;
          const sentiment = activeTab === 'negative' ? 'NEGATIVE' : 'POSITIVE';
          return (
            <span
              key={`${activeTab}-${kw.text}-${i}`}
              onClick={() => onSelectKeyword(isSelected ? '' : kw.text, sentiment)}
              style={{
                fontSize: '12px', fontWeight: '700',
                color: isSelected ? (activeTab === 'negative' ? '#fff' : '#000') : c,
                backgroundColor: isSelected ? c : `${c}18`,
                padding: '5px 12px', borderRadius: '500px', cursor: 'pointer',
                border: `1px solid ${isSelected ? c : `${c}30`}`,
                transition: 'background-color 0.15s, transform 0.1s',
              }}
              onMouseOver={e => { if (!isSelected) { e.currentTarget.style.backgroundColor = `${c}30`; e.currentTarget.style.transform = 'scale(1.04)'; } }}
              onMouseOut={e => { if (!isSelected) { e.currentTarget.style.backgroundColor = `${c}18`; e.currentTarget.style.transform = 'scale(1)'; } }}
            >
              {kw.text} <span style={{ fontWeight: '400', opacity: 0.6, fontSize: '10px' }}>{kw.value}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
