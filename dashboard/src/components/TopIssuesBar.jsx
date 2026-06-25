export default function TopIssuesBar({ matrix }) {
  // Calculate negative reviews count for each row and filter out zero-count rows
  const topicsWithNegatives = matrix
    .map(row => {
      const negativeCount = Math.round((row.reviews_count * row.pct_negative) / 100);
      return {
        ...row,
        negativeCount
      };
    })
    .filter(row => row.negativeCount > 0);

  // Sort by negativeCount descending and limit to top 5
  const topIssues = [...topicsWithNegatives]
    .sort((a, b) => b.negativeCount - a.negativeCount)
    .slice(0, 5);

  const maxNegatives = topIssues.length > 0 ? topIssues[0].negativeCount : 1;

  if (topIssues.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px' }}>
        <p style={{ color: 'var(--text-subdued)' }}>No negative review counts found to rank.</p>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '300px' }}>
      <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>Top Issues by Volume</h3>
      <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '24px' }}>Categories with highest number of negative mentions</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px', flex: 1, justifyContent: 'center' }}>
        {topIssues.map((issue) => {
          const percentageOfMax = (issue.negativeCount / maxNegatives) * 100;
          return (
            <div key={issue.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '500', marginBottom: '6px' }}>
                <span style={{ color: 'var(--text-base)' }}>{issue.label}</span>
                <span style={{ color: '#e74c3c', fontWeight: '700' }}>{issue.negativeCount} complaints</span>
              </div>
              <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--divider)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  width: `${percentageOfMax}%`, height: '100%',
                  backgroundColor: '#e74c3c',
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
