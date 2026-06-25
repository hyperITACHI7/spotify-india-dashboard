import json
import time
import yaml
from openai import OpenAI
from core import llm as _llm
from nlp.sentiment.analyzer import SentimentAnalyzer, EnhancedSentimentAnalyzer
from nlp.topics.tagger import TopicTagger, HierarchicalTopicTagger
from nlp.summary.generator import generate_topic_summaries
from core.db import get_connection

# Valid taxonomy topics for LLM extraction (used in prompt)
VALID_TOPICS = [
    "Song Discovery & Recommendations",
    "Subscriptions & Pricing",
    "Playlists & Library",
    "Offline Mode",
    "Podcasts",
    "UI / Layout",
    "Audio Quality",
    "Social & Sharing",
    "Content Availability",
    "Ads Experience",
    "Performance & Crashes",
    "Account & Login",
]


def _get_llm_client() -> OpenAI:
    return _llm.get_client()


def extract_issues_and_topics(review_text: str, client: OpenAI, rating: int | None = None) -> dict:
    """
    Phase 1: LLM-powered extraction of structured issues, sub-topics,
    user intent, severity, and product area from a single review.

    Returns dict with keys:
        issues, sub_topics, user_intent, severity, product_area
    """
    topics_csv = ", ".join(VALID_TOPICS)

    prompt = f"""You are a product analyst for Spotify. Analyze this user review and extract structured intelligence.

Review rating: {rating if rating is not None else "unknown"} out of 5
Review: "{review_text}"

Rules:
1. complaint_issues: Extract 0-5 concrete negative problems (3-7 words each). Be specific (e.g., "excessive ads between songs", not "bad").
2. praise_points: Extract 0-3 clearly positive aspects separately. Do not put praise in complaint_issues.
3. issues: Backward-compatible alias for complaint_issues only.
4. sub_topics: Specific features mentioned (e.g., "Discover Weekly quality", "payment issues", "download reliability").
5. topics: Assign from this fixed list: {topics_csv}
6. user_intent: One of Complaint, Praise, Question, Suggestion. For 1-2 star reviews, default to Complaint unless the text is only a question/suggestion.
7. severity: Low (minor inconvenience) | Medium (degraded experience) | High (major feature broken) | Critical (app unusable, data loss, payment failure)
8. product_area: One of Monetization, Discovery, Playback, UX, Content, Social

Rating guardrail:
- 1-2 star reviews are overall negative complaints even if they contain a small positive clause.
- Do not describe negative phrases as praise.

Return ONLY valid JSON, no markdown, no commentary:
{{"topics": ["..."], "sub_topics": ["..."], "complaint_issues": ["..."], "praise_points": ["..."], "issues": ["..."], "user_intent": "...", "severity": "...", "product_area": "..."}}"""

    try:
        response = client.chat.completions.create(
            model=_llm.model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if the model wraps in ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = json.loads(raw)

        # Validate and sanitize
        complaint_issues = parsed.get("complaint_issues") or parsed.get("issues", [])
        complaint_issues = [str(i).strip() for i in complaint_issues if i][:5]
        praise_points = [str(p).strip() for p in parsed.get("praise_points", []) if p][:3]
        if rating is not None and rating <= 2:
            # Low-star reviews are complaint-first; preserve praise separately
            # but keep the backward-compatible issues field negative only.
            parsed_intent = "Complaint" if parsed.get("user_intent") == "Praise" else parsed.get("user_intent")
        else:
            parsed_intent = parsed.get("user_intent")

        return {
            "issues": complaint_issues,
            "complaint_issues": complaint_issues,
            "praise_points": praise_points,
            "sub_topics": [str(s).strip() for s in parsed.get("sub_topics", []) if s][:5],
            "topics": [t for t in parsed.get("topics", []) if t in VALID_TOPICS],
            "user_intent": parsed_intent if parsed_intent in ("Complaint", "Praise", "Question", "Suggestion") else "Complaint",
            "severity": parsed.get("severity") if parsed.get("severity") in ("Low", "Medium", "High", "Critical") else "Medium",
            "product_area": parsed.get("product_area") if parsed.get("product_area") in ("Monetization", "Discovery", "Playback", "UX", "Content", "Social") else "UX",
        }

    except json.JSONDecodeError as e:
        print(f"  LLM JSON parse error: {e}")
        return _empty_extraction()
    except Exception as e:
        err_msg = str(e)
        # Detect Groq 429 rate limit specifically
        if '429' in err_msg or 'rate_limit' in err_msg.lower():
            # Re-raise so caller can stop making LLM calls
            raise
        print(f"  LLM extraction error: {e}")
        return _empty_extraction()


def _empty_extraction() -> dict:
    """Fallback when LLM extraction fails."""
    return {
        "issues": [],
        "complaint_issues": [],
        "praise_points": [],
        "sub_topics": [],
        "topics": [],
        "user_intent": None,
        "severity": None,
        "product_area": None,
    }


# Rule-based issue extraction — polarity-aware, with negation detection.
# Negative issues: matched when rating is low or negation context present.
# Positive issues: matched when rating is high and no negation.
_NEGATIVE_ISSUE_KEYWORDS = {
    "excessive ads": ["too many ads", "too many ad", "ads are", "ad after", "ad every", "ad between",
                      "forced ads", "forced to watch", "watch ads", "watching ads",
                      "ad break", "ad comes on", "constant ads", "nonstop ads",
                      "ad interrupt", "ads interrupt", "so many ads", "ridiculous ads",
                      "unskippable ad", "can't skip", "cant skip"],
    "premium upsell too aggressive": ["premium popup", "premium pop-up", "upgrade to premium",
                                       "pushing premium", "forcing premium", "forced premium",
                                       "premium ad", "premium not worth", "not worth it",
                                       "overpriced", "price hike", "too expensive"],
    "app crashes": ["crash", "crashes", "crashing", "freeze", "frozen", "force close",
                    "keeps closing", "won't open", "keeps stopping"],
    "slow performance": ["slow", "laggy", "lag", "buffering", "takes forever", "loading forever",
                         "takes too long", "very slow"],
    "login issues": ["can't log in", "cant log in", "login fail", "sign in problem",
                     "can't sign in", "password", "authentication", "locked out"],
    "forced shuffle mode": ["can't play in order", "cant play in order", "forced shuffle",
                            "shuffle only", "won't play album", "can't play album",
                            "play albums in order", "random order"],
    "liked songs restrictions": ["liked songs", "can't play my", "my songs", "songs missing",
                                  "library disappeared", "deleted playlist", "lost my"],
    "offline mode broken": ["offline not working", "downloaded songs", "won't download",
                            "can't download", "offline mode", "no internet",
                            "downloads disappear", "offline broken"],
    "audio quality poor": ["audio quality", "sound quality", "bitrate", "quiet",
                           "volume too low", "audio issue"],
    "UI confusing": ["confusing", "hard to use", "can't find", "cant find",
                     "bad design", "ugly", "cluttered", "too complicated"],
    "content unavailable": ["not available", "unavailable", "region", "removed",
                            "missing songs", "song not found", "can't find song"],
    "podcast problems": ["podcast clutter", "too many podcasts", "podcast episode",
                         "podcast recommendation", "podcast playing"],
    "playlist issues": ["playlist deleted", "playlist missing", "can't edit playlist",
                        "songs disappear from", "playlist won't"],
    "disappointing updates": ["update broke", "new update", "latest update", "used to be",
                              "getting worse", "changed my rating", "downgrading",
                              "used to love", "was great"],
}

_POSITIVE_ISSUE_KEYWORDS = {
    "great music discovery": ["love the recommendation", "discover weekly is great",
                               "amazing playlist", "found new artist", "found some gems",
                               "introduced me to", "love the algorithm", "perfect playlist",
                               "daily mix is", "great suggestions", "love spotify"],
    "smooth playback": ["no issues", "works perfectly", "works great", "flawless",
                        "smooth", "fast", "no lag", "no crash", "runs great"],
    "good value for money": ["worth the money", "worth it", "good deal", "fair price",
                             "love premium", "happy with premium", "great value"],
    "excellent recommendations": ["recommendations are great", "love my discover weekly",
                                   "perfect suggestions", "algorithm knows me",
                                   "exactly what i wanted", "spot on"],
}

# Negation words that flip polarity: "no ads" is NOT "excessive ads"
_NEGATION_WORDS = ["no ", "not ", "isn't ", "isn\u2019t ", "don't ", "doesn't ", "without ", "never ", "zero ", "none "]


def _extract_rule_based_complaints_and_praise(text: str, rating: int = 3) -> dict:
    """
    Extract 2-5 issues from review text using polarity-aware keyword matching
    with negation detection. Fallback when LLM unavailable.
    
    Uses rating to bias towards positive/negative issue categories:
    - 1-2 stars: prefer negative issues
    - 4-5 stars: prefer positive issues
    - 3 stars: mixed
    """
    if not text:
        return []
    lower = text.lower()
    
    neg_issues = []
    pos_issues = []

    direct_negative_patterns = {
        "premium too expensive": ["overpriced", "too expensive", "monthly rates are too high",
                                  "rates are too high", "price is too high", "premium not worth",
                                  "not worth it"],
        "free plan skip restrictions": ["not possible to skip", "can't skip", "cant skip",
                                        "cannot skip", "skip songs", "skip limit"],
        "free plan playback restrictions": ["restrictive music playing", "not subscribed",
                                            "play in order", "can't play in order",
                                            "cant play in order", "forced shuffle"],
        "too many advertisements": ["advertisements are also higher", "advertisements are higher",
                                    "too many advertisements", "too many ads", "higher than usual",
                                    "constant ads", "excessive ads"],
        "regional pricing inconsistency": ["varies by region", "regional price", "region yet expensive"],
    }

    direct_positive_patterns = {
        "better sound quality": ["sound quality is better", "better sound quality", "good sound quality"],
    }

    for issue_label, keywords in direct_negative_patterns.items():
        if any(kw in lower for kw in keywords):
            neg_issues.append(issue_label)

    for praise_label, keywords in direct_positive_patterns.items():
        if any(kw in lower for kw in keywords):
            pos_issues.append(praise_label)
    
    # Match negative issues (with negation check)
    for issue_label, keywords in _NEGATIVE_ISSUE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                # Check if preceded by negation (e.g., "no excessive ads")
                idx = lower.find(kw)
                preceding = lower[max(0, idx - 15):idx]
                is_negated = any(neg_word in preceding for neg_word in _NEGATION_WORDS)
                if not is_negated:
                    neg_issues.append(issue_label)
                    break  # Only count this issue once
    
    # Match positive issues (with negation check)
    for issue_label, keywords in _POSITIVE_ISSUE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                idx = lower.find(kw)
                preceding = lower[max(0, idx - 15):idx]
                is_negated = any(neg_word in preceding for neg_word in _NEGATION_WORDS)
                if not is_negated:
                    pos_issues.append(issue_label)
                    break
    
    # Combine based on rating polarity
    result = []
    if rating <= 2:
        # Low rating: negative issues first, max 1 positive
        result = neg_issues[:4]
        if pos_issues and len(result) < 3:
            result.extend(pos_issues[:1])
    elif rating >= 4:
        # High rating: positive issues first, max 1 negative
        result = pos_issues[:4]
        if neg_issues and len(result) < 3:
            result.extend(neg_issues[:1])
    else:
        # 3 stars: mix both
        result = neg_issues[:2] + pos_issues[:2]
    
    # Remove duplicates
    seen = set()
    unique = []
    for issue in result:
        if issue not in seen:
            seen.add(issue)
            unique.append(issue)
    result = unique[:5]
    
    # If nothing matched, generate generic issues from rating
    if not result:
        if rating <= 2:
            result = ["poor experience", "needs improvement"]
        elif rating >= 4:
            result = ["good experience", "works well"]
        else:
            result = ["average experience"]
    
    praise_points = []
    for issue in pos_issues:
        if issue not in praise_points:
            praise_points.append(issue)

    return {
        "complaint_issues": result,
        "praise_points": praise_points[:3],
        "issues": result,
    }


def _extract_rule_based_issues(text: str, rating: int = 3) -> list:
    """Backward-compatible wrapper returning complaint issues only."""
    return _extract_rule_based_complaints_and_praise(text, rating).get("complaint_issues", [])

def seed_topics_from_taxonomy():
    """Auto-seeds the topics table from taxonomy.yaml so topic foreign keys always exist."""
    try:
        with open('config/taxonomy.yaml', 'r') as f:
            taxonomy = yaml.safe_load(f)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        for category in taxonomy.get('categories', []):
            topic_id = category['id']
            label = category['label']
            keywords = category.get('keywords', [])
            
            cursor.execute(
                """
                INSERT INTO topics (id, label, keywords)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    label = EXCLUDED.label,
                    keywords = EXCLUDED.keywords
                """,
                (topic_id, label, keywords)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Topics table seeded from taxonomy.yaml.")
    except Exception as e:
        print(f"Warning: Could not seed topics table: {e}")

def run_nlp_pipeline(dry_run: bool = False, limit: int = 500, skip_llm: bool = False, progress_callback=None):
    print("Initializing NLP Pipeline...")
    sentiment_engine = SentimentAnalyzer()
    enhanced_engine = EnhancedSentimentAnalyzer()  # Phase 4
    topic_engine = TopicTagger()
    hierarchical_tagger = HierarchicalTopicTagger()  # Phase 2
    llm_client = None
    
    if skip_llm:
        print("LLM extraction skipped (--no-llm mode). Using VADER + rule-based enrichment only.")
    
    if not dry_run:
        if not skip_llm:
            try:
                llm_client = _get_llm_client()
            except Exception as e:
                print(f"Warning: Could not initialize Groq client: {e}")
                print("LLM extraction will be skipped; only VADER sentiment + rule-based topics will run.")
        seed_topics_from_taxonomy()
    
    if dry_run:
        print("--- DRY RUN ENABLED: Skipping database operations ---")
        llm_client = _get_llm_client()  # Still init for dry-run testing
        dummy_reviews = [
            "I absolutely love the new discover weekly algorithm, it found some gems!",
            "The app keeps crashing when I open my library.",
            "Why am I getting the same songs over and over again? The recommendations are boring.",
            "Nice UI but too many ads interrupting my music every two songs.",
            "Premium price hike is ridiculous, family plan is no longer worth it."
        ]
        
        for idx, text in enumerate(dummy_reviews):
            sentiment = sentiment_engine.analyze(text)
            topics = topic_engine.extract_topics(text)
            llm_result = extract_issues_and_topics(text, llm_client) if llm_client else _empty_extraction()
            
            # Phase 2: Validate LLM output through hierarchical tagger
            validated = hierarchical_tagger.map_llm_extraction(llm_result) if llm_result['topics'] else llm_result
            
            print(f"\n--- Review {idx+1} ---")
            print(f"Text: {text}")
            print(f"VADER Sentiment: {sentiment['label']} (score: {sentiment['score']})")
            print(f"Rule Topics: {[t['topic_id'] for t in topics]}")
            print(f"LLM Issues: {llm_result['issues']}")
            print(f"LLM Raw Sub-topics: {llm_result['sub_topics']}")
            print(f"LLM Intent: {llm_result['user_intent']} | Severity: {llm_result['severity']} | Area: {llm_result['product_area']}")
            # Phase 4: Enhanced analysis (rule-based fallback + emotional tone)
            enhanced = enhanced_engine.full_analysis(text)
            print(f"[Phase 4] Intent: {enhanced['user_intent']} | Severity: {enhanced['severity']} | Tone: {enhanced['emotional_tone']}")
            if 'topic_ids' in validated:
                print(f"[Phase 2] Resolved topic_ids: {validated['topic_ids']}")
                print(f"[Phase 2] Validated sub-topics: {validated['sub_topics']}")
            
            if llm_client:
                time.sleep(1)  # Rate limit buffer
        
        # Phase 3: Generate topic summaries from mock data (dry-run)
        print("\n--- Phase 3: Topic Summary Generation (dry-run) ---")
        summary_results = generate_topic_summaries(conn=None, llm_client=llm_client, dry_run=True)
        print(f"\nPhase 3 dry-run: Generated {len(summary_results)} summaries.")
        
        print("\nDry run complete.")
        return

    # Real DB Execution
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch unprocessed reviews (includes VADER-only rows that need LLM upgrade)
    cursor.execute("""
        SELECT r.id, r.text_original, r.rating
        FROM reviews_raw r
        LEFT JOIN reviews_enriched e ON r.id = e.review_id
        WHERE e.review_id IS NULL
           OR e.nlp_processed = FALSE
        LIMIT %s
    """, (limit,))
    
    unprocessed = cursor.fetchall()
    print(f"Found {len(unprocessed)} unprocessed reviews in the database.")
    
    if not unprocessed:
        return

    # 2. Process and insert
    success_count = 0
    total_unprocessed = len(unprocessed)
    llm_rate_limited = False  # Flag: stop calling LLM after 429
    LLM_CALL_CAP = 500        # Max LLM calls per pipeline run to stay within free-tier budget
    llm_calls_made = 0
    for i, row in enumerate(unprocessed):
        if progress_callback and i % 10 == 0:
            progress_callback(i, total_unprocessed)
        review_id = row['id']
        text = row['text_original']
        rating_for_review = int(row.get('rating') or 3)
        
        # VADER sentiment with rating override (fast, always runs)
        sentiment = sentiment_engine.analyze(text, rating=rating_for_review)
        # Rule-based topic tagging (fast, always runs)
        topics = topic_engine.extract_topics(text)
        
        # LLM-powered issue extraction (Phase 1)
        llm_result = _empty_extraction()
        validated = llm_result  # default: no validation
        if llm_client and not llm_rate_limited and not skip_llm and llm_calls_made < LLM_CALL_CAP:
            try:
                llm_result = extract_issues_and_topics(text, llm_client, rating=rating_for_review)
                llm_calls_made += 1
                # Phase 2: Validate through hierarchical tagger
                if llm_result['topics']:
                    validated = hierarchical_tagger.map_llm_extraction(llm_result)
                # 2.1s delay keeps throughput just under Groq's 30 RPM free-tier limit
                time.sleep(2.1)
                if llm_calls_made >= LLM_CALL_CAP:
                    print(f"  LLM call cap ({LLM_CALL_CAP}) reached at review {i+1}. "
                          f"Switching to rule-based for remaining reviews.")
            except Exception as rate_err:
                err_str = str(rate_err)
                if '429' in err_str or 'rate_limit' in err_str.lower():
                    llm_rate_limited = True
                    print(f"  Groq rate limit hit at review {i+1}/{len(unprocessed)}. "
                          f"Switching to rule-based for remaining reviews.")
                    llm_result = _empty_extraction()
                    validated = llm_result
                elif '403' in err_str or 'permission' in err_str.lower() or 'blocked' in err_str.lower():
                    llm_rate_limited = True  # reuse flag to stop further LLM calls
                    print(f"  LLM model blocked/forbidden at review {i+1}. "
                          f"Check model permissions with your LLM provider. "
                          f"Switching to rule-based for remaining reviews.")
                    llm_result = _empty_extraction()
                    validated = llm_result
                else:
                    llm_result = _empty_extraction()
                    validated = llm_result
        
        # Phase 4: Use EnhancedSentimentAnalyzer as fallback for intent/severity
        if not llm_result.get('user_intent') or not llm_result.get('severity'):
            enhanced = enhanced_engine.full_analysis(text, rating=rating_for_review)
            if not llm_result.get('user_intent'):
                llm_result['user_intent'] = enhanced['user_intent']
            if not llm_result.get('severity'):
                llm_result['severity'] = enhanced['severity']
        
        # Fallback issue extraction when LLM fails or is rate-limited
        if not llm_result.get('issues'):
            fallback_extraction = _extract_rule_based_complaints_and_praise(text, rating_for_review)
            llm_result['issues'] = fallback_extraction['complaint_issues']
            llm_result['complaint_issues'] = fallback_extraction['complaint_issues']
            llm_result['praise_points'] = fallback_extraction['praise_points']
        
        # Use validated sub_topics from Phase 2 if available
        final_sub_topics = validated.get('sub_topics', llm_result.get('sub_topics', [])) or None
        
        try:
            # Insert or upgrade enriched review with Phase 1 + Phase 2 fields.
            # ON CONFLICT also updates sentiment columns so that any mis-labelled
            # rows from VADER-only ingestion (which lacked the rating signal) are
            # corrected with the rating-aware blended score computed above.
            cursor.execute("""
                INSERT INTO reviews_enriched
                (review_id, sentiment_score, sentiment_label, sentiment_confidence, sentiment_model_version,
                 issues, sub_topics, user_intent, severity, product_area, llm_model_version, nlp_processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (review_id) DO UPDATE SET
                    sentiment_score = EXCLUDED.sentiment_score,
                    sentiment_label = EXCLUDED.sentiment_label,
                    sentiment_confidence = EXCLUDED.sentiment_confidence,
                    sentiment_model_version = EXCLUDED.sentiment_model_version,
                    issues = EXCLUDED.issues,
                    sub_topics = EXCLUDED.sub_topics,
                    user_intent = EXCLUDED.user_intent,
                    severity = EXCLUDED.severity,
                    product_area = EXCLUDED.product_area,
                    llm_model_version = EXCLUDED.llm_model_version,
                    nlp_processed = TRUE
            """, (
                review_id,
                sentiment['score'],
                sentiment['label'],
                sentiment['confidence'],
                sentiment['version'],
                llm_result['issues'] or None,
                final_sub_topics,
                llm_result['user_intent'],
                llm_result['severity'],
                llm_result['product_area'],
                _llm.model() if llm_client else None,
            ))
            
            # Insert rule-based topic mappings
            for t in topics:
                cursor.execute("""
                    INSERT INTO review_topics (review_id, topic_id, confidence, method)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (review_id, topic_id) DO NOTHING
                """, (review_id, t['topic_id'], t['confidence'], t['method']))
            
            # Phase 2: Insert LLM-resolved topic mappings with sub_topic
            if 'topic_ids' in validated:
                for tid in validated['topic_ids']:
                    # Find matching sub_topic for this topic_id (if any)
                    matched_sub = None
                    for sub in (validated.get('sub_topics') or []):
                        if hierarchical_tagger.validate_subtopic(sub, tid):
                            matched_sub = sub
                            break
                    cursor.execute("""
                        INSERT INTO review_topics (review_id, topic_id, confidence, method, sub_topic)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (review_id, topic_id) DO UPDATE 
                            SET method = 'hybrid', sub_topic = EXCLUDED.sub_topic
                    """, (review_id, tid, 0.9, 'llm', matched_sub))
                
            success_count += 1
            
            if (i + 1) % 5 == 0:
                subs = llm_result.get('sub_topics') or []
                print(f"  [{i+1}/{total_unprocessed}] LLM sub_topics: {subs or 'none'}")

        except Exception as e:
            print(f"Failed to process review {review_id}: {e}")
            conn.rollback()
            continue

    conn.commit()
    
    # Phase 3: Generate topic summaries (works without LLM via rule-based fallback)
    print("\n--- Phase 3: Generating topic summaries ---")
    if llm_client and not llm_rate_limited:
        try:
            generate_topic_summaries(conn, llm_client=llm_client, dry_run=False)
        except Exception as e:
            print(f"Phase 3 summary generation failed (non-fatal): {e}")
    else:
        # Generate summaries without LLM using rule-based aggregation
        _generate_rule_based_summaries(conn)
    
    print(f"NLP Pipeline complete. Successfully processed and enriched {success_count} reviews.")
    if llm_client and not llm_rate_limited:
        print(f"  LLM model used: {_llm.model()}")
        print(f"  Fields extracted: issues, sub_topics, user_intent, severity, product_area")
        print(f"  Phase 2: Hierarchical topic validation active")
    else:
        print(f"  LLM skipped — rule-based enrichment used (issues, topics, intent, severity)")
    
    cursor.close()
    conn.close()


def _generate_rule_based_summaries(conn):
    """Generate topic summaries without LLM — aggregate dominant issues per topic."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id as topic_id, t.label,
                   COUNT(DISTINCT rt.review_id) as review_count
            FROM topics t
            JOIN review_topics rt ON t.id = rt.topic_id
            GROUP BY t.id, t.label
            HAVING COUNT(DISTINCT rt.review_id) >= 3
        """)
        topic_rows = cursor.fetchall()
        
        for trow in topic_rows:
            topic_id = trow['topic_id']
            label = trow['label']
            review_count = trow['review_count']
            
            # Get dominant issues for this topic
            cursor.execute("""
                SELECT unnest(e.issues) as issue, COUNT(*) as cnt
                FROM review_topics rt
                JOIN reviews_enriched e ON rt.review_id = e.review_id
                WHERE rt.topic_id = %s AND e.issues IS NOT NULL
                GROUP BY issue
                ORDER BY cnt DESC
                LIMIT 5
            """, (topic_id,))
            issue_rows = cursor.fetchall()
            dominant_issues = [r['issue'] for r in issue_rows]
            
            # Get sentiment distribution
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN e.sentiment_label = 'POSITIVE' THEN 1 ELSE 0 END) as pos,
                    SUM(CASE WHEN e.sentiment_label = 'NEGATIVE' THEN 1 ELSE 0 END) as neg
                FROM review_topics rt
                JOIN reviews_enriched e ON rt.review_id = e.review_id
                WHERE rt.topic_id = %s
            """, (topic_id,))
            sd = cursor.fetchone()
            total = sd['total'] or 1
            pos_pct = round((sd['pos'] or 0) / total, 2)
            neg_pct = round((sd['neg'] or 0) / total, 2)
            neu_pct = round(1.0 - pos_pct - neg_pct, 2)
            
            # Generate summary text from dominant issues — varied templates, not one-size-fits-all
            issue_a = dominant_issues[0].capitalize() if dominant_issues else None
            issue_b = dominant_issues[1] if len(dominant_issues) > 1 else None
            issue_c = dominant_issues[2] if len(dominant_issues) > 2 else None

            if issue_a:
                if neg_pct > 0.65:
                    if issue_b and issue_c:
                        summary = f"Strong complaint pattern: {issue_a}, {issue_b}, and {issue_c}."
                    elif issue_b:
                        summary = f"{issue_a} and {issue_b} dominate complaints ({round(neg_pct * 100)}% negative)."
                    else:
                        summary = f"{issue_a} is the dominant complaint ({round(neg_pct * 100)}% negative feedback)."
                elif neg_pct > 0.4:
                    if issue_b:
                        summary = f"{issue_a} and {issue_b} are the leading concerns ({round(neg_pct * 100)}% dissatisfied)."
                    else:
                        summary = f"{issue_a} is the primary concern with {round(neg_pct * 100)}% negative feedback."
                elif pos_pct > 0.6:
                    summary = f"Largely positive; minor complaints include {issue_a}."
                else:
                    if issue_b:
                        summary = f"Mixed reception; recurring issues include {issue_a} and {issue_b}."
                    else:
                        summary = f"Mixed reception; primary concern is {issue_a}."
            else:
                if pos_pct > 0.6:
                    summary = f"Predominantly positive feedback across {review_count} reviews."
                elif neg_pct > 0.4:
                    summary = f"{round(neg_pct * 100)}% negative sentiment with no single dominant issue."
                else:
                    summary = f"Mixed feedback across {review_count} reviews without a dominant pattern."
            
            cursor.execute("""
                INSERT INTO topic_summaries (topic_id, sub_topic, summary_text, review_count, 
                    sentiment_distribution, dominant_issues)
                VALUES (%s, NULL, %s, %s, %s, %s)
                ON CONFLICT (topic_id, COALESCE(sub_topic, '__parent__')) DO UPDATE SET
                    summary_text = EXCLUDED.summary_text,
                    review_count = EXCLUDED.review_count,
                    sentiment_distribution = EXCLUDED.sentiment_distribution,
                    dominant_issues = EXCLUDED.dominant_issues,
                    generated_at = NOW()
            """, (topic_id, summary, review_count,
                  json.dumps({"positive": pos_pct, "negative": neg_pct, "neutral": neu_pct}),
                  dominant_issues or None))
        
        conn.commit()
        print(f"Generated rule-based summaries for {len(topic_rows)} topics.")
    except Exception as e:
        print(f"Rule-based summary generation failed (non-fatal): {e}")
        conn.rollback()


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    skip_llm = "--no-llm" in sys.argv
    run_nlp_pipeline(dry_run=dry_run, skip_llm=skip_llm)
