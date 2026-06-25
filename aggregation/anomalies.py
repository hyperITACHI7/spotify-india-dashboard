"""
aggregation/anomalies.py

Phase 6: Anomaly Detection.
Detects unusual sentiment shifts for topics using z-score analysis.
Pure-Python using math module (no scipy/numpy needed).
"""

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def _mean(values: List[float]) -> float:
    """Compute arithmetic mean."""
    return sum(values) / len(values) if values else 0.0


def _std_dev(values: List[float]) -> float:
    """Compute population standard deviation."""
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((x - avg) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _z_scores(values: List[float]) -> List[float]:
    """Compute z-scores for a list of values."""
    avg = _mean(values)
    std = _std_dev(values)
    if std == 0:
        return [0.0] * len(values)
    return [(v - avg) / std for v in values]


class AnomalyDetector:
    """
    Phase 6: Detects sentiment anomalies using z-score analysis.
    Flags days where negative sentiment deviates significantly (>2 std devs)
    from the norm for a given topic.
    """

    def detect_anomalies(
        self,
        reviews: List[Dict],
        window_days: int = 14,
        z_threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Detect unusual sentiment patterns from review data.

        Args:
            reviews: List of review dicts with 'date', 'sentiment', 'topics' keys.
            window_days: Number of days to analyze.
            z_threshold: Z-score threshold for anomaly detection (default 2.0).

        Returns:
            {
                "anomalies": [
                    {
                        "topic": "search_discovery",
                        "date": "2026-06-18",
                        "anomaly_type": "negative_spike",
                        "description": "Negative sentiment 45% above average on 2026-06-18",
                        "severity": "High",
                        "negative_pct": 0.8,
                        "z_score": 2.5
                    },
                    ...
                ],
                "daily_stats": [...],
                "topics_analyzed": 5
            }
        """
        if not reviews:
            return {"anomalies": [], "daily_stats": [], "topics_analyzed": 0}

        # Parse dates
        dated_reviews = []
        for r in reviews:
            date_str = r.get('date', '')
            if not date_str:
                continue
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dated_reviews.append((dt, r))
            except ValueError:
                continue

        if not dated_reviews:
            return {"anomalies": [], "daily_stats": [], "topics_analyzed": 0}

        # Find date range
        max_date = max(dt for dt, _ in dated_reviews)
        min_date = max_date - timedelta(days=window_days - 1)

        # Collect all topics from reviews
        all_topics = set()
        for _, r in dated_reviews:
            for t in (r.get('topics') or []):
                all_topics.add(t)

        if not all_topics:
            # Use a fallback topic
            all_topics = {'general'}

        # Build daily sentiment stats per topic
        # daily_data[topic][date_str] = {"total": N, "negative": N, "positive": N}
        daily_data = defaultdict(lambda: defaultdict(lambda: {"total": 0, "negative": 0, "positive": 0}))

        for dt, r in dated_reviews:
            if dt < min_date or dt > max_date:
                continue
            date_key = dt.strftime("%Y-%m-%d")
            sentiment = (r.get('sentiment') or 'NEUTRAL').upper()
            topics = r.get('topics') or ['general']

            for topic in topics:
                daily_data[topic][date_key]["total"] += 1
                if sentiment == 'NEGATIVE':
                    daily_data[topic][date_key]["negative"] += 1
                elif sentiment == 'POSITIVE':
                    daily_data[topic][date_key]["positive"] += 1

        # Detect anomalies per topic
        anomalies = []
        daily_stats_output = []
        topics_analyzed = 0

        for topic in sorted(all_topics):
            topic_daily = daily_data.get(topic, {})
            if not topic_daily:
                continue

            # Build sorted date list
            dates_sorted = sorted(topic_daily.keys())
            if len(dates_sorted) < 3:
                continue

            topics_analyzed += 1
            negative_pcts = []

            for d in dates_sorted:
                stats = topic_daily[d]
                total = stats["total"]
                neg_pct = stats["negative"] / total if total > 0 else 0.0
                negative_pcts.append(neg_pct)

                daily_stats_output.append({
                    "topic": topic,
                    "date": d,
                    "total_reviews": total,
                    "negative_pct": round(neg_pct * 100, 1),
                    "positive_pct": round((stats["positive"] / total * 100) if total > 0 else 0, 1),
                })

            # Compute z-scores
            z = _z_scores(negative_pcts)
            avg_neg = _mean(negative_pcts)

            for i, z_val in enumerate(z):
                abs_z = abs(z_val)
                if abs_z >= z_threshold:
                    neg_pct = negative_pcts[i]
                    deviation = round((neg_pct - avg_neg) * 100, 1)

                    if z_val > 0:
                        anomaly_type = "negative_spike"
                        description = f"Negative sentiment {abs(deviation)}% above average on {dates_sorted[i]}"
                    else:
                        anomaly_type = "positive_spike"
                        description = f"Negative sentiment {abs(deviation)}% below average on {dates_sorted[i]} (unusually positive day)"

                    anomalies.append({
                        "topic": topic,
                        "date": dates_sorted[i],
                        "anomaly_type": anomaly_type,
                        "description": description,
                        "severity": "High" if abs_z > 3.0 else "Medium",
                        "negative_pct": round(neg_pct, 3),
                        "z_score": round(abs_z, 2),
                    })

        # Sort anomalies by z_score descending
        anomalies.sort(key=lambda a: a['z_score'], reverse=True)

        return {
            "anomalies": anomalies,
            "daily_stats": daily_stats_output,
            "topics_analyzed": topics_analyzed,
        }

    def detect_anomalies_from_db(
        self, conn, window_days: int = 14, z_threshold: float = 2.0,
        mode_filter: str = ""
    ) -> Dict[str, Any]:
        """
        Live DB version of anomaly detection.
        Queries daily sentiment distribution per topic from reviews_enriched.
        mode_filter: optional SQL AND-clause to restrict by ingestion run.
        """
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT
                DATE(rr.created_at) as date,
                rt.topic_id as topic,
                COUNT(DISTINCT re.review_id) as total,
                COUNT(DISTINCT re.review_id) FILTER (WHERE re.sentiment_label = 'NEGATIVE') as negative_count,
                COUNT(DISTINCT re.review_id) FILTER (WHERE re.sentiment_label = 'POSITIVE') as positive_count
            FROM reviews_enriched re
            JOIN reviews_raw rr ON re.review_id = rr.id
            JOIN review_topics rt ON re.review_id = rt.review_id
            WHERE rr.created_at >= NOW() - INTERVAL '%s days'
            {mode_filter}
            GROUP BY DATE(rr.created_at), rt.topic_id
            ORDER BY rt.topic_id, date
        """, (window_days,))

        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return {"anomalies": [], "daily_stats": [], "topics_analyzed": 0, "source": "database"}

        # Group by topic
        topic_data = defaultdict(list)
        for row in rows:
            topic_data[row['topic']].append({
                "date": row['date'],
                "total": row['total'],
                "negative": row['negative_count'],
                "positive": row['positive_count'],
            })

        anomalies = []
        daily_stats = []
        topics_analyzed = 0

        for topic, days in topic_data.items():
            if len(days) < 3:
                continue
            topics_analyzed += 1

            days_sorted = sorted(days, key=lambda d: d['date'])
            negative_pcts = [d['negative'] / d['total'] if d['total'] > 0 else 0.0 for d in days_sorted]
            z = _z_scores(negative_pcts)
            avg_neg = _mean(negative_pcts)

            for i, d in enumerate(days_sorted):
                neg_pct = negative_pcts[i]
                daily_stats.append({
                    "topic": topic,
                    "date": d['date'].isoformat() if hasattr(d['date'], 'isoformat') else str(d['date']),
                    "total_reviews": d['total'],
                    "negative_pct": round(neg_pct * 100, 1),
                })

                abs_z = abs(z[i])
                if abs_z >= z_threshold:
                    deviation = round((neg_pct - avg_neg) * 100, 1)
                    anomaly_type = "negative_spike" if z[i] > 0 else "positive_spike"
                    description = (
                        f"Negative sentiment {abs(deviation)}% above average on {d['date']}"
                        if z[i] > 0
                        else f"Negative sentiment {abs(deviation)}% below average on {d['date']}"
                    )
                    anomalies.append({
                        "topic": topic,
                        "date": d['date'].isoformat() if hasattr(d['date'], 'isoformat') else str(d['date']),
                        "anomaly_type": anomaly_type,
                        "description": description,
                        "severity": "High" if abs_z > 3.0 else "Medium",
                        "negative_pct": round(neg_pct, 3),
                        "z_score": round(abs_z, 2),
                    })

        anomalies.sort(key=lambda a: a['z_score'], reverse=True)
        return {
            "anomalies": anomalies,
            "daily_stats": daily_stats,
            "topics_analyzed": topics_analyzed,
            "source": "database",
        }
