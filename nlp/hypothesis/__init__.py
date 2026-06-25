"""
nlp/hypothesis/__init__.py

Phase 7: Hypothesis Generation.
Reads the full dashboard report — topic distribution, worst review excerpts,
priority issues, trends, clusters — then asks the LLM to generate 5 grounded,
testable hypotheses. Requires topic matrix to be populated (NLP done).
"""

import json
from typing import List, Dict, Any, Optional
from core import llm as _llm


class HypothesisGenerator:

    def generate(
        self,
        topic_stats: Dict[str, Any],
        topic_matrix: List[Dict],
        top_issues: List[Dict],
        trends: List[Dict],
        clusters: List[Dict],
        worst_reviews_by_topic: Optional[Dict[str, List[Dict]]] = None,
        cache_key: tuple = (),
    ) -> List[Dict[str, str]]:
        """
        Generate 5 product hypotheses grounded in topic distribution + real review excerpts.
        Returns a list with a single error-flagged dict on failure.
        """
        volume   = topic_stats.get('total_reviews', 0)
        sent_dist = topic_stats.get('sentiment_distribution', {})
        neg_pct  = round((sent_dist.get('NEGATIVE', 0) / volume) * 100) if volume else 0
        pos_pct  = round((sent_dist.get('POSITIVE', 0) / volume) * 100) if volume else 0

        # --- Topic breakdown (the primary signal) ---
        topic_lines = []
        for t in topic_matrix[:6]:
            trend_str = t.get('trend', '—')
            topic_lines.append(
                f"  • {t['label']}: {t['reviews_count']} reviews | "
                f"{t['pct_negative']}% negative, {t['pct_positive']}% positive | trend: {trend_str}"
            )

        # --- Worst review excerpts per top 4 topics ---
        excerpt_lines = []
        for t in topic_matrix[:4]:
            tid = t['id']
            reviews = (worst_reviews_by_topic or {}).get(tid, [])
            if reviews:
                excerpt_lines.append(f"  {t['label']}:")
                for r in reviews:
                    stars = '★' * int(r['rating']) + '☆' * (5 - int(r['rating']))
                    excerpt_lines.append(f"    [{stars}] \"{r['text'][:180]}\"")

        # --- Priority issues (from LLM NLP; may be empty for rule-based-only runs) ---
        if top_issues:
            issue_lines = "\n".join(
                f"  • {i.get('issue','unknown')} "
                f"(severity: {i.get('severity','Medium')}, volume: {i.get('volume',0)})"
                for i in top_issues[:5]
            )
        else:
            issue_lines = "  (Not yet available — use topic distribution above to anchor hypotheses)"

        # --- Emerging trends ---
        emerging = [t for t in trends if t.get('trend') == 'emerging'][:3]
        if emerging:
            trend_lines = "\n".join(
                f"  • {t.get('issue','unknown')} "
                f"(+{t.get('growth_rate',0)}% growth, current volume: {t.get('volume_current',0)})"
                for t in emerging
            )
        else:
            trend_lines = "  No emerging trends detected."

        # --- Issue clusters ---
        top_clusters = clusters[:3]
        if top_clusters:
            cluster_lines = "\n".join(
                f"  • Cluster '{c.get('representative_issue','unknown')}' "
                f"(volume: {c.get('volume',0)}, related: {', '.join(c.get('issues',[])[:3])})"
                for c in top_clusters
            )
        else:
            cluster_lines = "  No significant clusters found."

        context = f"""SPOTIFY INDIA — REVIEW INTELLIGENCE REPORT
============================================
Total Reviews Analyzed: {volume}
Overall Sentiment: {neg_pct}% negative · {pos_pct}% positive

TOPIC DISTRIBUTION (sorted by review volume):
{chr(10).join(topic_lines) if topic_lines else "  No topic data."}

WORST USER REVIEWS BY TOPIC (most negative first):
{chr(10).join(excerpt_lines) if excerpt_lines else "  No excerpts available."}

PRIORITY ISSUES (extracted per-review by NLP):
{issue_lines}

EMERGING TRENDS (last 7 days):
{trend_lines}

ISSUE CLUSTERS:
{cluster_lines}"""

        try:
            client = _llm.get_client()

            prompt = f"""You are a senior product analyst for Spotify India.
You have been given the full review intelligence report below. Generate exactly 5 testable product hypotheses.

Rules:
- Each hypothesis must reference a SPECIFIC topic from the Topic Distribution (use exact topic names)
- Each evidence field must cite a SPECIFIC number from the report (e.g. "38 reviews, 76% negative")
- Do not invent data not present in the report
- If priority issues are unavailable, base hypotheses on the topic distribution and review excerpts
- The 5 hypotheses should cover 5 DIFFERENT topics — do not repeat the same topic twice

{context}

Return ONLY a JSON array of exactly 5 objects with these keys:
  hypothesis, evidence, recommended_test, confidence (High/Medium/Low), topic

No markdown, no explanation — only the JSON array."""

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=_llm.model(),
                max_tokens=1800,
                temperature=0.3,
            )

            response_text = chat_completion.choices[0].message.content.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                )

            hypotheses = json.loads(response_text)
            if isinstance(hypotheses, list) and len(hypotheses) > 0:
                for h in hypotheses:
                    h.setdefault('confidence', 'Medium')
                    h.setdefault('topic', 'general')
                    h['_source'] = 'llm'
                return hypotheses

            return [{'_source': 'error', '_error': 'LLM returned an empty or invalid response.'}]

        except Exception as e:
            err = str(e)
            if '429' in err or 'rate_limit' in err.lower() or 'tokens' in err.lower():
                msg = 'LLM daily token limit reached. Hypotheses will generate once the quota resets (usually within 24 hours).'
            elif '401' in err or 'invalid' in err.lower() or 'authentication' in err.lower():
                msg = 'Invalid API key. Update LLM_API_KEY in config/credentials/.env and restart the server.'
            elif 'connect' in err.lower() or 'network' in err.lower() or 'timeout' in err.lower():
                msg = 'LLM provider unreachable. Check your network connection and verify LLM_BASE_URL in .env.'
            else:
                msg = f'LLM unavailable: {err[:120]}'
            return [{'_source': 'error', '_error': msg}]
