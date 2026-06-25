import { X } from 'lucide-react';

export default function FilterPanel({
  dateRange,
  version,
  rating,
  platform,
  onApply,
  onReset,
}) {
  const platforms  = ['All', 'android', 'ios'];
  const versions   = ['All', 'v9.0.2', 'v8.9.12', 'v8.9.10'];
  const ratings    = ['All', '1', '2', '3', '4', '5'];
  const dateRanges = [
    { value: 'All', label: 'All Time' },
    { value: '7d',  label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
    { value: '90d', label: 'Last 90 Days' },
  ];

  const handleFilterChange = (key, value) => {
    onApply({ dateRange, version, rating, platform, [key]: value });
  };

  const hasAnyActiveFilters =
    dateRange !== 'All' ||
    version   !== 'All' ||
    rating    !== 'All' ||
    platform  !== 'All';

  return (
    <div className="card" style={{ marginBottom: '16px', padding: '16px', display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center' }}>
      {/* Date Range */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Timeframe</span>
        <select
          value={dateRange}
          onChange={(e) => handleFilterChange('dateRange', e.target.value)}
          className="filter-select"
        >
          {dateRanges.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
      </div>

      {/* App Version */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>App Version</span>
        <select
          value={version}
          onChange={(e) => handleFilterChange('version', e.target.value)}
          className="filter-select"
        >
          {versions.map(v => <option key={v} value={v}>{v === 'All' ? 'All Versions' : v}</option>)}
        </select>
      </div>

      {/* Rating */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Rating</span>
        <select
          value={rating}
          onChange={(e) => handleFilterChange('rating', e.target.value)}
          className="filter-select"
        >
          {ratings.map(r => (
            <option key={r} value={r}>{r === 'All' ? 'All Ratings' : `${r} Star${r !== '1' ? 's' : ''}`}</option>
          ))}
        </select>
      </div>

      {/* Platform */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase' }}>Platform</span>
        <select
          value={platform}
          onChange={(e) => handleFilterChange('platform', e.target.value)}
          className="filter-select"
        >
          {platforms.map(p => (
            <option key={p} value={p}>
              {p === 'All' ? 'All Platforms' : p === 'android' ? 'Play Store' : 'App Store'}
            </option>
          ))}
        </select>
      </div>

      {/* Reset button — only visible when any filter is active */}
      <div style={{ display: 'flex', gap: '10px', alignSelf: 'flex-end', height: '38px' }}>
        {hasAnyActiveFilters && (
          <button
            onClick={onReset}
            style={{
              background: 'none',
              border: '1px solid var(--divider)',
              borderRadius: '500px',
              color: 'var(--text-base)',
              padding: '8px 20px',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              height: '100%',
              transition: 'border-color 0.2s, background-color 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = 'var(--text-base)';
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = 'var(--divider)';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
