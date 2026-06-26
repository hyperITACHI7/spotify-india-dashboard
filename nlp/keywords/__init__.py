"""
nlp/keywords/__init__.py

Phase 5: Intelligent Buzzword Extraction.
Extracts actionable, issue-based buzzwords from review intelligence.

Key design decisions:
- 3-word cap: issues with 4+ words are too specific to match reliably across reviews
- Sentiment-based bucketing: an issue goes to Frustrations if it appears predominantly
  in negative reviews, Praise if predominantly positive. This prevents complaint labels
  (e.g. "removed replays", "no ad skip") from leaking into the Praise bucket just
  because they were mentioned in a mixed 4-star review.
"""

from collections import Counter
from typing import List, Dict, Any, Tuple

MAX_BUZZWORD_WORDS = 3  # hard cap — 4+ word phrases match too few reviews


def extract_buzzwords_bimodal(
    reviews: List[Dict],
    top_n: int = 20,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Single-pass bimodal buzzword extractor.

    Scans all reviews once, counting how often each issue label appears in
    NEGATIVE vs POSITIVE reviews. An issue is classified as:
      - Frustration: neg_count >= pos_count (even a tie defaults to frustration)
      - Praise:      pos_count > neg_count

    Enforces MAX_BUZZWORD_WORDS cap — any issue label with more words is skipped.

    Returns (negative_buzzwords, positive_buzzwords), each a list of dicts:
      {"text": str, "count": int, "topics": List[str]}
    """
    issue_neg: Counter = Counter()
    issue_pos: Counter = Counter()
    issue_meta: Dict[str, Dict] = {}

    for review in reviews:
        sentiment = (review.get('sentiment') or '').upper()
        if sentiment not in ('NEGATIVE', 'POSITIVE'):
            continue
        issues = review.get('issues') or []
        if isinstance(issues, str):
            try:
                import json
                issues = json.loads(issues)
            except Exception:
                issues = [issues]

        for raw_issue in issues:
            key = raw_issue.lower().strip()
            if not key:
                continue
            # Hard cap: skip labels with more than MAX_BUZZWORD_WORDS words
            if len(key.split()) > MAX_BUZZWORD_WORDS:
                continue

            if sentiment == 'NEGATIVE':
                issue_neg[key] += 1
            else:
                issue_pos[key] += 1

            if key not in issue_meta:
                issue_meta[key] = {'display': raw_issue, 'topics': set()}
            for t in (review.get('topics') or []):
                issue_meta[key]['topics'].add(t)

    all_keys = set(issue_neg.keys()) | set(issue_pos.keys())

    frustrations = []
    praises = []

    for key in all_keys:
        neg = issue_neg.get(key, 0)
        pos = issue_pos.get(key, 0)
        meta = issue_meta.get(key, {'display': key, 'topics': set()})
        entry = {
            'text': meta['display'],
            'topics': sorted(meta['topics']),
        }
        # Ties go to frustrations — safer default for ambiguous issues
        if neg >= pos:
            entry['count'] = neg
            frustrations.append((neg, entry))
        else:
            entry['count'] = pos
            praises.append((pos, entry))

    frustrations.sort(key=lambda x: x[0], reverse=True)
    praises.sort(key=lambda x: x[0], reverse=True)

    return (
        [e for _, e in frustrations[:top_n]],
        [e for _, e in praises[:top_n]],
    )


# ---------------------------------------------------------------------------
# Legacy wrappers kept for any direct callers outside get_top_keywords
# ---------------------------------------------------------------------------

def extract_frustration_keywords(reviews: List[Dict], top_n: int = 20) -> List[Dict]:
    neg, _ = extract_buzzwords_bimodal(reviews, top_n=top_n)
    return neg


def extract_praise_keywords(reviews: List[Dict], top_n: int = 20) -> List[Dict]:
    _, pos = extract_buzzwords_bimodal(reviews, top_n=top_n)
    return pos
