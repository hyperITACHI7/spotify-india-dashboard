function NlpProcessingState({ label, nlpProgress = {} }) {
  const { processed = 0, total = 0 } = nlpProgress;
  const pct = total > 0 ? Math.round((processed / total) * 100) : null;
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px', gap: '16px' }}>
      <p style={{ color: 'var(--text-base)', fontWeight: '600', fontSize: '13px', margin: 0 }}>{label}</p>
      <p style={{ color: 'var(--text-subdued)', fontSize: '11px', margin: 0 }}>
        {pct !== null ? `${processed} / ${total} reviews processed` : 'NLP topic analysis starting…'}
      </p>
      <div style={{ width: '200px', height: '4px', backgroundColor: 'var(--divider)', borderRadius: '2px', overflow: 'hidden', position: 'relative' }}>
        {pct !== null
          ? <div style={{ position: 'absolute', top: 0, left: 0, width: `${pct}%`, height: '100%', backgroundColor: 'var(--spotify-green)', borderRadius: '2px', transition: 'width 0.4s ease' }} />
          : <div className="nlp-processing-bar" style={{ position: 'absolute', top: 0, left: 0, width: '40%', height: '100%', backgroundColor: 'var(--spotify-green)', borderRadius: '2px' }} />
        }
      </div>
      {pct !== null && <p style={{ color: 'var(--text-subdued)', fontSize: '10px', margin: 0 }}>{pct}%</p>}
    </div>
  );
}

export default function TopIssuesBar({ matrix, totalReviews, nlpProgress }) {
  const topicsWithNegatives = matrix
    .map(row => ({
      ...row,
      negativeCount: Math.round(((row.reviews_count || 0) * (row.pct_negative || 0)) / 100),
    }))
    .filter(row => row.reviews_count > 0);

  // Primary: sort by negative count; fallback: sort by total if all negatives are 0
  const hasNegatives = topicsWithNegatives.some(r => r.negativeCount > 0);
  const topIssues = [...topicsWithNegatives]
    .sort((a, b) => hasNegatives
      ? b.negativeCount - a.negativeCount
      : b.reviews_count - a.reviews_count
    )
    .slice(0, 5);

  const maxValue = topIssues.length > 0
    ? (hasNegatives ? topIssues[0].negativeCount : topIssues[0].reviews_count)
    : 1;

  if (topIssues.length === 0) {
    if (totalReviews > 0) return <NlpProcessingState label="Analyzing topic distribution..." nlpProgress={nlpProgress} />;
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No reviews scraped yet.</p>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '300px' }}>
      <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>Top Issues by Volume</h3>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '24px' }}>
        {hasNegatives ? 'Categories with highest number of negative mentions' : 'Categories by review volume'}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px', flex: 1, justifyContent: 'center' }}>
        {topIssues.map((issue) => {
          const displayValue = hasNegatives ? issue.negativeCount : issue.reviews_count;
          const percentageOfMax = (displayValue / maxValue) * 100;
          return (
            <div key={issue.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '500', marginBottom: '6px' }}>
                <span style={{ color: 'var(--text-base)' }}>{issue.label}</span>
                <span style={{ color: hasNegatives ? '#e74c3c' : 'var(--text-subdued)', fontWeight: '700' }}>
                  {hasNegatives ? `${displayValue} complaints` : `${displayValue} reviews`}
                </span>
              </div>
              <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--divider)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  width: `${percentageOfMax}%`, height: '100%',
                  backgroundColor: hasNegatives ? '#e74c3c' : 'var(--spotify-green)',
                  borderRadius: '3px',
                  transition: 'width 0.6s ease',
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
