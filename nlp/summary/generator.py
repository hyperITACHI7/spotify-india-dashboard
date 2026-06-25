"""
nlp/summary/generator.py

Phase 3: Synthesizes analyst-quality topic summaries using the Groq LLM.

Instead of copying review text verbatim, this module generates concise
analytical summaries that capture the dominant frustration or praise pattern
for each topic (and optionally sub-topic).

Usage:
    # Standalone
    from nlp.summary.generator import TopicSummaryGenerator, generate_topic_summaries

    generator = TopicSummaryGenerator(client)
    summary = generator.generate_summary("Ads Experience", reviews)

    # As post-enrichment pipeline step
    generate_topic_summaries(conn, llm_client)
"""

import json
from collections import Counter
from typing import List, Dict, Any, Optional


class TopicSummaryGenerator:
    """
    Generates analyst-quality synthesized summaries for a topic
    based on its reviews, issues, and sub-topics.

    Rules:
    - 20-30 words maximum
    - Objective, analytical tone (not conversational)
    - Represents dominant frustration or praise
    - Never copies review text verbatim
    """

    def __init__(self, client=None):
        """
        Args:
            client: Groq API client (or None for rule-based fallback).
        """
        self.client = client

    def generate_summary(self, topic_label: str, reviews: List[Dict[str, Any]],
                         sub_topic: str = None) -> str:
        """
        Generate a synthesized summary for a topic (or sub-topic) across its reviews.

        Args:
            topic_label: Human-readable topic name (e.g. 'Ads Experience').
            reviews: List of review dicts with keys: text, sentiment, severity, issues.
            sub_topic: Optional sub-topic name to scope the summary.

        Returns:
            A 20-30 word analytical summary string.
        """
        if not reviews:
            return f"No reviews available for {topic_label}."

        # Use top 20 most representative reviews (sorted by severity then date)
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_reviews = sorted(
            reviews,
            key=lambda r: severity_order.get(r.get("severity", "Medium"), 2)
        )
        sample = sorted_reviews[:20]

        # Build context from review texts + issues
        lines = []
        for r in sample:
            text_snippet = (r.get("text") or "")[:150]
            issues_csv = ", ".join(r.get("issues") or [])
            line = f"- [{r.get('sentiment', 'NEUTRAL')}] {text_snippet}"
            if issues_csv:
                line += f"  | Issues: {issues_csv}"
            lines.append(line)

        context_text = "\n".join(lines)
        scope = f"{topic_label} > {sub_topic}" if sub_topic else topic_label

        if self.client:
            return self._llm_summarize(scope, context_text, sample)
        else:
            return self._rule_based_summarize(scope, sample)

    # ------------------------------------------------------------------
    # LLM-backed synthesis
    # ------------------------------------------------------------------

    def _llm_summarize(self, scope: str, context_text: str,
                       sample: List[Dict]) -> str:
        """Call Groq LLM to synthesize an analytical summary."""
        neg_count = sum(1 for r in sample if r.get("sentiment") == "NEGATIVE")
        pos_count = sum(1 for r in sample if r.get("sentiment") == "POSITIVE")
        total = len(sample)

        prompt = f"""You are a senior product analyst at Spotify. Synthesize a concise analytical summary for the topic "{scope}".

Context (sample of {total} reviews — {neg_count} negative, {pos_count} positive):
{context_text}

Requirements:
- Length: exactly 20-30 words
- Tone: objective, analytical — NOT conversational, do NOT start with "Users"
- Focus: dominant frustration or praise pattern with specific feature names
- NEVER copy any review text verbatim
- Capture the root cause, not symptoms
- Include severity signal if applicable (e.g., "critical", "widespread")

Example good summaries (each is 20-30 words):
- "Unskippable ads after every song and aggressive premium upsell popups erode free-tier experience, driving churn rather than conversion."
- "Discover Weekly praised for relevance but criticised for repetitive suggestions; niche-genre listeners report algorithm rarely learns new preferences."
- "Downloaded tracks disappear after app updates — a cache-persistence regression making offline mode unreliable for commuters."

Generate summary (20-30 words only, no markdown, no quotes):"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            summary = response.choices[0].message.content.strip()
            # Strip surrounding quotes if present
            summary = summary.strip('"\'')
            # Strip markdown fences
            if summary.startswith("```"):
                summary = summary.split("\n", 1)[1] if "\n" in summary else summary[3:]
            if summary.endswith("```"):
                summary = summary[:-3]
            summary = summary.strip()

            # Enforce word count
            words = summary.split()
            if len(words) > 35:
                summary = " ".join(words[:30]) + "..."

            return summary

        except Exception as e:
            print(f"  LLM summary error for '{scope}': {e}")
            return self._rule_based_summarize(scope, sample)

    # ------------------------------------------------------------------
    # Rule-based fallback (when LLM unavailable)
    # ------------------------------------------------------------------

    def _rule_based_summarize(self, scope: str,
                              sample: List[Dict]) -> str:
        """
        Heuristic summary: aggregates complaint issues + sentiment signals
        into a varied, analytical sentence. Never copies review text.
        """
        # Count complaint issues only — skip pure praise
        issue_counter = Counter()
        for r in sample:
            if r.get("sentiment") in ("POSITIVE", "POS") and r.get("user_intent") != "Complaint":
                continue
            for issue in (r.get("issues") or []):
                issue_counter[issue.lower()] += 1

        top_issues = [issue for issue, _ in issue_counter.most_common(3)]

        total = len(sample)
        neg_count = sum(1 for r in sample if r.get("sentiment") in ("NEGATIVE", "NEG"))
        pos_count = sum(1 for r in sample if r.get("sentiment") in ("POSITIVE", "POS"))
        neg_pct = round(neg_count / total * 100) if total else 0
        pos_pct = round(pos_count / total * 100) if total else 0

        critical_count = sum(
            1 for r in sample
            if r.get("severity") in ("Critical", "High") and r.get("sentiment") in ("NEGATIVE", "NEG")
        )

        if not top_issues:
            if pos_pct > 60 and neg_pct < 20:
                return f"Predominantly positive reception for {scope} with no recurring complaint."
            if neg_pct > 40:
                return f"{scope} receives {neg_pct}% negative feedback but lacks a single dominant issue."
            return f"Mixed feedback for {scope} — no dominant pattern across {total} reviews."

        issue_a = top_issues[0].capitalize()
        issue_b = top_issues[1] if len(top_issues) > 1 else None
        issue_c = top_issues[2] if len(top_issues) > 2 else None

        # Single dominant issue
        if not issue_b:
            if critical_count > 0:
                return f"{issue_a} is the critical pain point driving the majority of negative feedback."
            return f"{issue_a} is the primary concern, driving {neg_pct}% negative sentiment."

        # Two or more issues — vary framing by severity and volume
        if critical_count >= 2:
            return f"{issue_a} and {issue_b} are the critical pain points."
        if critical_count == 1:
            return f"{issue_a} (critical severity) and {issue_b} are the dominant pain points."

        if neg_pct >= 65:
            if issue_c:
                return f"Overwhelmingly negative: {issue_a}, {issue_b}, and {issue_c} are recurring problems."
            return f"{issue_a} and {issue_b} drive a {neg_pct}% negative sentiment rate."
        if neg_pct >= 45:
            return f"{issue_a} and {issue_b} are the leading complaints, affecting {neg_pct}% of reviewers."
        if neg_pct >= 25:
            return f"Mixed reception; {issue_a} and {issue_b} appear as recurring concerns."
        # Mostly positive
        return f"Largely positive; minor friction points include {issue_a} and {issue_b}."


# ======================================================================
# PIPELINE INTEGRATION: generate summaries for all topics after enrichment
# ======================================================================

def compute_sentiment_distribution(reviews: List[Dict]) -> Dict[str, float]:
    """Returns {"positive": 0.x, "negative": 0.y, "neutral": 0.z} from a list of review dicts."""
    if not reviews:
        return {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    total = len(reviews)
    pos = sum(1 for r in reviews if r.get("sentiment", "").upper() in ("POSITIVE", "POS"))
    neg = sum(1 for r in reviews if r.get("sentiment", "").upper() in ("NEGATIVE", "NEG"))
    neu = total - pos - neg
    return {
        "positive": round(pos / total, 2),
        "negative": round(neg / total, 2),
        "neutral": round(neu / total, 2),
    }


def extract_dominant_issues(reviews: List[Dict], top_n: int = 5) -> List[str]:
    """Returns the top-N most frequent issues (lowercased) from a list of review dicts."""
    counter = Counter()
    for r in reviews:
        for issue in (r.get("issues") or []):
            counter[issue.lower()] += 1
    return [issue for issue, _ in counter.most_common(top_n)]


def generate_topic_summaries(conn, llm_client=None, dry_run: bool = False):
    """
    Phase 3 post-enrichment step.

    For every topic that has enriched reviews, generates a synthesized summary
    (and optionally sub-topic summaries) and upserts into the `topic_summaries` table.

    Args:
        conn: psycopg2 connection (or None for dry-run).
        llm_client: Groq client (or None for rule-based fallback).
        dry_run: If True, print summaries instead of writing to DB.
    """
    generator = TopicSummaryGenerator(client=llm_client)

    # ------------------------------------------------------------------
    # Step 1: Discover topics from the DB (or mock fallback)
    # ------------------------------------------------------------------
    if not dry_run and conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT unnest(e.sub_topics) AS sub_topic,
                            rt.topic_id
            FROM reviews_enriched e
            JOIN review_topics rt ON rt.review_id = e.review_id
            WHERE e.sub_topics IS NOT NULL
        """)
        # Build a map: topic_id -> {sub_topics}
        topic_sub_map: Dict[str, set] = {}
        for row in cursor.fetchall():
            tid = row["topic_id"]
            sub = row["sub_topic"]
            topic_sub_map.setdefault(tid, set())
            if sub:
                topic_sub_map[tid].add(sub)

        # Also discover topics from review_topics directly
        cursor.execute("SELECT DISTINCT topic_id FROM review_topics")
        for row in cursor.fetchall():
            topic_sub_map.setdefault(row["topic_id"], set())

        topics_to_summarize = list(topic_sub_map.keys())
        print(f"Phase 3: Found {len(topics_to_summarize)} topics to summarize.")
    else:
        # Dry-run: use taxonomy topics
        try:
            import yaml
            with open("config/taxonomy.yaml", "r") as f:
                taxonomy = yaml.safe_load(f)
            topics_to_summarize = [cat["id"] for cat in taxonomy.get("categories", [])]
            topic_sub_map = {
                cat["id"]: set(cat.get("subtopics", []))
                for cat in taxonomy.get("categories", [])
            }
        except Exception:
            topics_to_summarize = []
            topic_sub_map = {}
        print(f"Phase 3 [DRY-RUN]: {len(topics_to_summarize)} topics from taxonomy.")

    # ------------------------------------------------------------------
    # Step 2: For each topic, fetch reviews and generate summary
    # ------------------------------------------------------------------
    from nlp.topics.tagger import HierarchicalTopicTagger
    try:
        htagger = HierarchicalTopicTagger()
    except Exception:
        htagger = None

    results = []
    for topic_id in topics_to_summarize:
        label = topic_id.replace("_", " ").title().replace(" And ", " & ")
        if htagger:
            label = htagger.topic_id_to_label.get(topic_id, label)

        # Fetch reviews for this topic
        reviews = _fetch_reviews_for_topic(conn, topic_id, dry_run)
        if not reviews:
            continue

        # Parent-topic summary
        summary_text = generator.generate_summary(label, reviews)
        sentiment_dist = compute_sentiment_distribution(reviews)
        dominant = extract_dominant_issues(reviews)

        result = {
            "topic_id": topic_id,
            "sub_topic": None,
            "summary": summary_text,
            "review_count": len(reviews),
            "sentiment_dist": sentiment_dist,
            "dominant_issues": dominant,
        }
        results.append(result)

        if dry_run:
            print(f"\n  [{label}] ({len(reviews)} reviews)")
            print(f"    Summary: {summary_text}")
            print(f"    Sentiment: {sentiment_dist}")
            print(f"    Top issues: {dominant}")
        else:
            _upsert_summary(conn, result)

        # Sub-topic summaries (only for sub-topics with enough reviews)
        subs = topic_sub_map.get(topic_id, set())
        for sub in subs:
            sub_reviews = [
                r for r in reviews
                if sub in (r.get("sub_topics") or [])
            ]
            if len(sub_reviews) < 3:
                continue  # Not enough data

            sub_summary = generator.generate_summary(label, sub_reviews, sub_topic=sub)
            sub_sentiment = compute_sentiment_distribution(sub_reviews)
            sub_dominant = extract_dominant_issues(sub_reviews)

            sub_result = {
                "topic_id": topic_id,
                "sub_topic": sub,
                "summary": sub_summary,
                "review_count": len(sub_reviews),
                "sentiment_dist": sub_sentiment,
                "dominant_issues": sub_dominant,
            }
            results.append(sub_result)

            if dry_run:
                print(f"    [{sub}] ({len(sub_reviews)} reviews): {sub_summary}")
            else:
                _upsert_summary(conn, sub_result)

    if not dry_run and conn:
        conn.commit()
        print(f"Phase 3: Upserted {len(results)} topic/sub-topic summaries.")

    return results


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _fetch_reviews_for_topic(conn, topic_id: str, dry_run: bool) -> List[Dict]:
    """Fetch enriched reviews for a given topic_id from the DB, or mock data in dry-run."""
    if dry_run or not conn:
        # Use mock data
        try:
            from aggregation.discovery_stats import ALL_REVIEWS
            return [
                r for r in ALL_REVIEWS
                if topic_id in r.get("topics", [])
            ]
        except Exception:
            return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                coalesce(r.text_translated, r.text_original) AS text,
                e.sentiment_label AS sentiment,
                e.severity,
                e.issues,
                e.sub_topics
            FROM reviews_raw r
            JOIN reviews_enriched e ON r.id = e.review_id
            JOIN review_topics rt ON rt.review_id = r.id
            WHERE rt.topic_id = %s
            ORDER BY r.created_at DESC
            LIMIT 50
        """, (topic_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"  Failed to fetch reviews for topic '{topic_id}': {e}")
        return []


def _upsert_summary(conn, result: Dict):
    """Upsert a summary row into the topic_summaries table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO topic_summaries
                (topic_id, sub_topic, summary_text, review_count,
                 sentiment_distribution, dominant_issues, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (topic_id, COALESCE(sub_topic, '__parent__'))
            DO UPDATE SET
                summary_text = EXCLUDED.summary_text,
                review_count = EXCLUDED.review_count,
                sentiment_distribution = EXCLUDED.sentiment_distribution,
                dominant_issues = EXCLUDED.dominant_issues,
                generated_at = NOW()
        """, (
            result["topic_id"],
            result["sub_topic"],
            result["summary"],
            result["review_count"],
            json.dumps(result["sentiment_dist"]),
            result["dominant_issues"] or None,
        ))
    except Exception as e:
        print(f"  Failed to upsert summary for {result['topic_id']}/{result['sub_topic']}: {e}")
        conn.rollback()
