import { MessageSquare, Star, Heart, TrendingDown } from 'lucide-react';

function buildSourceLabel(source_counts) {
  const counts = source_counts || {};
  const parts = [];
  if (counts.playstore) parts.push(`Play Store (${counts.playstore})`);
  if (counts.appstore) parts.push(`App Store (${counts.appstore})`);
  if (parts.length === 0) return 'India stores';
  return parts.join(' & ') + ' · India';
}

export default function OverviewKpis({ stats }) {
  const { total_reviews, avg_sentiment, avg_rating, neg_this_month, source_counts } = stats;

  // Helpers to color score and style rating
  const getSentimentColor = (val) => {
    if (val > 0.15) return 'var(--spotify-green)';
    if (val < -0.15) return '#e74c3c';
    return '#f1c40f';
  };

  const getSentimentText = (val) => {
    if (val > 0.15) return 'Positive';
    if (val < -0.15) return 'Negative';
    return 'Mixed';
  };

  return (
    <div className="grid-4" style={{ marginBottom: '24px' }}>
      {/* Total Reviews Card */}
      <div className="card kpi-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="kpi-title">Total Reviews</span>
          <MessageSquare size={20} color="var(--text-subdued)" />
        </div>
        <p className="kpi-value">{total_reviews.toLocaleString()}</p>
        <span className="kpi-subtext">{buildSourceLabel(source_counts)}</span>
      </div>

      {/* Avg Sentiment Card */}
      <div className="card kpi-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="kpi-title">Avg Sentiment</span>
          <Heart size={20} color={getSentimentColor(avg_sentiment)} />
        </div>
        <p className="kpi-value" style={{ color: getSentimentColor(avg_sentiment) }}>
          {avg_sentiment > 0 ? `+${avg_sentiment}` : avg_sentiment}
        </p>
        <span className="kpi-subtext">Overall Mood: <strong style={{ color: getSentimentColor(avg_sentiment) }}>{getSentimentText(avg_sentiment)}</strong></span>
      </div>

      {/* 5-Star Average Rating Card */}
      <div className="card kpi-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="kpi-title">Average Rating</span>
          <Star size={20} color="#f1c40f" fill="#f1c40f" />
        </div>
        <p className="kpi-value">{avg_rating.toFixed(2)} <span style={{ fontSize: '18px', color: 'var(--text-subdued)' }}>/ 5</span></p>
        <span className="kpi-subtext">User satisfaction score</span>
      </div>

      {/* Monthly Negatives Card */}
      <div className="card kpi-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="kpi-title">Negatives This Month</span>
          <TrendingDown size={20} color="#e74c3c" />
        </div>
        <p className="kpi-value" style={{ color: '#e74c3c' }}>{neg_this_month}</p>
        <span className="kpi-subtext">Flagged for discovery issues</span>
      </div>
    </div>
  );
}
