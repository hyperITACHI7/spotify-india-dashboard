"""
aggregation/trends.py

Phase 6: Trend Detection.
Identifies emerging, stable, and declining issues by comparing
issue volumes in the current period vs the previous period.
Pure-Python, no external dependencies.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class TrendDetector:
    """
    Phase 6: Detects issue trends by comparing current vs previous time windows.
    Classifies each issue as 'emerging' (growth >100%), 'stable' (-20%..100%),
    or 'declining' (growth <-20%).
    """

    def detect_trends(
        self,
        reviews: List[Dict],
        lookback_days: int = 7,
        reference_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Identify emerging/stable/declining issues from review data.

        Args:
            reviews: List of review dicts with 'issues' and 'date' keys.
            lookback_days: Number of days for the current window.
            reference_date: Optional reference date string (YYYY-MM-DD).
                           If None, uses the most recent date in the data.

        Returns:
            {
                "trends": [
                    {
                        "issue": "premium popups",
                        "trend": "emerging",
                        "volume_current": 45,
                        "volume_previous": 12,
                        "growth_rate": 275.0
                    },
                    ...
                ],
                "period_current": "2026-06-15 to 2026-06-21",
                "period_previous": "2026-06-08 to 2026-06-14",
                "total_issues_tracked": 50
            }
        """
        if not reviews:
            return {"trends": [], "period_current": "", "period_previous": "", "total_issues_tracked": 0}

        # Parse dates and find reference date
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
            return {"trends": [], "period_current": "", "period_previous": "", "total_issues_tracked": 0}

        # Determine reference date
        if reference_date:
            ref_date = datetime.strptime(reference_date, "%Y-%m-%d")
        else:
            ref_date = max(dt for dt, _ in dated_reviews)

        current_start = ref_date - timedelta(days=lookback_days - 1)
        previous_start = ref_date - timedelta(days=lookback_days * 2 - 1)
        previous_end = current_start - timedelta(days=1)

        # Count issues in current period
        current_issues = Counter()
        for dt, review in dated_reviews:
            if current_start <= dt <= ref_date:
                for issue in (review.get('issues') or []):
                    if isinstance(issue, str) and issue.strip():
                        current_issues[issue.lower().strip()] += 1

        # Count issues in previous period
        previous_issues = Counter()
        for dt, review in dated_reviews:
            if previous_start <= dt <= previous_end:
                for issue in (review.get('issues') or []):
                    if isinstance(issue, str) and issue.strip():
                        previous_issues[issue.lower().strip()] += 1

        # Compute growth rates
        all_issues = set(current_issues.keys()) | set(previous_issues.keys())
        trends = []

        for issue in all_issues:
            curr = current_issues.get(issue, 0)
            prev = previous_issues.get(issue, 0)

            if prev == 0:
                growth_rate = 999.0 if curr > 0 else 0.0
            else:
                growth_rate = ((curr - prev) / prev) * 100

            if growth_rate > 100:
                trend_type = "emerging"
            elif growth_rate < -20:
                trend_type = "declining"
            else:
                trend_type = "stable"

            trends.append({
                "issue": issue,
                "trend": trend_type,
                "volume_current": curr,
                "volume_previous": prev,
                "growth_rate": round(growth_rate, 1) if growth_rate != 999.0 else 999.0,
            })

        # Sort: emerging first (by growth desc), then stable, then declining
        trend_order = {"emerging": 0, "stable": 1, "declining": 2}
        trends.sort(key=lambda x: (trend_order[x['trend']], -x['growth_rate']))

        return {
            "trends": trends,
            "period_current": f"{current_start.strftime('%Y-%m-%d')} to {ref_date.strftime('%Y-%m-%d')}",
            "period_previous": f"{previous_start.strftime('%Y-%m-%d')} to {previous_end.strftime('%Y-%m-%d')}",
            "total_issues_tracked": len(all_issues),
        }

    def detect_trends_from_db(
        self, conn, lookback_days: int = 7
    ) -> Dict[str, Any]:
        """
        Live DB version of trend detection.
        Queries reviews_enriched for current and previous period issue volumes.
        """
        cursor = conn.cursor()

        # Current period
        cursor.execute("""
            SELECT unnest(issues) as issue, COUNT(*) as count
            FROM reviews_enriched
            WHERE created_at >= NOW() - INTERVAL '%s days'
              AND issues IS NOT NULL
            GROUP BY issue
        """, (lookback_days,))
        current = {row['issue']: row['count'] for row in cursor.fetchall()}

        # Previous period
        cursor.execute("""
            SELECT unnest(issues) as issue, COUNT(*) as count
            FROM reviews_enriched
            WHERE created_at >= NOW() - INTERVAL '%s days'
              AND created_at < NOW() - INTERVAL '%s days'
              AND issues IS NOT NULL
            GROUP BY issue
        """, (lookback_days * 2, lookback_days))
        previous = {row['issue']: row['count'] for row in cursor.fetchall()}
        cursor.close()

        # Compute growth (same logic as in-memory version)
        all_issues = set(current.keys()) | set(previous.keys())
        trends = []
        for issue in all_issues:
            curr = current.get(issue, 0)
            prev = previous.get(issue, 0)
            if prev == 0:
                growth_rate = 999.0 if curr > 0 else 0.0
            else:
                growth_rate = ((curr - prev) / prev) * 100

            trend_type = "emerging" if growth_rate > 100 else "declining" if growth_rate < -20 else "stable"
            trends.append({
                "issue": issue,
                "trend": trend_type,
                "volume_current": curr,
                "volume_previous": prev,
                "growth_rate": round(growth_rate, 1) if growth_rate != 999.0 else 999.0,
            })

        trend_order = {"emerging": 0, "stable": 1, "declining": 2}
        trends.sort(key=lambda x: (trend_order[x['trend']], -x['growth_rate']))

        return {
            "trends": trends,
            "total_issues_tracked": len(all_issues),
            "source": "database",
        }
