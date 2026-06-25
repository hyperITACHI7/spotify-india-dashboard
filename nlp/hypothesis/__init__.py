"""
nlp/hypothesis/__init__.py

Phase 7: Hypothesis Generation.
Uses Groq LLM to generate analyst-quality, testable product hypotheses from
real review intelligence. Returns an error dict on failure — no fake fallback.
"""

import json
from typing import List, Dict, Any
from core import llm as _llm


class HypothesisGenerator:

    def generate(
        self,
        topic_stats: Dict[str, Any],
        top_issues: List[Dict],
        trends: List[Dict],
        clusters: List[Dict],
        cache_key: tuple = (),
    ) -> List[Dict[str, str]]:
        """
        Generate 5 product hypotheses via LLM.
        Returns a list with a single error-flagged dict on failure.
        """
        volume = topic_stats.get('total_reviews', 0)
        sent_dist = topic_stats.get('sentiment_distribution', {})
        top_5_issues = top_issues[:5]
        emerging = [t for t in trends if t.get('trend') == 'emerging'][:3]
        top_clusters = clusters[:3]

        context = f"""Review Intelligence Summary:
- Total Reviews Analyzed: {volume}
- Sentiment Distribution: {sent_dist}

Top Priority Issues:
{chr(10).join(f"  - {i.get('issue','unknown')} (severity: {i.get('severity','Medium')}, volume: {i.get('volume',0)})" for i in top_5_issues)}

Emerging Trends:
{chr(10).join(f"  - {t.get('issue','unknown')} (growth: {t.get('growth_rate',0)}%, current volume: {t.get('volume_current',0)})" for t in emerging) if emerging else "  No emerging trends detected."}

Issue Clusters:
{chr(10).join(f"  - Cluster '{c.get('representative_issue','unknown')}' (volume: {c.get('volume',0)}, issues: {', '.join(c.get('issues',[])[:3])})" for c in top_clusters) if top_clusters else "  No significant clusters found."}
"""

        try:
            client = _llm.get_client()

            prompt = f"""You are a senior product analyst for Spotify India. Based on this review intelligence, generate exactly 5 testable product hypotheses — one per priority issue listed above.

{context}

Generate hypotheses in this exact JSON format (return a JSON array of exactly 5 items):
[
  {{
    "hypothesis": "Clear statement linking cause to effect",
    "evidence": "Specific data points from the intelligence above",
    "recommended_test": "Concrete A/B test or research method",
    "confidence": "High/Medium/Low",
    "topic": "Most relevant topic area"
  }}
]

Return ONLY valid JSON, no markdown or explanation."""

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=_llm.model(),
                max_tokens=1500,
                temperature=0.4,
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
