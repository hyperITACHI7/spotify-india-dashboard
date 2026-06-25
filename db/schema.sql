-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE topics (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    keywords    TEXT[] NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_string  TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL,   -- 'ios' | 'android'
    release_date    DATE NOT NULL,
    changelog       TEXT
);

CREATE TABLE reviews_raw (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_review_id  TEXT,
    source              TEXT NOT NULL,   -- 'appstore' | 'playstore' | 'reddit' | 'twitter'
    platform            TEXT,            -- 'ios' | 'android' | null
    rating              SMALLINT,        -- 1-5 or NULL
    text_original       TEXT NOT NULL,
    text_cleaned        TEXT,
    language_detected   CHAR(5),
    text_translated     TEXT,
    is_translated       BOOL DEFAULT FALSE,
    app_version_id      UUID REFERENCES app_versions(id),
    country_code        CHAR(2),         -- 'IN' for India (enforced at ingestion)
    review_hash         TEXT UNIQUE NOT NULL,
    is_duplicate        BOOL DEFAULT FALSE,
    is_spam             BOOL DEFAULT FALSE,
    ingestion_run_id    UUID,            -- links to ingestion_runs table (see below)
    relevance_score     FLOAT,           -- computed before N-limit truncation
    created_at          TIMESTAMPTZ NOT NULL,   -- original review date
    ingested_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Tracks each ingestion run for audit + token budget accounting
CREATE TABLE ingestion_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    region_filter       CHAR(2) NOT NULL DEFAULT 'IN',
    review_limit_n      INT NOT NULL,
    relevance_strategy  TEXT NOT NULL,
    reviews_fetched     INT,
    reviews_stored      INT,
    estimated_tokens    INT,
    actual_tokens_used  INT,             -- populated after NLP run completes
    triggered_by        TEXT,            -- 'scheduler' | 'api' | 'dashboard'
    status              TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'done' | 'failed'
    is_snapshot         BOOL DEFAULT FALSE
);

-- Partial index to enforce India-only constraint
CREATE INDEX idx_reviews_country_india ON reviews_raw(country_code)
    WHERE country_code = 'IN';

CREATE TABLE reviews_enriched (
    review_id               UUID PRIMARY KEY REFERENCES reviews_raw(id),
    sentiment_score         FLOAT NOT NULL,       -- [-1.0, +1.0]
    sentiment_label         TEXT NOT NULL,        -- POSITIVE | NEGATIVE | NEUTRAL
    sentiment_confidence    FLOAT NOT NULL,
    sentiment_model_version TEXT,
    top_keywords            TEXT[],
    -- Phase 1: Enhanced Issue Extraction (LLM-powered)
    issues                  TEXT[],              -- Extracted concrete issues (e.g., 'premium popups')
    sub_topics              TEXT[],              -- Hierarchical sub-topics
    user_intent             VARCHAR(50),         -- Complaint | Praise | Question | Suggestion
    severity                VARCHAR(20),         -- Low | Medium | High | Critical
    product_area            VARCHAR(50),         -- Monetization | Discovery | Playback | UX | Content | Social
    llm_model_version       TEXT,               -- LLM model used for extraction
    nlp_processed           BOOL DEFAULT TRUE,
    processed_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE review_topics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id   UUID NOT NULL REFERENCES reviews_raw(id),
    topic_id    TEXT NOT NULL REFERENCES topics(id),
    confidence  FLOAT NOT NULL,
    method      TEXT NOT NULL,   -- 'rule' | 'ml' | 'llm' | 'hybrid'
    sub_topic   TEXT,            -- Phase 2: validated sub-topic from taxonomy
    UNIQUE (review_id, topic_id)
);

CREATE TABLE alerts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id      TEXT REFERENCES topics(id),
    alert_type    TEXT NOT NULL,
    severity      TEXT NOT NULL,
    description   TEXT NOT NULL,
    metric_value  FLOAT,
    threshold     FLOAT,
    detected_at   TIMESTAMPTZ DEFAULT NOW(),
    is_resolved   BOOL DEFAULT FALSE,
    resolved_at   TIMESTAMPTZ
);

-- Phase 3: Synthesized Topic Summaries (LLM-generated, not excerpts)
CREATE TABLE topic_summaries (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id                 TEXT NOT NULL REFERENCES topics(id),
    sub_topic                TEXT,               -- NULL for parent-topic summaries
    summary_text             TEXT NOT NULL,
    review_count             INTEGER,
    sentiment_distribution   JSONB,              -- {"positive": 0.6, "negative": 0.3, "neutral": 0.1}
    dominant_issues          TEXT[],
    generated_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_reviews_raw_created_at    ON reviews_raw(created_at);
CREATE INDEX idx_reviews_raw_source         ON reviews_raw(source);
CREATE INDEX idx_reviews_raw_rating         ON reviews_raw(rating);
CREATE INDEX idx_reviews_raw_country        ON reviews_raw(country_code);
CREATE INDEX idx_reviews_raw_run_id         ON reviews_raw(ingestion_run_id);
CREATE INDEX idx_review_topics_topic_id     ON review_topics(topic_id);
CREATE INDEX idx_review_topics_review_id    ON review_topics(review_id);
CREATE INDEX idx_enriched_sentiment_label   ON reviews_enriched(sentiment_label);
CREATE INDEX idx_enriched_sentiment_score   ON reviews_enriched(sentiment_score);
CREATE INDEX idx_enriched_severity          ON reviews_enriched(severity);
CREATE INDEX idx_enriched_user_intent       ON reviews_enriched(user_intent);
CREATE INDEX idx_enriched_product_area      ON reviews_enriched(product_area);
CREATE INDEX idx_enriched_issues            ON reviews_enriched USING GIN(issues);
CREATE INDEX idx_ingestion_runs_run_at      ON ingestion_runs(run_at DESC);
CREATE INDEX idx_review_topics_sub_topic    ON review_topics(sub_topic);  -- Phase 2
CREATE INDEX idx_enriched_sub_topics         ON reviews_enriched USING GIN(sub_topics);  -- Phase 2
CREATE INDEX idx_topic_summaries_topic_id   ON topic_summaries(topic_id);  -- Phase 3
CREATE INDEX idx_topic_summaries_sub_topic  ON topic_summaries(sub_topic); -- Phase 3
CREATE UNIQUE INDEX idx_topic_summaries_unique ON topic_summaries(topic_id, COALESCE(sub_topic, '__parent__'));

-- Full-text search on review text (English + Indic languages via pg_trgm fallback)
CREATE INDEX idx_reviews_fts ON reviews_raw
    USING GIN (to_tsvector('english', COALESCE(text_translated, text_original)));

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_reviews_trgm ON reviews_raw
    USING GIN (text_original gin_trgm_ops);  -- trigram index for Hindi/Tamil text search
