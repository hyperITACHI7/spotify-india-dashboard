import yaml
import hashlib
import threading
from datetime import datetime, timezone
import pandas as pd
from typing import List, Optional, Callable

from ingestion.collectors import playstore_collector, appstore_collector
from ingestion.collectors.base import Review
from core.db import get_connection


def _launch_nlp_background() -> None:
    """Run rule-based NLP topic assignment in a background thread after scraping."""
    def _job():
        try:
            from nlp.pipeline import run_nlp_pipeline
            from aggregation.discovery_stats import set_nlp_progress

            def _cb(processed: int, total: int):
                set_nlp_progress(processed, total, "running")

            set_nlp_progress(0, 0, "running")
            run_nlp_pipeline(skip_llm=False, limit=500, progress_callback=_cb)
            set_nlp_progress(0, 0, "done")
        except Exception as e:
            print(f"Background NLP job failed: {e}")
            try:
                from aggregation.discovery_stats import set_nlp_progress
                set_nlp_progress(0, 0, "idle")
            except Exception:
                pass

    threading.Thread(target=_job, daemon=True).start()

def load_settings():
    with open('config/settings.yaml', 'r') as f:
        return yaml.safe_load(f)

def compute_relevance_score(review: Review, strategy: str) -> float:
    """
    Computes a relevance score to help trim down to the top N reviews.
    """
    # Simple strategy: recency
    # We return a timestamp as a float. Higher is more recent.
    # If strategy was "recency_x_rating", we would weight it here.
    return review.created_at.timestamp()

def ingest_run(limit_override: int = None, region_override: str = None, dry_run: bool = False,
                progress_callback: Optional[Callable[[int, int, str], None]] = None):
    settings = load_settings()
    
    def _progress(current, total, msg):
        if progress_callback:
            progress_callback(current, total, msg)
    
    # Step 0: Configure run parameters
    region = region_override or settings['ingestion']['region_filter'].get('country_code', 'IN')
    limit = limit_override or settings['ingestion']['review_limit'].get('max_reviews_per_run', 1000)
    strategy = settings['ingestion']['review_limit'].get('relevance_strategy', 'recency')
    
    print(f"Starting ingestion run: N={limit}, Region={region}, Strategy={strategy}, DryRun={dry_run}")
    
    # Step 0b: Compute per-platform quota (50/50 preferred, but total is the priority).
    # Apple's SSR page caps at ~30 reviews. Play Store absorbs whatever App Store
    # can't fill via the overflow logic below.
    half = limit // 2
    # Apple's see-all page has ~10 unique reviews (same reviews repeated across 3 shelf
    # sections). After deduplication the collector returns at most 10 unique items.
    _appstore_cap = 10
    # Ask Play Store for enough to cover the full limit if App Store falls short.
    fetch_buffer = max(limit - _appstore_cap, half)
    
    # Step 1: Fetch candidates from each platform independently
    playstore_candidates: List[Review] = []
    appstore_candidates: List[Review] = []
    
    _progress(0, limit, "Fetching Play Store reviews...")
    try:
        playstore_candidates = playstore_collector.fetch_reviews(limit=fetch_buffer, country=region)
        _progress(int(limit * 0.3), limit, f"Got {len(playstore_candidates)} Play Store reviews. Fetching App Store...")
    except Exception as e:
        print(f"Error fetching Play Store reviews: {e}")
        _progress(int(limit * 0.3), limit, "Play Store fetch failed. Trying App Store...")
        
    try:
        appstore_candidates = appstore_collector.fetch_reviews(limit=fetch_buffer, country=region)
        _progress(int(limit * 0.5), limit, f"Got {len(appstore_candidates)} App Store reviews. Storing in database...")
    except Exception as e:
        print(f"Error fetching App Store reviews: {e}")
        _progress(int(limit * 0.5), limit, "App Store fetch done. Storing reviews...")
        
    # Ensure tz awareness
    for r in playstore_candidates + appstore_candidates:
        if r.created_at.tzinfo is None:
            r.created_at = r.created_at.replace(tzinfo=timezone.utc)

    # Sort each platform by relevance independently
    playstore_candidates.sort(key=lambda r: compute_relevance_score(r, strategy), reverse=True)
    appstore_candidates.sort(key=lambda r: compute_relevance_score(r, strategy), reverse=True)

    # Step 2: Allocate 50/50 with overflow
    # Take half from each; if one side is short, give its leftover quota to the other
    play_count = min(half, len(playstore_candidates))
    app_count = min(half, len(appstore_candidates))

    # Overflow: if one platform couldn't fill its half, let the other absorb the rest
    if play_count < half:
        app_count = min(limit - play_count, len(appstore_candidates))
    elif app_count < half:
        play_count = min(limit - app_count, len(playstore_candidates))

    top_n = playstore_candidates[:play_count] + appstore_candidates[:app_count]

    print(f"Total candidates fetched: {len(playstore_candidates) + len(appstore_candidates)}")
    if not top_n:
        print("No candidates found. Aborting run.")
        return

    print(f"Selected {play_count} Play Store + {app_count} App Store = {len(top_n)} reviews (50/50 split).")
    
    if dry_run:
        print("--- DRY RUN ENABLED: Skipping database insertion ---")
        # Show samples from each platform
        for label, pool in [("Play Store", playstore_candidates[:play_count]),
                            ("App Store", appstore_candidates[:app_count])]:
            print(f"\n  -- {label} samples ({len(pool)} selected) --")
            for idx, r in enumerate(pool[:3]):
                safe_review = r.text_original[:200].encode('ascii', 'ignore').decode('ascii')
                print(f"  [{idx+1}] Rating: {r.rating}/5 | Date: {r.created_at}")
                print(f"      {safe_review}...")
        print("\nDry run complete. Scrapers are working perfectly.")
        return

    # Step 3: Insert / Deduplicate via DB
    conn = get_connection()
    cursor = conn.cursor()

    # Create the run record FIRST — old data is only deleted after the new scrape
    # commits successfully, so a failed scrape never leaves you with no data.
    cursor.execute(
        """
        INSERT INTO ingestion_runs (region_filter, review_limit_n, relevance_strategy, reviews_fetched, status, is_snapshot)
        VALUES (%s, %s, %s, %s, 'running', FALSE)
        RETURNING id
        """,
        (region, limit, strategy, len(top_n))
    )
    run_id = cursor.fetchone()['id']
    
    inserted_count = 0
    for r in top_n:
        # Include run_id in hash so the same review can exist in both snapshot and
        # live runs without conflict. Deduplication is scoped to one run only.
        review_hash_input = f"{run_id}_{r.source}_{r.platform_review_id}"
        review_hash = hashlib.sha256(review_hash_input.encode('utf-8')).hexdigest()
        
        try:
            cursor.execute("SAVEPOINT sp_review")
            cursor.execute(
                """
                INSERT INTO reviews_raw
                (platform_review_id, source, platform, rating, text_original, created_at, country_code, app_version_id, review_hash, ingestion_run_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)
                ON CONFLICT (review_hash) DO NOTHING
                """,
                (r.platform_review_id, r.source, r.platform, r.rating, r.text_original, r.created_at, r.country_code, review_hash, run_id)
            )
            if cursor.rowcount == 1:
                inserted_count += 1
            cursor.execute("RELEASE SAVEPOINT sp_review")
        except Exception as e:
            print(f"Failed to insert review {r.platform_review_id}: {e}")
            cursor.execute("ROLLBACK TO SAVEPOINT sp_review")
            continue
            
    # Mark run complete
    cursor.execute(
        """
        UPDATE ingestion_runs 
        SET reviews_stored = %s, status = 'done'
        WHERE id = %s
        """,
        (inserted_count, run_id)
    )
    
    conn.commit()

    # Now that new data is safely committed, delete previous live scrape runs.
    # Snapshot data (is_snapshot = TRUE) is never touched.
    try:
        old_run_ids = """
            SELECT id FROM ingestion_runs WHERE (is_snapshot = FALSE OR is_snapshot IS NULL) AND id != %s
        """
        cursor.execute(f"DELETE FROM review_topics WHERE review_id IN (SELECT id FROM reviews_raw WHERE ingestion_run_id IN ({old_run_ids}))", (run_id,))
        cursor.execute(f"DELETE FROM reviews_enriched WHERE review_id IN (SELECT id FROM reviews_raw WHERE ingestion_run_id IN ({old_run_ids}))", (run_id,))
        cursor.execute(f"DELETE FROM reviews_raw WHERE ingestion_run_id IN ({old_run_ids})", (run_id,))
        cursor.execute("DELETE FROM ingestion_runs WHERE (is_snapshot = FALSE OR is_snapshot IS NULL) AND id != %s", (run_id,))
        conn.commit()
        print("Cleared previous live scrape data. New data preserved.")
    except Exception as e:
        print(f"Failed to clear old live data (non-fatal): {e}")
        conn.rollback()

    # Step 4: VADER-only enrichment — guarantees reviews_enriched rows immediately
    # so the dashboard can show real scraped data even if LLM NLP pipeline fails later.
    if inserted_count > 0:
        vader_start = int(limit * 0.5)
        vader_end = int(limit * 0.8)
        _progress(vader_start, limit, "Running sentiment analysis on scraped reviews...")
        try:
            from nlp.sentiment.analyzer import SentimentAnalyzer, EnhancedSentimentAnalyzer
            vader = SentimentAnalyzer()
            enhanced = EnhancedSentimentAnalyzer()
            
            cursor.execute("""
                SELECT r.id, r.text_original, r.rating
                FROM reviews_raw r
                LEFT JOIN reviews_enriched e ON r.id = e.review_id
                WHERE e.review_id IS NULL
                  AND r.ingestion_run_id = %s
            """, (run_id,))
            raw_reviews = cursor.fetchall()
            total_to_enrich = len(raw_reviews)
            print(f"VADER enrichment: {total_to_enrich} reviews to process...")

            enriched_count = 0
            for row in raw_reviews:
                text = row['text_original']
                rating = int(row['rating']) if row.get('rating') is not None else None
                sentiment = vader.analyze(text, rating=rating)
                intent_info = enhanced.full_analysis(text, rating=rating)
                
                try:
                    cursor.execute("SAVEPOINT sp_enrich")
                    cursor.execute("""
                        INSERT INTO reviews_enriched
                        (review_id, sentiment_score, sentiment_label, sentiment_confidence,
                         sentiment_model_version, user_intent, severity, product_area, nlp_processed)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                        ON CONFLICT (review_id) DO NOTHING
                    """, (
                        row['id'],
                        sentiment['score'],
                        sentiment['label'],
                        sentiment['confidence'],
                        sentiment['version'],
                        intent_info.get('user_intent', 'Complaint'),
                        intent_info.get('severity', 'Medium'),
                        intent_info.get('product_area', 'UX'),
                    ))
                    enriched_count += 1
                    cursor.execute("RELEASE SAVEPOINT sp_enrich")
                except Exception as e:
                    print(f"  VADER enrichment failed for review {row['id']}: {e}")
                    cursor.execute("ROLLBACK TO SAVEPOINT sp_enrich")
                    continue
                
                # Report progress every 10 reviews (more granular for UI)
                if enriched_count % 10 == 0 and total_to_enrich > 0:
                    fraction = enriched_count / total_to_enrich
                    progress_val = vader_start + int((vader_end - vader_start) * fraction)
                    _progress(progress_val, limit, f"Analyzing reviews: {enriched_count}/{total_to_enrich}...")
            
            conn.commit()
            _progress(vader_end, limit, f"Analysis complete: {enriched_count} reviews enriched.")
            print(f"VADER enrichment complete: {enriched_count}/{inserted_count} reviews enriched.")
        except Exception as e:
            print(f"VADER enrichment step failed (non-fatal): {e}")
            conn.rollback()
    
    cursor.close()
    conn.close()
    
    _progress(int(limit * 0.8), limit, f"Ingestion done: {inserted_count} reviews stored and analyzed.")
    print(f"Ingestion run complete! Inserted {inserted_count} new reviews.")

    if inserted_count > 0 and not dry_run:
        _launch_nlp_background()

if __name__ == "__main__":
    # Test script run
    import sys
    dry_run = "--dry-run" in sys.argv
    ingest_run(limit_override=10, dry_run=dry_run)
