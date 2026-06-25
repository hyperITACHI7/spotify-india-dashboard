"""
nlp/keywords/__init__.py

Phase 5: Intelligent Buzzword Extraction.
Extracts actionable, issue-based buzzwords from review intelligence
(instead of generic adjectives from raw text).
"""

from collections import Counter
from typing import List, Dict, Any, Optional


class IntelligentBuzzwordExtractor:
    """
    Phase 5: Extracts buzzwords from structured issues, not raw review text.
    This solves the "P1: Generic Keywords" problem where the old approach
    extracted adjectives like "good", "bad", "nice" instead of actionable issues.
    """

    def extract_buzzwords(
        self,
        reviews: List[Dict],
        sentiment_filter: Optional[str] = None,
        severity_filter: Optional[List[str]] = None,
        top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Extract buzzwords from issues in reviews.

        Args:
            reviews: List of review dicts, each with an 'issues' key.
            sentiment_filter: Optional sentiment label to filter by (e.g. 'NEGATIVE').
            severity_filter: Optional list of severity levels to include.
            top_n: Number of top buzzwords to return.

        Returns:
            [{"text": "premium popups", "count": 45, "sentiment": "Negative",
              "avg_severity": "High", "topics": ["ads_experience"]}, ...]
        """
        filtered = reviews
        if sentiment_filter:
            norm = sentiment_filter.upper()
            filtered = [r for r in filtered if r.get('sentiment', '').upper() == norm]
        if severity_filter:
            sev_set = {s.lower() for s in severity_filter}
            filtered = [r for r in filtered if (r.get('severity') or '').lower() in sev_set]

        issue_counter: Counter = Counter()
        issue_meta: Dict[str, Dict] = {}  # track severity, topics per issue

        for review in filtered:
            issues = review.get('issues') or []
            if isinstance(issues, str):
                issues = [issues]
            for issue_text in issues:
                key = issue_text.lower().strip()
                if not key:
                    continue
                issue_counter[key] += 1

                if key not in issue_meta:
                    issue_meta[key] = {
                        'display': issue_text,
                        'severities': [],
                        'topics': set(),
                    }
                sev = review.get('severity') or 'Medium'
                issue_meta[key]['severities'].append(sev)
                for t in (review.get('topics') or []):
                    issue_meta[key]['topics'].add(t)

        # Build buzzword list
        buzzwords = []
        for issue_key, count in issue_counter.most_common(top_n):
            meta = issue_meta[issue_key]
            # Dominant severity
            sev_counter = Counter(meta['severities'])
            dominant_severity = sev_counter.most_common(1)[0][0] if sev_counter else 'Medium'

            buzzwords.append({
                'text': meta['display'],
                'count': count,
                'sentiment': sentiment_filter or 'Mixed',
                'avg_severity': dominant_severity,
                'topics': sorted(meta['topics']),
            })

        return buzzwords


def extract_frustration_keywords(reviews: List[Dict], top_n: int = 20) -> List[Dict]:
    """
    Phase 5: Extract keywords specifically from negative/high-severity reviews.
    Returns issue-based buzzwords (not adjectives).
    """
    negative_reviews = [
        r for r in reviews
        if r.get('sentiment', '').upper() == 'NEGATIVE'
        and (r.get('severity') or 'Medium') in ('High', 'Critical')
    ]
    # If filtering leaves too few, widen to all negative
    if len(negative_reviews) < 5:
        negative_reviews = [r for r in reviews if r.get('sentiment', '').upper() == 'NEGATIVE']

    return IntelligentBuzzwordExtractor().extract_buzzwords(
        negative_reviews,
        sentiment_filter='Negative',
        severity_filter=['High', 'Critical'],
        top_n=top_n,
    )


def extract_praise_keywords(reviews: List[Dict], top_n: int = 20) -> List[Dict]:
    """
    Phase 5: Extract keywords from positive reviews.
    Returns issue/praise-based buzzwords (not generic adjectives).
    """
    positive_reviews = [r for r in reviews if r.get('sentiment', '').upper() == 'POSITIVE']

    return IntelligentBuzzwordExtractor().extract_buzzwords(
        positive_reviews,
        sentiment_filter='Positive',
        top_n=top_n,
    )
