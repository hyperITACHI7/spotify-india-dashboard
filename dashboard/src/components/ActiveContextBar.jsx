import { X, Filter } from 'lucide-react';

function Chip({ label, onClear, color, borderColor, textColor }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '3px 8px 3px 10px',
      borderRadius: '500px',
      backgroundColor: color,
      border: `1px solid ${borderColor}`,
      fontSize: '12px',
      fontWeight: '600',
      color: textColor,
    }}>
      {label}
      <button
        onClick={onClear}
        title="Remove filter"
        style={{
          background: 'none',
          border: 'none',
          color: textColor,
          cursor: 'pointer',
          padding: '0',
          display: 'flex',
          alignItems: 'center',
          opacity: 0.65,
          lineHeight: 1,
        }}
        onMouseOver={(e) => { e.currentTarget.style.opacity = '1'; }}
        onMouseOut={(e) => { e.currentTarget.style.opacity = '0.65'; }}
      >
        <X size={11} />
      </button>
    </span>
  );
}

/**
 * ActiveContextBar — a slim bar that surfaces every active global filter and
 * every active drill-down selection as dismissible chips in one place.
 *
 * Global filter chips (green) = affect all widgets.
 * Drill-down chips (yellow) = scope only the review list below.
 */
export default function ActiveContextBar({
  dateRange,
  version,
  rating,
  platform,
  search,
  selectedTopic,
  selectedTopicLabel,
  selectedKeyword,
  onClearFilter,
  onClearTopic,
  onClearKeyword,
  onResetAll,
}) {
  const dateLabel = {
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '90d': 'Last 90 Days',
  };

  const platformLabel = {
    android: 'Play Store',
    ios: 'App Store',
  };

  const globalChips = [];
  const drillChips = [];

  if (dateRange !== 'All')
    globalChips.push({ key: 'dateRange', label: dateLabel[dateRange] || dateRange, onClear: () => onClearFilter('dateRange') });
  if (version !== 'All')
    globalChips.push({ key: 'version', label: version, onClear: () => onClearFilter('version') });
  if (rating !== 'All')
    globalChips.push({ key: 'rating', label: `${rating} Star${rating !== '1' ? 's' : ''}`, onClear: () => onClearFilter('rating') });
  if (platform !== 'All')
    globalChips.push({ key: 'platform', label: platformLabel[platform] || platform, onClear: () => onClearFilter('platform') });
  if (search)
    globalChips.push({ key: 'search', label: `"${search}"`, onClear: () => onClearFilter('search') });

  if (selectedTopic)
    drillChips.push({ key: 'topic', label: `Topic: ${selectedTopicLabel}`, onClear: onClearTopic });
  if (selectedKeyword)
    drillChips.push({ key: 'keyword', label: `Keyword: "${selectedKeyword}"`, onClear: onClearKeyword });

  if (globalChips.length === 0 && drillChips.length === 0) return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: '8px',
      padding: '10px 14px',
      marginBottom: '16px',
      borderRadius: '8px',
      backgroundColor: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--divider)',
    }}>
      <Filter size={13} style={{ color: 'var(--text-subdued)', flexShrink: 0 }} />
      <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-subdued)', textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>
        Filters
      </span>

      {/* Global filter chips — green, affect all widgets */}
      {globalChips.map(chip => (
        <Chip
          key={chip.key}
          label={chip.label}
          onClear={chip.onClear}
          color="rgba(29, 185, 84, 0.12)"
          borderColor="rgba(29, 185, 84, 0.28)"
          textColor="var(--spotify-green)"
        />
      ))}

      {/* Divider between global and drill-down chips */}
      {globalChips.length > 0 && drillChips.length > 0 && (
        <span style={{ fontSize: '14px', color: 'var(--divider)', userSelect: 'none' }}>│</span>
      )}

      {/* Drill-down chips — yellow, scope only the review list */}
      {drillChips.map(chip => (
        <Chip
          key={chip.key}
          label={chip.label}
          onClear={chip.onClear}
          color="rgba(241, 196, 15, 0.1)"
          borderColor="rgba(241, 196, 15, 0.28)"
          textColor="#f1c40f"
        />
      ))}

      {drillChips.length > 0 && (
        <span style={{ fontSize: '11px', color: 'var(--text-subdued)', fontStyle: 'italic' }}>
          — scopes review list only
        </span>
      )}

      <button
        onClick={onResetAll}
        style={{
          marginLeft: 'auto',
          background: 'none',
          border: 'none',
          color: 'var(--text-subdued)',
          fontSize: '12px',
          fontWeight: '600',
          cursor: 'pointer',
          padding: '2px 6px',
          borderRadius: '4px',
          flexShrink: 0,
        }}
        onMouseOver={(e) => { e.currentTarget.style.color = 'var(--text-base)'; }}
        onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-subdued)'; }}
      >
        Reset all
      </button>
    </div>
  );
}
