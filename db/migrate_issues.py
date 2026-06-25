"""
db/migrate_issues.py

Phase 1 Migration Script: Backfills existing reviews_enriched rows
with LLM-extracted issues, sub_topics, user_intent, severity, and product_area.

Steps:
  1. ALTER TABLE to add new Phase 1 columns (idempotent)
  2. Find reviews_enriched rows WHERE issues IS NULL
  3. For each, fetch text_original from reviews_raw
  4. Call LLM extraction via nlp.pipeline.extract_issues_and_topics()
  5. UPDATE the enriched row with extracted data
  6. Rate-limit aware: pauses every 25 reviews

Usage:
    python -m db.migrate_issues                     # backfill all, batch 100
    python -m db.migrate_issues --limit 10          # backfill 10 reviews
    python -m db.migrate_issues --dry-run           # preview without writing
"""

import sys
import time

from core.db import get_connection
from nlp.pipeline import extract_issues_and_topics, _get_groq_client, LLM_MODEL

BATCH_SIZE = 100
PAUSE_EVERY = 25  # Pause after every N reviews for rate limiting
PAUSE_SECONDS = 5


def alter_table_if_needed(conn):
    """Idempotent: add Phase 1 columns if they don't already exist."""
    cursor = conn.cursor()
    columns_to_add = [
        ("issues", "TEXT[]"),
        ("sub_topics", "TEXT[]"),
        ("user_intent", "VARCHAR(50)"),
        ("severity", "VARCHAR(20)"),
        ("product_area", "VARCHAR(50)"),
        ("llm_model_version", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE reviews_enriched ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
        except Exception as e:
            print(f"  Column '{col_name}': {e}")
            conn.rollback()

    conn.commit()
    print("Schema check complete (Phase 1 columns verified).")


def migrate_phase2_schema(conn):
    """Idempotent: add Phase 2 sub_topic column to review_topics + GIN index on sub_topics."""
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE review_topics ADD COLUMN IF NOT EXISTS sub_topic TEXT")
        print("  Phase 2: review_topics.sub_topic column verified.")
    except Exception as e:
        print(f"  Phase 2 sub_topic column: {e}")
        conn.rollback()

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_topics_sub_topic ON review_topics(sub_topic)")
        print("  Phase 2: idx_review_topics_sub_topic index verified.")
    except Exception as e:
        print(f"  Phase 2 sub_topic index: {e}")
        conn.rollback()

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_enriched_sub_topics ON reviews_enriched USING GIN(sub_topics)")
        print("  Phase 2: idx_enriched_sub_topics GIN index verified.")
    except Exception as e:
        print(f"  Phase 2 sub_topics GIN index: {e}")
        conn.rollback()

    conn.commit()
    print("Phase 2 schema migration complete.")


def migrate_phase3_schema(conn):
    """Idempotent: create topic_summaries table + indexes for Phase 3."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_summaries (
                id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                topic_id                 TEXT NOT NULL,
                sub_topic                TEXT,
                summary_text             TEXT NOT NULL,
                review_count             INTEGER,
                sentiment_distribution   JSONB,
                dominant_issues          TEXT[],
                generated_at             TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (topic_id, COALESCE(sub_topic, '__parent__'))
            )
        """)
        print("  Phase 3: topic_summaries table verified.")
    except Exception as e:
        print(f"  Phase 3 topic_summaries table: {e}")
        conn.rollback()

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_topic_summaries_topic_id ON topic_summaries(topic_id)",
        "CREATE INDEX IF NOT EXISTS idx_topic_summaries_sub_topic ON topic_summaries(sub_topic)",
    ]:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            print(f"  Phase 3 index: {e}")
            conn.rollback()

    conn.commit()
    print("Phase 3 schema migration complete.")


def run_migration(limit: int = None, dry_run: bool = False):
    print("=" * 60)
    print("Phase 1+2+3 Migration: Backfill LLM-Extracted Issues, Hierarchical Topics & Summaries")
    print("=" * 60)

    conn = get_connection()

    # Step 1: Ensure schema is up to date (Phase 1 + Phase 2 + Phase 3)
    alter_table_if_needed(conn)
    migrate_phase2_schema(conn)
    migrate_phase3_schema(conn)

    if dry_run:
        print("\n--- DRY RUN: Testing LLM extraction on 3 sample reviews ---")
        client = _get_groq_client()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT re.review_id, rr.text_original
            FROM reviews_enriched re
            JOIN reviews_raw rr ON re.review_id = rr.id
            WHERE re.issues IS NULL
            LIMIT 3
        """)
        samples = cursor.fetchall()
        cursor.close()
        conn.close()

        if not samples:
            print("No unprocessed reviews found. Migration already complete!")
            return

        for row in samples:
            text = row['text_original']
            result = extract_issues_and_topics(text, client)
            safe_text = text[:80].encode('ascii', 'ignore').decode('ascii')
            print(f"\n  Review: {safe_text}...")
            print(f"  Issues: {result['issues']}")
            print(f"  Sub-topics: {result['sub_topics']}")
            print(f"  Intent: {result['user_intent']} | Severity: {result['severity']} | Area: {result['product_area']}")
            time.sleep(1)

        print("\nDry run complete. No data was modified.")
        return

    # Step 2: Initialize LLM client
    try:
        client = _get_groq_client()
    except Exception as e:
        print(f"FATAL: Cannot initialize Groq client: {e}")
        conn.close()
        return

    cursor = conn.cursor()

    # Step 3: Find reviews needing backfill
    query = """
        SELECT re.review_id, rr.text_original
        FROM reviews_enriched re
        JOIN reviews_raw rr ON re.review_id = rr.id
        WHERE re.issues IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    to_backfill = cursor.fetchall()
    total = len(to_backfill)
    print(f"\nFound {total} reviews needing LLM backfill.")

    if total == 0:
        print("Nothing to do. All reviews already have issues extracted.")
        cursor.close()
        conn.close()
        return

    # Step 4: Process in batches
    updated = 0
    failed = 0

    for i, row in enumerate(to_backfill):
        review_id = row['review_id']
        text = row['text_original']

        result = extract_issues_and_topics(text, client)

        try:
            cursor.execute("""
                UPDATE reviews_enriched
                SET issues = %s,
                    sub_topics = %s,
                    user_intent = %s,
                    severity = %s,
                    product_area = %s,
                    llm_model_version = %s
                WHERE review_id = %s
            """, (
                result['issues'] or None,
                result['sub_topics'] or None,
                result['user_intent'],
                result['severity'],
                result['product_area'],
                LLM_MODEL,
                review_id,
            ))
            conn.commit()
            updated += 1
        except Exception as e:
            print(f"  Failed to update review {review_id}: {e}")
            conn.rollback()
            failed += 1

        # Rate limiting
        if (i + 1) % PAUSE_EVERY == 0:
            print(f"  [{i+1}/{total}] Pausing {PAUSE_SECONDS}s for rate limits...")
            time.sleep(PAUSE_SECONDS)
        else:
            time.sleep(0.5)

    cursor.close()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"Migration complete!")
    print(f"  Updated: {updated}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {total}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    run_migration(limit=limit, dry_run=dry_run)
