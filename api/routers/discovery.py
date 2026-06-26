from fastapi import APIRouter, Response, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from aggregation import discovery_stats
from core import llm as _llm
from ingestion.pipeline import ingest_run
from nlp.pipeline import run_nlp_pipeline

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

# =====================================================================
# SCRAPE PROGRESS TRACKER (in-memory, thread-safe for single-process)
# =====================================================================
def _fresh_progress() -> Dict[str, Any]:
    return {"status": "idle", "stage": "", "current": 0, "total": 0, "message": ""}

_scrape_progress: Dict[str, Any] = _fresh_progress()


def _update_progress(stage: str, current: int = 0, total: int = 0, message: str = "", status: str = "running"):
    """Update the global scrape progress tracker."""
    _scrape_progress["status"] = status
    _scrape_progress["stage"] = stage
    _scrape_progress["current"] = current
    _scrape_progress["total"] = total
    _scrape_progress["message"] = message


def run_background_scraping_task(limit: int):
    """Fetches reviews + runs VADER, marks scrape complete so the dashboard shows data
    immediately, then launches NLP topic analysis in a background thread so the topic
    widgets can display a real live progress bar while it runs.
    Progress mapping: 0-80% = ingestion + VADER, 80% = scrape done (dashboard unlocks),
    NLP progress tracked separately via /nlp-progress endpoint."""
    try:
        print(f"Background scrape task triggered with limit {limit}...")

        def ingestion_progress(current, total, msg):
            _update_progress("ingestion", current, total, msg)

        ingest_run(limit_override=limit, progress_callback=ingestion_progress)
        print("Ingestion + VADER done. Unlocking dashboard and launching NLP in background...")

        import aggregation.discovery_stats as _ds
        _ds.invalidate_llm_caches()
        _ds.set_data_mode("live")

        # Stage 1 done — dashboard can now refresh with VADER data.
        # Keep status="nlp_running" so the progress bar stays visible.
        # Stage 2 (NLP) runs in a background thread and feeds its progress
        # back into _scrape_progress. The bar only closes once NLP finishes.
        _update_progress("nlp", 0, limit,
                         "Reviews scraped! Running topic analysis…",
                         status="nlp_running")

        def _nlp_thread():
            try:
                def _cb(current, total):
                    discovery_stats.set_nlp_progress(current, total, "running")
                    msg = f"Topic analysis: {current}/{total} reviews processed" if total else "Topic analysis running…"
                    _update_progress("nlp", current, total, msg, status="nlp_running")

                discovery_stats.set_nlp_progress(0, 0, "running")
                run_nlp_pipeline(limit=limit * 2, progress_callback=_cb)
                discovery_stats.set_nlp_progress(0, 0, "done")
                _ds.invalidate_llm_caches()
                _update_progress("done", limit, limit,
                                 f"All done! {limit} reviews scraped and topics analyzed.",
                                 status="completed")
                print("Background NLP complete.")
            except Exception as e:
                print(f"Background NLP failed (non-fatal, VADER data still in DB): {e}")
                discovery_stats.set_nlp_progress(0, 0, "done")
                _update_progress("done", limit, limit,
                                 f"{limit} reviews scraped. Topic analysis incomplete — VADER data saved.",
                                 status="completed")

        import threading
        threading.Thread(target=_nlp_thread, daemon=True).start()

    except Exception as e:
        print(f"Failed to execute background scrape pipeline: {e}")
        _update_progress("error", 0, limit, f"Scrape failed: {str(e)}", status="error")

@router.post("/scrape")
def trigger_scrape(
    limit: int = Query(50, description="Number of reviews to scrape"),
    background_tasks: BackgroundTasks = None
):
    """Triggers live app review scraping and VADER enrichment in the background.
    Returns immediately. Poll GET /scrape-progress for status updates."""
    if _scrape_progress["status"] == "running":
        return {"status": "already_running", "message": "A scrape is already in progress. Please wait."}

    # Pre-flight: check DB is reachable before starting the pipeline
    from aggregation.discovery_stats import _is_db_reachable, _DB_REACHABLE
    global _DB_REACHABLE  # noqa: F841 — force re-probe on each scrape attempt
    import aggregation.discovery_stats as _ds
    _ds._DB_REACHABLE = None     # reset cache so scrape always re-probes
    _ds._HAS_LIVE_DATA = None   # reset so post-scrape widgets see fresh data
    if not _ds._is_db_reachable():
        return {
            "status": "error",
            "message": (
                "PostgreSQL is not reachable at localhost:5432. "
                "Start your database server and try again."
            ),
        }

    _update_progress("starting", 0, limit, "Preparing to scrape reviews...", status="running")

    if background_tasks:
        background_tasks.add_task(run_background_scraping_task, limit)
        return {"status": "started", "message": f"Scraping {limit} reviews in background. Poll /scrape-progress for updates."}
    else:
        # Fallback: run synchronously if BackgroundTasks not available
        run_background_scraping_task(limit)
        return {"status": "success", "message": "Scraper pipeline completed successfully."}

@router.get("/scrape-progress")
def get_scrape_progress():
    """Returns the current scrape progress for the frontend progress bar."""
    return _scrape_progress.copy()

@router.get("/nlp-progress")
def get_nlp_progress():
    return {"status": "ok", "data": discovery_stats.get_nlp_progress()}

@router.get("/stats")
def get_stats(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Returns overall KPIs, sentiment distribution, and trend over time."""
    data = discovery_stats.get_stats_aggregated(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}

@router.get("/topics")
def get_topics(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Returns the Topic Sentiment Matrix (spreadsheet table rows)."""
    data = discovery_stats.get_topics_matrix(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}

@router.get("/topics/{topic_id}/subtopics")
def get_subtopics(
    topic_id: str,
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Phase 2: Returns sub-topic drill-down stats for a given parent topic."""
    data = discovery_stats.get_subtopics_for_topic(
        topic_id=topic_id,
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}

@router.get("/topics/{topic_id}/summary")
def get_topic_summary(topic_id: str):
    """Phase 3: Returns the synthesized LLM summary for a given topic."""
    data = discovery_stats.get_topic_summary(topic_id=topic_id)
    return {"status": "success", "data": data}

# =====================================================================
# PHASE 4: INTENT, SEVERITY & PRIORITY ENDPOINTS
# =====================================================================

@router.get("/intent-distribution")
def get_intent_distribution(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = ""
):
    """Phase 4: Returns distribution of user intents across filtered reviews."""
    data = discovery_stats.get_intent_distribution(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search
    )
    return {"status": "success", "data": data}

@router.get("/severity-breakdown")
def get_severity_breakdown(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = ""
):
    """Phase 4: Returns severity distribution by topic."""
    data = discovery_stats.get_severity_breakdown(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search
    )
    return {"status": "success", "data": data}

@router.get("/priority-issues")
def get_priority_issues(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    limit: int = 10
):
    """Phase 4: Returns top priority issues based on severity + volume + sentiment."""
    data = discovery_stats.get_priority_issues(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        limit=limit
    )
    return {"status": "success", "data": data}

# =====================================================================
# PHASE 5: INTELLIGENT BUZZWORD EXTRACTION ENDPOINTS
# =====================================================================

@router.get("/frustrations")
def get_frustrations(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    limit: int = 20
):
    """Phase 5: Returns top frustration buzzwords (from issues, not adjectives)."""
    data = discovery_stats.get_frustration_cloud(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        limit=limit
    )
    return {"status": "success", "data": data}

@router.get("/positive-buzzwords")
def get_positive_buzzwords(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    limit: int = 20
):
    """Phase 5: Returns top positive buzzwords (from issues/praise, not adjectives)."""
    data = discovery_stats.get_positive_buzzwords(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        limit=limit
    )
    return {"status": "success", "data": data}

# =====================================================================
# PHASE 6: CLUSTERING & TREND ANALYSIS ENDPOINTS
# =====================================================================

@router.get("/clusters")
def get_clusters(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = ""
):
    """Phase 6: Returns clustered issues with volume and sentiment distribution."""
    data = discovery_stats.get_issue_clusters(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search
    )
    return {"status": "success", "data": data}

@router.get("/trends")
def get_trends(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    lookback_days: int = 7
):
    """Phase 6: Returns emerging/stable/declining issue trends."""
    data = discovery_stats.get_trends(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        lookback_days=lookback_days
    )
    return {"status": "success", "data": data}

@router.get("/anomalies")
def get_anomalies(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    window_days: int = 14
):
    """Phase 6: Returns sentiment anomalies and unusual patterns."""
    data = discovery_stats.get_anomalies(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        window_days=window_days
    )
    return {"status": "success", "data": data}

@router.get("/keywords")
def get_keywords(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Returns top keywords found in positive vs negative reviews."""
    data = discovery_stats.get_top_keywords(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}

@router.get("/reviews")
def get_reviews(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    topic: Optional[str] = None,
    issue_keyword: Optional[str] = None,
    keyword_sentiment: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    data_mode: Optional[str] = None
):
    """Returns a filtered, paginated list of reviews (for drill-down)."""
    data = discovery_stats.get_reviews_list(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        topic=topic,
        issue_keyword=issue_keyword,
        keyword_sentiment=keyword_sentiment,
        page=page,
        page_size=page_size,
        mode=data_mode
    )
    return {"status": "success", "data": data}

@router.get("/export")
def export_csv(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = ""
):
    """Generates and triggers download for the filtered review list as a CSV."""
    csv_data = discovery_stats.get_raw_csv_string(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered_reviews.csv"}
    )

class SynthesisResponse(BaseModel):
    summary: str
    error: Optional[str] = None

@router.post("/ai-synthesis", response_model=SynthesisResponse)
def synthesize_findings(
    date_range: str = Query("All"),
    version: str = Query("All"),
    rating: str = Query("All"),
    platform: str = Query("All"),
    search: str = Query(""),
    data_mode: str = Query(None)
):
    """
    Calls the LLM to synthesize top discovery frustrations into a brief summary.
    In snapshot mode, returns pre-computed data instantly without an LLM call.
    Results are cached per (mode + filters) and cleared on mode switch or scrape.
    """
    import aggregation.discovery_stats as _ds
    effective_mode = data_mode if data_mode in ("snapshot", "live") else _ds.get_data_mode()
    cache_key = (effective_mode, date_range, version, rating, platform, search)
    if cache_key in _ds._synthesis_cache:
        return {"summary": _ds._synthesis_cache[cache_key]}

    # Snapshot mode: return pre-computed synthesis, no LLM needed
    snapshot_text = discovery_stats.get_synthesis_for_mode(date_range, version, rating, platform, search, mode=data_mode)
    if snapshot_text is not None:
        _ds._synthesis_cache[cache_key] = snapshot_text
        return {"summary": snapshot_text}

    # Build cross-topic context — stats + topic matrix + worst reviews per topic
    stats = discovery_stats.get_stats_aggregated(date_range, version, rating, platform, search, mode=data_mode)
    total_reviews = stats.get("total_reviews", 0)
    if total_reviews == 0:
        return {"summary": "", "error": "No reviews found for the selected filters."}

    sent_dist = stats.get("sentiment_distribution", {})
    neg_pct = round((sent_dist.get("NEGATIVE", 0) / total_reviews) * 100) if total_reviews else 0
    pos_pct = round((sent_dist.get("POSITIVE", 0) / total_reviews) * 100) if total_reviews else 0
    avg_rating = stats.get("average_rating", 0)

    matrix = discovery_stats.get_topics_matrix(date_range, version, rating, platform, search, mode=data_mode)

    # Top negative reviews per topic (up to 3 each, top 4 topics)
    all_reviews = discovery_stats.filter_mock_reviews(date_range, version, rating, platform, search, mode=data_mode)
    all_negatives = sorted([r for r in all_reviews if r.get("sentiment") == "NEGATIVE"],
                           key=lambda r: r.get("score", 0))

    topic_sections = []
    for t in (matrix or [])[:5]:
        tid = t["id"]
        topic_revs = [r for r in all_negatives if tid in (r.get("topics") or [])]
        sample = topic_revs[:3]
        excerpt_block = "\n".join(f'    [{r.get("rating", "?")}★] "{(r.get("text") or "")[:160]}"' for r in sample)
        topic_sections.append(
            f"  • {t['label']}: {t['reviews_count']} reviews | "
            f"{t.get('pct_negative', 0)}% negative | trend: {t.get('trend', '—')}\n"
            + (excerpt_block if excerpt_block else "    (no negative reviews in this topic)")
        )

    # Fallback: if no topics, use raw negative reviews
    if not topic_sections:
        raw = "\n".join(f'  - "{(r.get("text") or "")[:180]}"' for r in all_negatives[:12])
        if not raw:
            return {"summary": "", "error": "No negative reviews found to synthesize."}
        topic_sections = [raw]

    topic_context = "\n\n".join(topic_sections)

    prompt = f"""You are a senior product analyst at Spotify India. You have been given the full review intelligence report below. Write a structured product briefing for the product team.

REPORT DATA:
- Total reviews: {total_reviews}
- Average rating: {avg_rating:.1f}/5
- Sentiment: {neg_pct}% negative · {pos_pct}% positive

TOP PROBLEM AREAS (with real user quotes):
{topic_context}

Write a structured briefing with EXACTLY these 4 sections. Use the exact headers shown.

**Executive Summary**
2-3 sentences. Name the single biggest problem and its scope (cite specific numbers from the data). Be direct and analytical.

**Key Problem Areas**
3-5 bullet points. Each must cite the topic name, review volume, and negative percentage. End each bullet with the core user pain in one phrase.

**Root Cause Analysis**
2-3 sentences. Identify the underlying product or engineering failures causing the problems above. Be specific — name features, flows, or systems.

**Recommended Product Actions**
3-5 numbered actions. Each must be concrete and implementable (not vague like "improve UX"). Reference which topic/problem area it addresses. Include a measurable success criterion for each.

No preamble, no closing remarks. Output only the 4 sections."""

    try:
        client = _llm.get_client()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=_llm.model(),
            max_tokens=1200,
            temperature=0.3,
        )
        summary = chat_completion.choices[0].message.content
        _ds._synthesis_cache[cache_key] = summary
        return {"summary": summary}
    except Exception as e:
        err = str(e)
        if "rate_limit" in err.lower() or "429" in err:
            msg = "Daily LLM rate limit reached. AI Synthesis will be available once the quota resets."
        elif "api_key" in err.lower() or "authentication" in err.lower() or "401" in err:
            msg = "LLM API key invalid or missing. Check your GROQ_API_KEY in the environment settings."
        elif "connection" in err.lower() or "timeout" in err.lower():
            msg = "LLM provider unreachable. Check your network connection."
        else:
            msg = f"LLM error: {err[:200]}"
        # Don't cache errors — next request should retry
        return {"summary": "", "error": msg}

@router.get("/alerts")
def get_alerts(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Returns dynamic anomaly alerts based on the current filters."""
    data = discovery_stats.get_anomaly_alerts(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}

# =====================================================================
# PHASE 7: HYPOTHESIS GENERATION ENDPOINT
# =====================================================================

@router.get("/hypotheses")
def get_hypotheses(
    date_range: str = "All",
    version: str = "All",
    rating: str = "All",
    platform: str = "All",
    search: str = "",
    data_mode: Optional[str] = None
):
    """Phase 7: Returns AI-generated product hypotheses from review intelligence."""
    data = discovery_stats.get_hypotheses(
        date_range=date_range,
        version=version,
        rating=rating,
        platform=platform,
        search=search,
        mode=data_mode
    )
    return {"status": "success", "data": data}


# =====================================================================
# DATA MODE (snapshot / live)
# =====================================================================

class ModeRequest(BaseModel):
    mode: str  # "snapshot" | "live"

@router.get("/mode")
def get_mode():
    """Returns current data mode plus snapshot/live run metadata."""
    mode = discovery_stats.get_data_mode()
    snapshot_info = None
    live_info = None
    if discovery_stats._is_db_reachable():
        try:
            from core.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT reviews_stored, run_at FROM ingestion_runs WHERE is_snapshot = TRUE ORDER BY run_at DESC LIMIT 1")
            row = cursor.fetchone()
            cursor.execute("SELECT reviews_stored, run_at FROM ingestion_runs WHERE is_snapshot = FALSE ORDER BY run_at DESC LIMIT 1")
            live_row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                snapshot_info = {"reviews": row["reviews_stored"], "scraped_at": str(row["run_at"])[:10]}
            if live_row:
                live_info = {"reviews": live_row["reviews_stored"], "scraped_at": str(live_row["run_at"])[:10]}
        except Exception:
            pass
    return {"status": "success", "data": {"mode": mode, "snapshot": snapshot_info, "live": live_info}}


@router.post("/mode")
def set_mode(body: ModeRequest):
    """Switches the dashboard data source between snapshot and live."""
    if body.mode not in ("snapshot", "live"):
        return {"status": "error", "message": "mode must be 'snapshot' or 'live'"}
    discovery_stats.set_data_mode(body.mode)
    import aggregation.discovery_stats as _ds
    _ds._HAS_LIVE_DATA = None
    return {"status": "success", "data": {"mode": body.mode}}
