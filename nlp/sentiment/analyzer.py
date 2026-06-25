from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re
from collections import Counter
from typing import List, Dict, Any

# Severity weights for priority computation
SEVERITY_WEIGHTS = {
    'Critical': 4.0,   # App crashes, data loss, payment failures
    'High': 3.0,       # Major feature broken, cannot use app
    'Medium': 2.0,     # Annoying but workable, degraded experience
    'Low': 1.0,        # Minor inconvenience, cosmetic issues
}


def compute_priority_score(sentiment: str, severity: str, volume: int) -> float:
    """
    Compute priority score for issue triage.
    Higher score = needs immediate attention.
    """
    base_score = SEVERITY_WEIGHTS.get(severity, 1.0)
    # Negative sentiment amplifies severity
    if sentiment and sentiment.upper() == 'NEGATIVE':
        base_score *= 1.5
    # Volume amplifies impact (capped at 2x)
    volume_multiplier = min(volume / 100.0, 2.0) if volume else 0.1
    return round(base_score * max(volume_multiplier, 0.1), 2)


class SentimentAnalyzer:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.version = "vaderSentiment-3.3.2+rating-guardrails"

    @staticmethod
    def _contains_strong_negative_text(text_lower: str) -> bool:
        strong_negative = [
            "crash", "crashes", "crashing", "unusable", "broken", "doesn't work",
            "doesnt work", "not working", "can't use", "cannot use", "won't open",
            "wont open", "terrible", "worst", "hate", "scam", "fraud",
        ]
        return any(term in text_lower for term in strong_negative)

    @classmethod
    def _apply_rating_guardrails(cls, compound: float, rating: int | None, text: str = "") -> float:
        """
        Star ratings are explicit user feedback. VADER can over-credit mixed
        reviews that contain one positive clause, so clamp extreme ratings.
        """
        if rating is None:
            return compound

        text_lower = (text or "").lower()
        if rating <= 1:
            return min(compound, -0.35)
        if rating == 2:
            return min(compound, -0.10)
        if rating == 4 and compound < -0.05 and not cls._contains_strong_negative_text(text_lower):
            return max(compound, 0.10)
        if rating >= 5 and not cls._contains_strong_negative_text(text_lower):
            return max(compound, 0.35)
        return compound

    @staticmethod
    def _label_from_score(compound: float, neutral_confidence: float = 1.0) -> tuple[str, float]:
        if compound >= 0.05:
            return "POSITIVE", min(abs(compound), 1.0)
        if compound <= -0.05:
            return "NEGATIVE", min(abs(compound), 1.0)
        return "NEUTRAL", neutral_confidence

    def analyze(self, text: str, rating: int = None) -> dict:
        """
        Analyzes sentiment using VADER + star rating override.

        Star ratings are a strong explicit signal:
          - 1-2 stars => at most NEUTRAL (never POSITIVE); typically NEGATIVE
          - 4-5 stars => POSITIVE (overrides weak VADER negative)
          - 3 stars   => trust VADER

        Returns dict with: score, label, confidence, version
        """
        if not text or not text.strip():
            return {
                "score": 0.0,
                "label": "NEUTRAL",
                "confidence": 1.0,
                "version": self.version
            }

        scores = self.analyzer.polarity_scores(text)
        vader_compound = scores['compound']

        # --- Rating-aware sentiment blending ---
        # Convert rating to a score in [-1, 1]: 1=>-1.0, 2=>-0.5, 3=>0.0, 4=>0.5, 5=>1.0
        if rating is not None:
            rating_score = (rating - 3) / 2.0
            if rating <= 2:
                # Low rating: user is explicitly unhappy. Weight rating heavily.
                blended = 0.7 * rating_score + 0.3 * vader_compound
            elif rating >= 4:
                # High rating: user is explicitly happy. Weight rating heavily.
                blended = 0.7 * rating_score + 0.3 * vader_compound
            else:
                # 3 stars: ambiguous, trust VADER more.
                blended = 0.4 * rating_score + 0.6 * vader_compound
            compound = self._apply_rating_guardrails(blended, rating, text)
        else:
            compound = vader_compound

        label, confidence = self._label_from_score(compound, scores['neu'])

        # Safety net: 1-2 star reviews must never be labelled POSITIVE.
        # VADER can over-weight isolated positive clauses ("sound quality is better")
        # in otherwise negative reviews. If the model still lands on POSITIVE for a
        # low-star review, downgrade to NEUTRAL — the least harmful wrong label.
        if rating is not None and rating <= 2 and label == "POSITIVE":
            label = "NEUTRAL"
            compound = 0.0
            confidence = round(scores['neu'], 4)

        return {
            "score": round(compound, 4),
            "label": label,
            "confidence": round(confidence, 4),
            "version": self.version
        }


class EnhancedSentimentAnalyzer:
    """
    Phase 4: Rule-based intent classifier, severity scorer, and emotional-tone
    detector.  Used as a fast, deterministic fallback when the LLM is unavailable.
    For LLM-powered extraction, use nlp.pipeline.extract_issues_and_topics().
    """

    # Keyword / phrase banks for intent detection
    _COMPLAINT_KEYWORDS = [
        "crash", "broken", "bug", "error", "fail", "freeze", "lag", "slow",
        "annoying", "frustrating", "horrible", "terrible", "useless", "hate",
        "worst", "uninstall", "waste", "doesn't work", "not working", "problem",
        "issue", "can't", "cannot", "won't", "disappointed", "bad", "sucks",
    ]
    _PRAISE_KEYWORDS = [
        "love", "great", "amazing", "fantastic", "awesome", "perfect", "best",
        "excellent", "smooth", "fast", "recommend", "gem", "beautiful", "wonderful",
        "incredible", "superb", "brilliant", "nice", "good", "happy",
    ]
    _QUESTION_KEYWORDS = [
        "why", "how", "when", "what", "where", "is there", "can i",
        "does anyone", "anyone know", "?",
    ]
    _SUGGESTION_KEYWORDS = [
        "should", "wish", "hope", "please add", "it would be nice",
        "feature request", "improve", "could you", "add a", "bring back",
    ]

    # Severity keyword banks
    _CRITICAL_KEYWORDS = [
        "crash", "crashes", "data loss", "lost", "payment fail", "unusable",
        "can't open", "won't open", "stuck", "bricked", "doesn't launch",
    ]
    _HIGH_KEYWORDS = [
        "broken", "not working", "doesn't work", "can't use", "cannot use",
        "keeps closing", "force close", "won't play", "won't download",
    ]
    _MEDIUM_KEYWORDS = [
        "annoying", "laggy", "slow", "confusing", "cluttered", "too many",
        "frustrating", "difficult", "hard to", "repetitive",
    ]
    _LOW_KEYWORDS = [
        "minor", "cosmetic", "slightly", "a bit", "could be better",
        "not ideal", "small issue",
    ]

    # Emotional tone
    _FRUSTRATED_KEYWORDS = [
        "frustrat", "annoy", "angry", "furious", "irritat", "rage", "hate",
        "sick of", "fed up", "done with",
    ]
    _SATISFIED_KEYWORDS = [
        "love", "happy", "pleased", "satisfied", "great", "amazing",
        "enjoy", "delight", "perfect", "fantastic",
    ]
    _CONFUSED_KEYWORDS = [
        "confused", "don't understand", "why", "how do", "unclear",
        "complicated", "doesn't make sense",
    ]
    _HOPEFUL_KEYWORDS = [
        "hope", "wish", "looking forward", "excited", "can't wait",
        "would be nice", "please fix",
    ]

    def analyze_intent(self, text: str) -> str:
        """Phase 4: Classify user intent from review text."""
        text_lower = (text or "").lower()
        scores = {
            'Complaint': self._score_keywords(text_lower, self._COMPLAINT_KEYWORDS),
            'Praise':    self._score_keywords(text_lower, self._PRAISE_KEYWORDS),
            'Question':  self._score_keywords(text_lower, self._QUESTION_KEYWORDS),
            'Suggestion': self._score_keywords(text_lower, self._SUGGESTION_KEYWORDS),
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'Complaint'

    def analyze_severity(self, text: str) -> str:
        """Phase 4: Score severity from review text using keyword matching."""
        text_lower = (text or "").lower()
        scores = {
            'Critical': self._score_keywords(text_lower, self._CRITICAL_KEYWORDS),
            'High':     self._score_keywords(text_lower, self._HIGH_KEYWORDS),
            'Medium':   self._score_keywords(text_lower, self._MEDIUM_KEYWORDS),
            'Low':      self._score_keywords(text_lower, self._LOW_KEYWORDS),
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'Medium'

    def analyze_emotional_tone(self, text: str) -> str:
        """Phase 4: Detect the dominant emotional tone."""
        text_lower = (text or "").lower()
        scores = {
            'Frustrated': self._score_keywords(text_lower, self._FRUSTRATED_KEYWORDS),
            'Satisfied':  self._score_keywords(text_lower, self._SATISFIED_KEYWORDS),
            'Confused':   self._score_keywords(text_lower, self._CONFUSED_KEYWORDS),
            'Hopeful':    self._score_keywords(text_lower, self._HOPEFUL_KEYWORDS),
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'Neutral'

    def full_analysis(self, text: str, rating: int = None) -> dict:
        """
        Phase 4: Run full enhanced analysis (rating-aware sentiment + intent + severity + tone).
        Returns a unified dict compatible with the Phase 1 schema columns.
        """
        _v = SentimentIntensityAnalyzer()
        scores = _v.polarity_scores(text or "")
        vader_compound = scores['compound']
        
        sentiment_result = SentimentAnalyzer().analyze(text or "", rating=rating)
        sentiment = sentiment_result['label']
        confidence = sentiment_result['confidence']

        return {
            'sentiment': sentiment,
            'confidence': round(confidence, 4),
            'user_intent': self.analyze_intent(text),
            'severity': self.analyze_severity(text),
            'emotional_tone': self.analyze_emotional_tone(text),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _score_keywords(text_lower: str, keyword_list: list) -> int:
        return sum(1 for kw in keyword_list if kw in text_lower)


def compute_priority_issues(reviews: List[Dict], top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Phase 4: Aggregate issues from reviews, compute priority scores, and
    return the top-N issues sorted by priority descending.
    """
    issue_data: Dict[str, Dict] = {}
    for r in reviews:
        issues = r.get('issues') or []
        if isinstance(issues, str):
            issues = [issues]
        for issue_text in issues:
            key = issue_text.lower().strip()
            if not key:
                continue
            if key not in issue_data:
                issue_data[key] = {
                    'issue': issue_text,
                    'count': 0,
                    'severities': [],
                    'sentiments': [],
                    'topics': set(),
                }
            issue_data[key]['count'] += 1
            sev = r.get('severity') or 'Medium'
            issue_data[key]['severities'].append(sev)
            issue_data[key]['sentiments'].append(r.get('sentiment', 'NEUTRAL'))
            for t in (r.get('topics') or []):
                issue_data[key]['topics'].add(t)

    results = []
    for key, data in issue_data.items():
        sev_counter = Counter(data['severities'])
        dominant_severity = sev_counter.most_common(1)[0][0]
        sent_counter = Counter(data['sentiments'])
        dominant_sentiment = sent_counter.most_common(1)[0][0]
        score = compute_priority_score(dominant_sentiment, dominant_severity, data['count'])
        results.append({
            'issue': data['issue'],
            'volume': data['count'],
            'severity': dominant_severity,
            'sentiment': dominant_sentiment,
            'priority_score': score,
            'topics': sorted(data['topics']),
        })

    results.sort(key=lambda x: x['priority_score'], reverse=True)
    return results[:top_n]
