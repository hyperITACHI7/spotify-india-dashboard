"""
aggregation/discovery_stats.py

Handles stats, charts, matrix tables, and review querying.
Supports dual-mode execution:
1. SQL Database: Queries PostgreSQL reviews_raw, reviews_enriched, review_topics, app_versions.
2. Filterable Mock Fallback: Serves a rich, interactive in-memory dataset if the DB is offline.
"""

import os
import json
from datetime import datetime, timedelta
import re
from typing import Dict, List, Any
import hashlib
from core.llm import get_client as _get_llm_client, model as _llm_model

# Attempt to import DB connection
try:
    from core.db import get_connection
    HAS_DB = True
except Exception:
    HAS_DB = False

# Cached DB reachability — avoids repeated slow connection attempts when DB is down.
# None = not yet probed; True/False = cached result for this server process.
_DB_REACHABLE: bool | None = None
_HAS_LIVE_DATA: bool | None = None  # cached after first successful DB count check
_DATA_MODE: str = "snapshot"        # "snapshot" | "live" — persists for server process lifetime

# LLM result caches — keyed by (mode, date_range, version, rating, platform, search).
# Cleared whenever mode switches or a scrape completes.
_hypotheses_cache: dict = {}
_synthesis_cache: dict = {}


def get_data_mode() -> str:
    return _DATA_MODE


def set_data_mode(mode: str) -> None:
    global _DATA_MODE
    if mode in ("snapshot", "live"):
        _DATA_MODE = mode
        _hypotheses_cache.clear()
        _synthesis_cache.clear()


def invalidate_llm_caches() -> None:
    """Call this after a scrape completes so the next load regenerates from fresh data."""
    _hypotheses_cache.clear()
    _synthesis_cache.clear()

def _is_db_reachable() -> bool:
    """Returns True if the DB is reachable. Result is cached for the process lifetime."""
    global _DB_REACHABLE
    if _DB_REACHABLE is not None:
        return _DB_REACHABLE
    if not HAS_DB:
        _DB_REACHABLE = False
        return False
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        _DB_REACHABLE = True
    except Exception:
        _DB_REACHABLE = False
    return _DB_REACHABLE

# Pinned topic that is always shown
PINNED_TOPIC = "search_discovery"

# Topic label cache from DB
_topic_label_cache = {}

def _get_topic_label(topic_id: str) -> str:
    """Converts a snake_case topic_id to a human-readable label.
    Tries DB lookup first, then falls back to title-casing the ID."""
    if topic_id in _topic_label_cache:
        return _topic_label_cache[topic_id]

    # Try DB lookup
    if _is_db_reachable():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT label FROM topics WHERE id = %s", (topic_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                _topic_label_cache[topic_id] = row['label']
                return row['label']
        except Exception:
            pass
    
    # Fallback: convert snake_case to Title Case
    label = topic_id.replace('_', ' ').title()
    # Fix common abbreviations
    label = label.replace(' And ', ' & ').replace('Ui', 'UI')
    _topic_label_cache[topic_id] = label
    return label

# Topic summary cache
_summary_cache = {}

def _auto_summarize_topic(reviews: List[Dict], topic_id: str) -> str:
    """Uses Groq LLM to generate a concise analyst-quality summary from the most common negative phrases."""
    neg_reviews = [r for r in reviews if r.get('sentiment') == 'NEGATIVE']
    if not neg_reviews:
        pos_reviews = [r for r in reviews if r.get('sentiment') == 'POSITIVE']
        if pos_reviews:
            return None  # Signal caller to use rule-based for positive topics
        return None

    # Get the top 10 most negative reviews (sorted by score ascending = most negative first)
    neg_reviews.sort(key=lambda r: r.get('score', 0))
    top_negs = neg_reviews[:10]

    # Create cache key based on the exact review texts
    hash_input = "".join([r['text'] for r in top_negs]).encode('utf-8')
    cache_key = topic_id + "_" + hashlib.md5(hash_input).hexdigest()

    if cache_key in _summary_cache:
        return _summary_cache[cache_key]

    # Build context: use extracted issues when available, otherwise review text
    context_lines = []
    for r in top_negs:
        issues_str = ", ".join(r.get('issues') or [])
        snippet = (r.get('text') or '')[:150]
        if issues_str:
            context_lines.append(f"- Issues: {issues_str} | Review: {snippet}")
        else:
            context_lines.append(f"- {snippet}")
    context_text = "\n".join(context_lines)

    topic_label = _get_topic_label(topic_id)
    prompt = (
        f"You are a product analyst. Synthesize a concise analytical summary for the Spotify topic \"{topic_label}\" "
        f"based on these {len(top_negs)} negative reviews.\n\n"
        f"Reviews:\n{context_text}\n\n"
        f"Requirements:\n"
        f"- Length: 20-30 words\n"
        f"- Tone: objective, analytical — NOT conversational, do NOT start with 'Users'\n"
        f"- Focus: the root cause or dominant pain point with specific feature names\n"
        f"- NEVER copy any review sentence verbatim\n\n"
        f"Generate summary:"
    )

    try:
        client = _get_llm_client()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=_llm_model(),
            max_tokens=80,
            temperature=0.3
        )
        summary = chat_completion.choices[0].message.content.strip()
        summary = summary.strip('"\'').replace('\n', ' ')
        # Strip markdown fences
        if summary.startswith("```"):
            summary = summary.split("\n", 1)[1] if "\n" in summary else summary[3:]
        if summary.endswith("```"):
            summary = summary[:-3]
        summary = summary.strip()
        # Enforce word count cap
        words = summary.split()
        if len(words) > 35:
            summary = " ".join(words[:30]) + "..."

        _summary_cache[cache_key] = summary
        return summary
    except Exception:
        # Never return verbatim review text — fall back to rule-based
        return None

# Phase 3: Quick lookup for pre-computed synthesized summaries
def _get_phase3_summary(topic_id: str) -> str | None:
    """
    Phase 3: Returns a pre-computed synthesized summary if available.
    Checks: (1) DB topic_summaries table, (2) _MOCK_TOPIC_SUMMARIES dict.
    Returns None if not found (caller falls back to _auto_summarize_topic).
    """
    # Check DB first
    if _is_db_reachable():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT summary_text FROM topic_summaries "
                "WHERE topic_id = %s AND sub_topic IS NULL "
                "ORDER BY generated_at DESC LIMIT 1",
                (topic_id,)
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return row['summary_text']
        except Exception:
            pass
    # Check mock dict (defined later in file but accessible at call time)
    mock = globals().get('_MOCK_TOPIC_SUMMARIES', {})
    return mock.get(topic_id)

def _compute_trend(reviews: List[Dict]) -> str:
    """Computes a real trend by comparing recent-week vs prior-week negative %."""
    today = datetime(2026, 6, 21)
    recent_start = today - timedelta(days=7)
    prior_start = today - timedelta(days=14)
    
    recent = []
    prior = []
    for r in reviews:
        try:
            rd = datetime.strptime(r['date'], '%Y-%m-%d')
        except (ValueError, KeyError):
            continue
        if rd >= recent_start:
            recent.append(r)
        elif rd >= prior_start:
            prior.append(r)
    
    if not prior or not recent:
        return '0% change'
    
    recent_neg_pct = (sum(1 for r in recent if r['sentiment'] == 'NEGATIVE') / len(recent)) * 100
    prior_neg_pct = (sum(1 for r in prior if r['sentiment'] == 'NEGATIVE') / len(prior)) * 100
    
    delta = round(recent_neg_pct - prior_neg_pct)
    if delta > 0:
        return f'+{delta}% neg'
    elif delta < 0:
        return f'{delta}% neg'
    return '0% change'

# Release dates to highlight on the trend chart
RELEASE_DATES = {
    "2026-06-05": "v8.9.10 Update",
    "2026-06-12": "v8.9.12 Hotfix",
    "2026-06-19": "v9.0.2 Redesign"
}

# =====================================================================
# RICH MOCK DATASET FOR OFFLINE DEVELOPMENT
# =====================================================================
MOCK_REVIEWS = [
    # Song Discovery
    {"date": "2026-06-20", "rating": 1, "sentiment": "NEGATIVE", "score": -0.85, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["search_discovery"],
     "sub_topics": ["Repetitive suggestions", "Release Radar"],
     "issues": ["repetitive song recommendations", "stale Release Radar"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Discovery", "emotional_tone": "Frustrated",
     "text": "Keeps playing the exact same 5 songs over and over. Release Radar and Discover Weekly are stuck in a repetitive loop!"},
    {"date": "2026-06-19", "rating": 2, "sentiment": "NEGATIVE", "score": -0.60, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["search_discovery"],
     "sub_topics": ["Recommendation relevance", "Regional music discovery"],
     "issues": ["broken recommendation algorithm", "ignores regional music preferences"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Discovery", "emotional_tone": "Frustrated",
     "text": "The recommendation algorithm is completely broken for Hindi indie music. I keep getting major Bollywood songs instead of indie artists."},
    {"date": "2026-06-18", "rating": 1, "sentiment": "NEGATIVE", "score": -0.75, "version": "v8.9.12", "platform": "ios", "source": "appstore", "topics": ["search_discovery"],
     "sub_topics": ["Autoplay relevance", "Algorithm learning"],
     "issues": ["stale autoplay recommendations", "algorithm stuck in bubble"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Discovery", "emotional_tone": "Frustrated",
     "text": "I can't find any new artists anymore, recommendations are stuck in a bubble. Autoplay just plays what I listened to yesterday."},
    {"date": "2026-06-17", "rating": 5, "sentiment": "POSITIVE", "score": 0.90, "version": "v8.9.12", "platform": "ios", "source": "appstore", "topics": ["search_discovery"],
     "sub_topics": ["Daily Mix quality", "Algorithm learning"],
     "issues": ["excellent Daily Mix curation"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Discovery", "emotional_tone": "Satisfied",
     "text": "Found some absolute gems on Daily Mix today! Spotify's algorithm knows my taste perfectly."},
    {"date": "2026-06-16", "rating": 2, "sentiment": "NEGATIVE", "score": -0.40, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["search_discovery"],
     "sub_topics": ["Search accuracy"],
     "issues": ["irrelevant search results"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Discovery", "emotional_tone": "Frustrated",
     "text": "The search tab results are highly irrelevant lately. If I type a small artist name, it just shows popular albums that are unrelated."},

    # Playlists & Library
    {"date": "2026-06-20", "rating": 2, "sentiment": "NEGATIVE", "score": -0.50, "version": "v9.0.2", "platform": "ios", "source": "appstore", "topics": ["playlists_library"],
     "sub_topics": ["Library layout"],
     "issues": ["confusing library layout", "cluttered interface"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "UX", "emotional_tone": "Frustrated",
     "text": "Why did they change the library layout? I can't easily find my liked songs. The interface is cluttered."},
    {"date": "2026-06-19", "rating": 1, "sentiment": "NEGATIVE", "score": -0.70, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["playlists_library"],
     "sub_topics": ["Custom playlist creation"],
     "issues": ["custom playlists disappeared after update", "data loss"],
     "user_intent": "Complaint", "severity": "Critical", "product_area": "UX", "emotional_tone": "Frustrated",
     "text": "My local custom playlists are gone after the update! I had 200 curated songs and the queue is empty now."},
    {"date": "2026-06-15", "rating": 4, "sentiment": "POSITIVE", "score": 0.75, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["playlists_library"],
     "sub_topics": ["Collaborative playlists"],
     "issues": ["smooth collaborative playlist sharing"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Social", "emotional_tone": "Satisfied",
     "text": "Love the collaborative playlists feature, sharing mixes with friends is so smooth."},

    # Offline Mode
    {"date": "2026-06-21", "rating": 1, "sentiment": "NEGATIVE", "score": -0.90, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["offline_mode"],
     "sub_topics": ["Offline playback bugs", "Download reliability"],
     "issues": ["offline mode not working", "downloaded songs won't play"],
     "user_intent": "Complaint", "severity": "Critical", "product_area": "Playback", "emotional_tone": "Frustrated",
     "text": "Offline mode is completely broken! I downloaded 3GB of songs for my flight and the app says no internet connection and won't play anything."},
    {"date": "2026-06-19", "rating": 2, "sentiment": "NEGATIVE", "score": -0.65, "version": "v9.0.2", "platform": "ios", "source": "appstore", "topics": ["offline_mode"],
     "sub_topics": ["Storage management"],
     "issues": ["downloaded tracks auto-deleting", "cache corruption"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Playback", "emotional_tone": "Frustrated",
     "text": "Downloaded tracks keep deleting themselves automatically. App cache issues are exhausting."},
    {"date": "2026-06-14", "rating": 5, "sentiment": "POSITIVE", "score": 0.85, "version": "v8.9.10", "platform": "ios", "source": "appstore", "topics": ["offline_mode"],
     "sub_topics": ["Download speed"],
     "issues": ["fast 5G download speed"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Playback", "emotional_tone": "Satisfied",
     "text": "Downloads are super fast on 5G. Perfect for offline commuting."},

    # UI / Layout
    {"date": "2026-06-20", "rating": 2, "sentiment": "NEGATIVE", "score": -0.55, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["ui_layout"],
     "sub_topics": ["Dark mode issues", "Font/readability"],
     "issues": ["poor dark mode readability", "misplaced buttons"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "UX", "emotional_tone": "Frustrated",
     "text": "The new v9 UI redesign is horrible! The font is too bold, buttons are misplaced, and it's hard to navigate on dark mode."},
    {"date": "2026-06-18", "rating": 3, "sentiment": "NEUTRAL", "score": 0.10, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["ui_layout"],
     "sub_topics": ["Navigation ease"],
     "issues": ["new interface adjustment period"],
     "user_intent": "Question", "severity": "Low", "product_area": "UX", "emotional_tone": "Neutral",
     "text": "New interface is okay but takes time getting used to. Colors are slightly different."},
    {"date": "2026-06-08", "rating": 5, "sentiment": "POSITIVE", "score": 0.95, "version": "v8.9.10", "platform": "ios", "source": "appstore", "topics": ["ui_layout"],
     "sub_topics": ["Navigation ease"],
     "issues": ["sleek dark interface design"],
     "user_intent": "Praise", "severity": "Low", "product_area": "UX", "emotional_tone": "Satisfied",
     "text": "Sleek dark interface, beautiful animations when switching tracks!"},

    # Performance & Crashes
    {"date": "2026-06-21", "rating": 1, "sentiment": "NEGATIVE", "score": -0.95, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["performance_crashes"],
     "sub_topics": ["App startup crashes"],
     "issues": ["app crashes on startup", "unusable after update"],
     "user_intent": "Complaint", "severity": "Critical", "product_area": "Playback", "emotional_tone": "Frustrated",
     "text": "App keeps crashing on startup after the v9.0.2 update! It freezes on the logo and closes. Unusable."},
    {"date": "2026-06-19", "rating": 2, "sentiment": "NEGATIVE", "score": -0.60, "version": "v9.0.2", "platform": "ios", "source": "appstore", "topics": ["performance_crashes"],
     "sub_topics": ["Scroll lag", "Battery drain"],
     "issues": ["scroll lag in playlists", "excessive battery drain"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Playback", "emotional_tone": "Frustrated",
     "text": "Extremely laggy when scrolling through playlists. The app eats my phone battery and heats it up."},
    {"date": "2026-06-11", "rating": 5, "sentiment": "POSITIVE", "score": 0.80, "version": "v8.9.10", "platform": "android", "source": "playstore", "topics": ["performance_crashes"],
     "sub_topics": [],
     "issues": ["lightweight app performance"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Playback", "emotional_tone": "Satisfied",
     "text": "App is running very fast and lightweight on my budget phone."},

    # Subscriptions & Pricing
    {"date": "2026-06-20", "rating": 2, "sentiment": "NEGATIVE", "score": -0.70, "version": "v9.0.2", "platform": "ios", "source": "appstore", "topics": ["subscriptions_pricing"],
     "sub_topics": ["Family plan pricing", "Student discount"],
     "issues": ["family plan price hike", "poor value for money"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Monetization", "emotional_tone": "Frustrated",
     "text": "Spotify premium India is becoming too expensive. The student plan is alright, but the family plan price hike is not worth it."},
    {"date": "2026-06-16", "rating": 5, "sentiment": "POSITIVE", "score": 0.90, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["subscriptions_pricing"],
     "sub_topics": ["Student discount"],
     "issues": ["affordable student discount", "convenient UPI payment"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Monetization", "emotional_tone": "Satisfied",
     "text": "Great student discount program, payment via UPI is very convenient."},

    # Content Availability
    {"date": "2026-06-17", "rating": 1, "sentiment": "NEGATIVE", "score": -0.80, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["content_availability"],
     "sub_topics": ["Missing artists", "Licensing issues"],
     "issues": ["missing regional artists due to licensing", "pushed to competitor platform"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Content", "emotional_tone": "Frustrated",
     "text": "So many Hindi indie songs and regional artists are missing from the catalog due to licensing issues. Moving to YouTube Music."},
    {"date": "2026-06-13", "rating": 3, "sentiment": "NEUTRAL", "score": -0.10, "version": "v8.9.12", "platform": "ios", "source": "appstore", "topics": ["content_availability"],
     "sub_topics": ["Regional content gaps"],
     "issues": ["limited classical music catalog"],
     "user_intent": "Suggestion", "severity": "Low", "product_area": "Content", "emotional_tone": "Hopeful",
     "text": "Catalog is huge but some local classical tracks are not available."},

    # Social & Sharing
    {"date": "2026-06-19", "rating": 4, "sentiment": "POSITIVE", "score": 0.70, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["social_sharing"],
     "sub_topics": ["Group Session / Jam"],
     "issues": ["great group jam feature"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Social", "emotional_tone": "Satisfied",
     "text": "Love the group session Jam feature! Sharing music live with friends works great."},
    {"date": "2026-06-15", "rating": 2, "sentiment": "NEGATIVE", "score": -0.45, "version": "v8.9.12", "platform": "ios", "source": "appstore", "topics": ["social_sharing"],
     "sub_topics": ["Instagram sharing bugs"],
     "issues": ["instagram sharing fails intermittently"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Social", "emotional_tone": "Frustrated",
     "text": "Sharing songs to Instagram stories fails half the time. App just glitches out."},

    # Podcasts
    {"date": "2026-06-20", "rating": 2, "sentiment": "NEGATIVE", "score": -0.50, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["podcasts"],
     "sub_topics": ["Podcast recommendations clutter"],
     "issues": ["podcast recommendations clutter homepage", "no podcast toggle option"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "UX", "emotional_tone": "Frustrated",
     "text": "I only use Spotify for music but my homepage is full of podcasts recommendation clutter! Give us a toggle to disable podcasts."},
    {"date": "2026-06-12", "rating": 5, "sentiment": "POSITIVE", "score": 0.85, "version": "v8.9.10", "platform": "android", "source": "playstore", "topics": ["podcasts"],
     "sub_topics": ["Video podcast support"],
     "issues": ["excellent video podcast support"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Content", "emotional_tone": "Satisfied",
     "text": "Best podcast selection and video support is really smooth."},

    # Ads Experience
    {"date": "2026-06-21", "rating": 1, "sentiment": "NEGATIVE", "score": -0.85, "version": "v9.0.2", "platform": "android", "source": "playstore", "topics": ["ads_experience"],
     "sub_topics": ["Ad frequency", "Unskippable ads"],
     "issues": ["excessive unskippable ads", "too many ads between songs"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Monetization", "emotional_tone": "Frustrated",
     "text": "Too many ads! There are 3 long unskippable ads after every single song on the free version. It's annoying and unusable."},
    {"date": "2026-06-14", "rating": 1, "sentiment": "NEGATIVE", "score": -0.75, "version": "v8.9.10", "platform": "ios", "source": "appstore", "topics": ["ads_experience"],
     "sub_topics": ["Ad volume levels"],
     "issues": ["ad volume louder than music", "jarring audio level changes"],
     "user_intent": "Complaint", "severity": "High", "product_area": "Monetization", "emotional_tone": "Frustrated",
     "text": "Ads volume is twice as loud as the music! It is literally hurting my ears. Free experience is terrible."},

    # Account & Login
    {"date": "2026-06-18", "rating": 2, "sentiment": "NEGATIVE", "score": -0.50, "version": "v8.9.12", "platform": "android", "source": "playstore", "topics": ["account_login"],
     "sub_topics": ["UPI authentication failures", "Two-factor verification issues"],
     "issues": ["UPI authentication failure", "two-factor email not arriving"],
     "user_intent": "Complaint", "severity": "High", "product_area": "UX", "emotional_tone": "Frustrated",
     "text": "UPI login authentication keeps failing. The two-factor verification email never arrives in my inbox."},

    # Audio Quality
    {"date": "2026-06-20", "rating": 2, "sentiment": "NEGATIVE", "score": -0.40, "version": "v9.0.2", "platform": "ios", "source": "appstore", "topics": ["audio_quality"],
     "sub_topics": ["Lossless/HiFi absence"],
     "issues": ["missing lossless HiFi audio option", "competitors offer better audio quality"],
     "user_intent": "Complaint", "severity": "Medium", "product_area": "Playback", "emotional_tone": "Hopeful",
     "text": "Where is the Lossless HiFi audio they promised years ago? Competitors like Apple Music have it at no extra cost."},
    {"date": "2026-06-10", "rating": 5, "sentiment": "POSITIVE", "score": 0.90, "version": "v8.9.10", "platform": "android", "source": "playstore", "topics": ["audio_quality"],
     "sub_topics": ["Equalizer features"],
     "issues": ["fantastic equalizer settings"],
     "user_intent": "Praise", "severity": "Low", "product_area": "Playback", "emotional_tone": "Satisfied",
     "text": "Equalizer settings are fantastic. Sounds clean on my Sony headphones."}
]

# Topic pool for generating mock data (display labels for placeholder text)
_MOCK_TOPIC_POOL = {
    "search_discovery": "Song Discovery & Recommendations",
    "playlists_library": "Playlists & Library",
    "offline_mode": "Offline Mode",
    "ui_layout": "UI / Layout",
    "performance_crashes": "Performance & Crashes",
    "subscriptions_pricing": "Subscriptions & Pricing",
    "content_availability": "Content Availability",
    "social_sharing": "Social & Sharing",
    "podcasts": "Podcasts",
    "ads_experience": "Ads Experience",
    "account_login": "Account & Login",
    "audio_quality": "Audio Quality"
}

# Phase 2: Sub-topic pool per topic for mock data generation
_MOCK_SUBTOPICS = {
    "search_discovery": ["Discover Weekly quality", "Recommendation relevance", "Search accuracy",
                         "AI DJ recommendations", "Algorithm learning", "Daily Mix quality",
                         "Release Radar", "Autoplay relevance", "Repetitive suggestions"],
    "playlists_library": ["Playlist organization", "Liked songs management", "Library layout",
                          "Custom playlist creation", "Playlist sharing"],
    "offline_mode": ["Download reliability", "Storage management", "Offline playback bugs",
                     "Download speed"],
    "ui_layout": ["Navigation ease", "Dark mode issues", "Font/readability", "Home screen layout",
                  "Button placement"],
    "performance_crashes": ["App startup crashes", "Scroll lag", "Battery drain",
                            "Memory usage", "Background playback issues"],
    "subscriptions_pricing": ["Premium value", "Family plan pricing", "Student discount",
                              "Payment failures", "Plan cancellation"],
    "content_availability": ["Regional content gaps", "Licensing issues", "Missing artists",
                             "Podcast exclusives"],
    "social_sharing": ["Instagram sharing bugs", "Group Session / Jam", "Collaborative playlists",
                       "Profile visibility"],
    "podcasts": ["Podcast recommendations clutter", "Video podcast support",
                 "Podcast download issues", "Episode discovery"],
    "ads_experience": ["Ad frequency", "Ad volume levels", "Unskippable ads",
                       "Ad relevance", "Premium upsell popups"],
    "account_login": ["UPI authentication failures", "Two-factor verification issues",
                      "Password reset problems", "Account merging"],
    "audio_quality": ["Lossless/HiFi absence", "Equalizer features", "Crossfade issues",
                      "Audio normalization"],
}

# Phase 2 helper: pick 1-2 subtopics for a topic based on review text keyword hints
def _pick_mock_subtopics(topic_id: str, text: str) -> list:
    """Heuristically pick 1-2 mock subtopics that loosely match the review text."""
    pool = _MOCK_SUBTOPICS.get(topic_id, [])
    if not pool:
        return []
    text_lower = text.lower()
    picked = []
    # Simple keyword-subtopic hints
    hints = {
        "discover weekly": "Discover Weekly quality",
        "recommend": "Recommendation relevance",
        "search": "Search accuracy",
        "autoplay": "Autoplay relevance",
        "daily mix": "Daily Mix quality",
        "release radar": "Release Radar",
        "repetitive": "Repetitive suggestions",
        "algorithm": "Algorithm learning",
        "download": "Download reliability",
        "offline": "Offline playback bugs",
        "storage": "Storage management",
        "crash": "App startup crashes",
        "lag": "Scroll lag",
        "battery": "Battery drain",
        "premium": "Premium value",
        "family": "Family plan pricing",
        "student": "Student discount",
        "ads": "Ad frequency",
        "ad ": "Ad frequency",
        "loud": "Ad volume levels",
        "unskippable": "Unskippable ads",
        "hi fi": "Lossless/HiFi absence",
        "hifi": "Lossless/HiFi absence",
        "equalizer": "Equalizer features",
        "dark mode": "Dark mode issues",
        "navigation": "Navigation ease",
        "library": "Library layout",
        "playlist": "Playlist organization",
        "liked": "Liked songs management",
        "collaborative": "Collaborative playlists",
        "sharing": "Instagram sharing bugs",
        "jam": "Group Session / Jam",
        "podcast": "Podcast recommendations clutter",
        "login": "UPI authentication failures",
        "authentication": "UPI authentication failures",
        "password": "Password reset problems",
        "missing": "Missing artists",
        "licensing": "Licensing issues",
        "regional": "Regional content gaps",
    }
    for keyword, sub in hints.items():
        if keyword in text_lower and sub in pool and sub not in picked:
            picked.append(sub)
            if len(picked) >= 2:
                break
    # Fallback: pick first subtopic if nothing matched
    if not picked and pool:
        picked.append(pool[0])
    return picked

# Phase 4: Issue pool and intent/severity mappings for mock data generation
_MOCK_ISSUES_NEGATIVE = {
    "search_discovery": ["repetitive song recommendations", "broken recommendation algorithm", "irrelevant search results", "stale autoplay"],
    "playlists_library": ["confusing library layout", "custom playlists disappeared", "liked songs hard to find", "playlist sharing issues"],
    "offline_mode": ["offline mode not working", "downloaded tracks auto-deleting", "slow download speed", "cache corruption"],
    "ui_layout": ["poor dark mode readability", "misplaced buttons", "cluttered interface", "confusing navigation"],
    "performance_crashes": ["app crashes on startup", "scroll lag in playlists", "excessive battery drain", "app freezes"],
    "subscriptions_pricing": ["family plan price hike", "poor value for money", "payment processing issues", "expensive premium"],
    "content_availability": ["missing regional artists", "limited classical catalog", "licensing gaps", "removed songs"],
    "social_sharing": ["instagram sharing fails", "collaborative playlist bugs", "profile visibility issues", "share link broken"],
    "podcasts": ["podcast clutter on homepage", "no podcast toggle option", "podcast download fails", "missing episode metadata"],
    "ads_experience": ["excessive unskippable ads", "ad volume louder than music", "too many ads between songs", "intrusive premium upsell"],
    "account_login": ["UPI authentication failure", "two-factor email not arriving", "password reset broken", "login loop"],
    "audio_quality": ["missing lossless HiFi audio", "audio normalization issues", "crossfade bugs", "volume fluctuation"],
}
_MOCK_ISSUES_POSITIVE = {
    "search_discovery": ["excellent Daily Mix curation", "great Discover Weekly", "relevant recommendations"],
    "playlists_library": ["smooth playlist sharing", "intuitive library management", "great collaborative features"],
    "offline_mode": ["fast download speed", "reliable offline playback", "efficient storage usage"],
    "ui_layout": ["sleek dark interface", "beautiful animations", "intuitive navigation"],
    "performance_crashes": ["lightweight app performance", "fast startup time", "smooth scrolling"],
    "subscriptions_pricing": ["affordable student discount", "convenient UPI payment", "great value premium"],
    "content_availability": ["huge music catalog", "great podcast selection", "exclusive content access"],
    "social_sharing": ["great group jam feature", "smooth social sharing", "fun collaborative experience"],
    "podcasts": ["excellent video podcast support", "great episode discovery", "smooth podcast playback"],
    "ads_experience": ["reasonable ad frequency", "relevant ad content", "non-intrusive ads"],
    "account_login": ["quick login process", "smooth authentication", "easy account setup"],
    "audio_quality": ["fantastic equalizer settings", "clean audio output", "great sound quality"],
}


def _infer_mock_intent_severity(rating: int, sentiment: str, topic: str) -> dict:
    """Phase 4: Infer intent, severity, product_area, emotional_tone from rating/sentiment."""
    # Intent
    if rating >= 4:
        intent = 'Praise'
    elif rating == 3:
        intent = 'Question'
    elif rating == 2:
        intent = 'Complaint'
    else:
        intent = 'Complaint'

    # Severity based on rating
    severity_map = {1: 'Critical', 2: 'Medium', 3: 'Low', 4: 'Low', 5: 'Low'}
    severity = severity_map.get(rating, 'Medium')

    # Product area from topic
    area_map = {
        'search_discovery': 'Discovery', 'playlists_library': 'UX',
        'offline_mode': 'Playback', 'ui_layout': 'UX',
        'performance_crashes': 'Playback', 'subscriptions_pricing': 'Monetization',
        'content_availability': 'Content', 'social_sharing': 'Social',
        'podcasts': 'Content', 'ads_experience': 'Monetization',
        'account_login': 'UX', 'audio_quality': 'Playback',
    }
    product_area = area_map.get(topic, 'UX')

    # Emotional tone from sentiment
    if sentiment == 'POSITIVE':
        tone = 'Satisfied'
    elif sentiment == 'NEGATIVE' and rating <= 1:
        tone = 'Frustrated'
    elif sentiment == 'NEGATIVE':
        tone = 'Frustrated'
    elif sentiment == 'NEUTRAL':
        tone = 'Neutral'
    else:
        tone = 'Neutral'

    return {
        'user_intent': intent,
        'severity': severity,
        'product_area': product_area,
        'emotional_tone': tone,
    }


# Generate more reviews dynamically to hit 150+ reviews with nice date spread
def _expand_mock_data():
    extra_reviews = []
    topics_pool = list(_MOCK_TOPIC_POOL.keys())
    base_dates = [datetime(2026, 6, 1) + timedelta(days=i) for i in range(21)]
    
    for i in range(120):
        topic = topics_pool[i % len(topics_pool)]
        date_obj = base_dates[i % len(base_dates)]
        date_str = date_obj.strftime("%Y-%m-%d")
        
        rating = (i % 5) + 1
        if rating <= 2:
            sentiment = "NEGATIVE"
            score = -0.5 - (0.1 * (i % 5))
            text = f"Experiencing issues with {_MOCK_TOPIC_POOL[topic]}. Quite buggy and frustrating."
        elif rating == 3:
            sentiment = "NEUTRAL"
            score = 0.0
            text = f"Decent experience with {_MOCK_TOPIC_POOL[topic]}, but could be improved."
        else:
            sentiment = "POSITIVE"
            score = 0.5 + (0.1 * (i % 5))
            text = f"Absolutely love {_MOCK_TOPIC_POOL[topic]}! Works incredibly well, highly recommend."
            
        version = "v9.0.2" if date_obj.day >= 19 else ("v8.9.12" if date_obj.day >= 12 else "v8.9.10")
        platform = "android" if i % 2 == 0 else "ios"
        source = "playstore" if platform == "android" else "appstore"

        # Phase 4: Add issues, intent, severity, product_area, emotional_tone
        phase4 = _infer_mock_intent_severity(rating, sentiment, topic)
        if sentiment == 'POSITIVE':
            issue_pool = _MOCK_ISSUES_POSITIVE.get(topic, ["great experience"])
        else:
            issue_pool = _MOCK_ISSUES_NEGATIVE.get(topic, ["general issue"])
        issues = [issue_pool[i % len(issue_pool)]]
        if rating <= 2 and len(issue_pool) > 1:
            issues.append(issue_pool[(i + 1) % len(issue_pool)])
        
        extra_reviews.append({
            "date": date_str,
            "rating": rating,
            "sentiment": sentiment,
            "score": score,
            "version": version,
            "platform": platform,
            "source": source,
            "topics": [topic],
            "sub_topics": _pick_mock_subtopics(topic, text),
            "issues": issues,
            "text": text,
            **phase4,
        })
    return MOCK_REVIEWS + extra_reviews

ALL_REVIEWS = _expand_mock_data()

# =====================================================================
# DATABASE CONNECTIVITY CHECK & DATA SCRAPE LOADER
# =====================================================================

def _mode_run_filter_re() -> str:
    """SQL AND-clause that filters reviews_enriched rows to the current data mode.
    Assumes the reviews_enriched table is aliased as 're' in the query."""
    if _DATA_MODE == "snapshot":
        return ("AND re.review_id IN ("
                "SELECT id FROM reviews_raw WHERE ingestion_run_id IN "
                "(SELECT id FROM ingestion_runs WHERE is_snapshot = TRUE)"
                ")")
    else:
        return ("AND re.review_id IN ("
                "SELECT id FROM reviews_raw WHERE ingestion_run_id = ("
                "SELECT id FROM ingestion_runs WHERE is_snapshot = FALSE "
                "ORDER BY run_at DESC LIMIT 1"
                "))")


def has_live_data() -> bool:
    """Returns True if the database has scraped reviews. Result is cached after first True."""
    global _HAS_LIVE_DATA
    if _HAS_LIVE_DATA is True:
        return True
    if not _is_db_reachable():
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM reviews_raw")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        result = row is not None and row['cnt'] > 0
        if result:
            _HAS_LIVE_DATA = True
        return result
    except Exception:
        return False

def get_all_reviews() -> List[Dict]:
    """
    Returns actual scraped reviews from Postgres if live data exists,
    otherwise returns the placeholder mockup dataset.
    Uses LEFT JOIN so reviews are returned even if LLM enrichment hasn't run yet.
    After scraping, ONLY real reviews are returned (no mock fallback).
    """
    if not has_live_data():
        return ALL_REVIEWS
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if _DATA_MODE == "snapshot":
            run_filter = "AND r.ingestion_run_id IN (SELECT id FROM ingestion_runs WHERE is_snapshot = TRUE)"
        else:
            # Live mode: ALL non-snapshot runs so multi-batch scrapes are fully visible
            run_filter = "AND r.ingestion_run_id IN (SELECT id FROM ingestion_runs WHERE is_snapshot = FALSE)"

        cursor.execute(f"""
            SELECT
                r.created_at::date::text as date,
                r.rating,
                COALESCE(e.sentiment_label,
                    CASE WHEN r.rating >= 4 THEN 'POSITIVE'
                         WHEN r.rating <= 2 THEN 'NEGATIVE'
                         ELSE 'NEUTRAL' END) as sentiment,
                COALESCE(e.sentiment_score,
                    CASE WHEN r.rating >= 4 THEN 0.5
                         WHEN r.rating <= 2 THEN -0.5
                         ELSE 0.0 END) as score,
                r.source,
                r.platform,
                coalesce(r.text_translated, r.text_original) as text,
                rt_agg.topics,
                e.sub_topics,
                e.issues,
                COALESCE(e.user_intent, 'Complaint') as user_intent,
                COALESCE(e.severity, 'Medium') as severity,
                COALESCE(e.product_area, 'UX') as product_area,
                coalesce(v.version_string, 'v9.0.2') as version
            FROM reviews_raw r
            LEFT JOIN reviews_enriched e ON r.id = e.review_id
            LEFT JOIN app_versions v ON r.app_version_id = v.id
            LEFT JOIN (
                SELECT review_id, json_agg(topic_id) as topics
                FROM review_topics
                GROUP BY review_id
            ) rt_agg ON r.id = rt_agg.review_id
            WHERE TRUE {run_filter}
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        cleaned = []
        for row in rows:
            topics_list = row.get("topics") or []
            if isinstance(topics_list, str):
                try:
                    topics_list = json.loads(topics_list)
                except Exception:
                    topics_list = []
            sub_topics_list = row.get("sub_topics") or []
            if isinstance(sub_topics_list, str):
                try:
                    sub_topics_list = json.loads(sub_topics_list)
                except Exception:
                    sub_topics_list = []
                    
            cleaned.append({
                "date": str(row["date"]),
                "rating": int(row["rating"] or 3),
                "sentiment": str(row["sentiment"] or "NEUTRAL"),
                "score": float(row["score"] or 0.0),
                "version": str(row["version"]),
                "platform": str(row["platform"] or "android"),
                "source": str(row["source"] or "playstore"),
                "topics": topics_list if isinstance(topics_list, list) else [],
                "sub_topics": sub_topics_list if isinstance(sub_topics_list, list) else [],
                "issues": row.get("issues") or [],
                "user_intent": row.get("user_intent") or "Complaint",
                "severity": row.get("severity") or "Medium",
                "product_area": row.get("product_area") or "UX",
                "emotional_tone": "Neutral",
                "text": str(row["text"])
            })
        
        # Return real data only — no fallback to mock after scraping
        return cleaned
    except Exception as e:
        print("Database query failed, falling back to mock dataset:", e)
        return ALL_REVIEWS

# =====================================================================
# FILTERING ENGINE
# =====================================================================
def filter_mock_reviews(date_range: str, version: str, rating: str, platform: str, search: str, topic: str = None) -> List[Dict]:
    filtered = []
    reviews_pool = get_all_reviews()
    
    # Calculate date limit
    limit_date = None
    today = datetime.now()
    if date_range == "7d":
        limit_date = today - timedelta(days=7)
    elif date_range == "30d":
        limit_date = today - timedelta(days=30)
    elif date_range == "90d":
        limit_date = today - timedelta(days=90)
        
    for r in reviews_pool:
        # Date Filter
        try:
            r_date = datetime.strptime(r["date"], "%Y-%m-%d")
        except ValueError:
            # Fallback for ISO timestamps
            try:
                r_date = datetime.fromisoformat(r["date"].replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                r_date = today
                
        if limit_date and r_date < limit_date:
            continue
            
        # Version Filter
        if version and version != "All" and r["version"] != version:
            continue
            
        # Rating Filter
        if rating and rating != "All":
            try:
                if r["rating"] != int(rating):
                    continue
            except Exception:
                continue
                
        # Platform Filter
        if platform and platform != "All" and r["platform"] != platform:
            continue
                
        # Topic Filter
        if topic and topic != "All" and topic not in r["topics"]:
            continue
            
        # Search Filter
        if search:
            query = search.lower()
            if query not in r["text"].lower():
                continue
                
        filtered.append(r)
        
    return filtered

# =====================================================================
# EXPORTED AGGREGATION HANDLERS
# =====================================================================
def get_stats_aggregated(date_range: str, version: str, rating: str, platform: str, search: str) -> Dict[str, Any]:
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    source = "database" if has_live_data() else "fallback_mock"
    
    total = len(filtered)
    if total == 0:
        return {
            "total_reviews": 0,
            "avg_sentiment": 0.0,
            "avg_rating": 0.0,
            "neg_this_month": 0,
            "sentiment_distribution": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
            "trend": [],
            "source_type": source,
            "source_counts": {},
        }
        
    avg_score = sum(r["score"] for r in filtered) / total
    avg_rating = sum(r["rating"] for r in filtered) / total
    neg_this_month = sum(1 for r in filtered if r["sentiment"] == "NEGATIVE" and r["date"].startswith("2026-06"))

    dist = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    source_counts: Dict[str, int] = {}
    for r in filtered:
        dist[r["sentiment"]] += 1
        s = r.get("source", "unknown")
        source_counts[s] = source_counts.get(s, 0) + 1
        
    dates_grouped = {}
    for r in filtered:
        dt = r["date"]
        if dt not in dates_grouped:
            dates_grouped[dt] = []
        dates_grouped[dt].append(r)
        
    trend = []
    for dt in sorted(dates_grouped.keys()):
        day_reviews = dates_grouped[dt]
        day_total = len(day_reviews)
        day_avg_sentiment = sum(dr["score"] for dr in day_reviews) / day_total
        day_avg_rating = sum(dr["rating"] for dr in day_reviews) / day_total
        
        trend.append({
            "date": dt,
            "avg_sentiment": round(day_avg_sentiment, 2),
            "avg_rating": round(day_avg_rating, 2),
            "is_release": RELEASE_DATES.get(dt)
        })
        
    return {
        "total_reviews": total,
        "avg_sentiment": round(avg_score, 2),
        "avg_rating": round(avg_rating, 2),
        "neg_this_month": neg_this_month,
        "sentiment_distribution": dist,
        "trend": trend,
        "source_type": source,
        "source_counts": source_counts,
    }

_COMPLAINT_SUMMARY_BLOCKLIST = [
    "too many ad", "excessive ad", "premium not worth", "not worth it",
    "playlist issues", "app crashes", "crash", "broken", "can't skip",
    "cannot skip", "overpriced", "too expensive", "restrictive",
]

_TOPIC_ISSUE_TERMS = {
    "search_discovery": [
        "discover", "discovery", "recommend", "recommendation", "recommendations",
        "algorithm", "search", "repetitive",
        "same songs", "release radar", "daily mix", "autoplay",
    ],
    "subscriptions_pricing": [
        "premium", "price", "pricing", "expensive", "overpriced", "subscription",
        "plan", "billing", "payment", "worth", "rates",
    ],
    "content_availability": [
        "content", "catalog", "missing", "unavailable", "not available", "region",
        "regional", "artist", "licensing",
    ],
    "playlists_library": [
        "playlist", "library", "liked", "queue", "shuffle", "skip", "play in order",
        "playback restrictions",
    ],
    "ads_experience": [
        "ad", "ads", "advertisement", "advertisements", "commercial", "sponsored",
        "upsell",
    ],
    "offline_mode": [
        "offline", "download", "downloaded", "cache", "no internet",
    ],
    "audio_quality": [
        "audio", "sound", "quality", "bitrate", "volume", "equalizer", "hifi",
        "lossless",
    ],
    "performance_crashes": [
        "crash", "crashes", "slow", "lag", "bug", "glitch", "freeze", "battery",
        "performance",
    ],
    "podcasts": [
        "podcast", "episode", "show", "audiobook",
    ],
    "ui_layout": [
        "ui", "layout", "interface", "design", "button", "navigation", "dark mode",
        "confusing",
    ],
    "social_sharing": [
        "share", "sharing", "friend", "group", "jam", "instagram", "social",
    ],
    "account_login": [
        "login", "sign in", "account", "password", "authentication", "oauth",
    ],
}

_PRAISE_ISSUE_TERMS = [
    "great", "excellent", "love", "loved", "good", "smooth", "better",
    "amazing", "perfect", "praise", "worth the money", "works well",
]


def _contains_topic_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _is_contradictory_issue_summary(summary: str | None) -> bool:
    if not summary:
        return False
    lowered = summary.lower()
    positive_frame = any(
        phrase in lowered for phrase in (
            "users appreciate", "users praise", "users like", "users love",
            "appreciate ", "praise ", "like "
        )
    )
    complaint_phrase = any(term in lowered for term in _COMPLAINT_SUMMARY_BLOCKLIST)
    return positive_frame and complaint_phrase


# Patterns that mark a stored summary as a basic rule-based template not worth showing
_LOW_QUALITY_PATTERNS = [
    "users report issues with",
    "mixed feedback with complaints about",
    "reviews mentioning this topic",
    "no dominant complaint pattern",
    "feedback is mostly positive",
]


def _is_low_quality_summary(summary: str | None) -> bool:
    """Returns True when the cached summary is a basic rule-based template with low analytical value."""
    if not summary:
        return True
    lowered = summary.lower()
    return any(pat in lowered for pat in _LOW_QUALITY_PATTERNS)


def _collect_topic_complaint_issues(topic_reviews: List[Dict], topic_id: str) -> tuple[Dict[str, int], List[Dict]]:
    complaint_reviews = [
        r for r in topic_reviews
        if r.get('sentiment') == 'NEGATIVE' or r.get('user_intent') == 'Complaint' or int(r.get('rating') or 3) <= 2
    ]
    issue_counts: Dict[str, int] = {}
    topic_terms = _TOPIC_ISSUE_TERMS.get(topic_id, [])
    for review in complaint_reviews:
        for issue in review.get('complaint_issues') or review.get('issues') or []:
            issue_text = str(issue).strip()
            if not issue_text:
                continue
            issue_lower = issue_text.lower()
            if any(term in issue_lower for term in _PRAISE_ISSUE_TERMS):
                continue
            if topic_terms and not any(_contains_topic_term(issue_lower, term) for term in topic_terms):
                continue
            issue_counts[issue_text] = issue_counts.get(issue_text, 0) + 1
    return issue_counts, complaint_reviews


def _build_core_issue_summary(topic_reviews: List[Dict], topic_id: str) -> str:
    issue_counts, complaint_reviews = _collect_topic_complaint_issues(topic_reviews, topic_id)

    total = len(topic_reviews)
    neg_count = sum(1 for r in topic_reviews if r.get('sentiment') == 'NEGATIVE')
    pos_count = sum(1 for r in topic_reviews if r.get('sentiment') == 'POSITIVE')
    neg_pct = round((neg_count / total) * 100) if total else 0
    pos_pct = round((pos_count / total) * 100) if total else 0

    critical_count = sum(
        1 for r in complaint_reviews
        if r.get('severity') in ('Critical', 'High')
    )

    if not issue_counts:
        if pos_pct > 60 and neg_pct < 20:
            return f"Predominantly positive with no recurring complaint pattern ({pos_pct}% satisfied)."
        if neg_pct > 40:
            label = _get_topic_label(topic_id)
            return f"{neg_pct}% negative sentiment with no single dominant complaint identified."
        return "Mixed feedback without a consistent complaint pattern."

    sorted_issues = sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)
    top_issues = [issue for issue, _ in sorted_issues[:3]]

    issue_a = top_issues[0].capitalize()
    issue_b = top_issues[1] if len(top_issues) > 1 else None
    issue_c = top_issues[2] if len(top_issues) > 2 else None

    # Single dominant issue
    if len(top_issues) == 1:
        if critical_count > 0:
            return f"{issue_a} is the critical complaint driving the majority of negative feedback."
        return f"{issue_a} is the primary user complaint for this topic."

    # Two or more issues — vary the framing based on severity and sentiment
    if critical_count >= 2:
        return f"{issue_a} and {issue_b} are the critical pain points."
    if critical_count == 1:
        return f"{issue_a} (critical) and {issue_b} drive the majority of negative feedback."

    if neg_pct >= 65:
        if issue_c:
            return f"Overwhelming complaint pattern: {issue_a}, {issue_b}, and {issue_c}."
        return f"Strongly negative: {issue_a} and {issue_b} dominate feedback ({neg_pct}% dissatisfied)."
    if neg_pct >= 45:
        return f"{issue_a} and {issue_b} are the leading complaints ({neg_pct}% negative)."
    if neg_pct >= 25:
        return f"Mixed reception; recurring concerns include {issue_a} and {issue_b}."
    # Mostly positive with minor gripes
    return f"Generally positive; minor complaints around {issue_a} and {issue_b}."


def get_topics_matrix(date_range: str, version: str, rating: str, platform: str, search: str) -> List[Dict[str, Any]]:
    """Dynamically discovers topics from actual review data and returns top 10 + pinned search_discovery."""
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    
    # Step 1: Group reviews by topic
    topic_buckets: Dict[str, List[Dict]] = {}
    for r in filtered:
        for t in r.get('topics', []):
            if t not in topic_buckets:
                topic_buckets[t] = []
            topic_buckets[t].append(r)
    
    # Step 2: Build matrix rows for topics that actually have reviews
    matrix = []
    for topic_id, topic_reviews in topic_buckets.items():
        count = len(topic_reviews)
        if count == 0:
            continue
        
        avg_sent = sum(r['score'] for r in topic_reviews) / count
        pos_cnt = sum(1 for r in topic_reviews if r['sentiment'] == 'POSITIVE')
        neg_cnt = sum(1 for r in topic_reviews if r['sentiment'] == 'NEGATIVE')
        
        pct_pos = round((pos_cnt / count) * 100)
        pct_neg = round((neg_cnt / count) * 100)
        
        # Priority: Phase 3 DB summary (if high quality) → live LLM → rule-based
        cached_summary = _get_phase3_summary(topic_id)
        if (cached_summary
                and not _is_contradictory_issue_summary(cached_summary)
                and not _is_low_quality_summary(cached_summary)):
            summary = cached_summary
        else:
            # Try live LLM call (returns None on failure or no negatives)
            llm_summary = _auto_summarize_topic(topic_reviews, topic_id)
            summary = llm_summary if llm_summary else _build_core_issue_summary(topic_reviews, topic_id)

        # Count distinct sub-topics that appear in reviews for this topic,
        # restricted to sub-topics actually defined for this topic in the taxonomy.
        from nlp.topics.tagger import HierarchicalTopicTagger
        try:
            _htagger = HierarchicalTopicTagger()
            _valid = set(_htagger.get_subtopics_for(topic_id))
        except Exception:
            _valid = set()
        sub_names = set()
        for r in topic_reviews:
            for s in (r.get('sub_topics') or []):
                if s and (not _valid or s in _valid):
                    sub_names.add(s)

        matrix.append({
            'id': topic_id,
            'label': _get_topic_label(topic_id),
            'reviews_count': count,
            'avg_sentiment': round(avg_sent, 2),
            'pct_positive': pct_pos,
            'pct_negative': pct_neg,
            'trend': _compute_trend(topic_reviews),
            'summary': summary,
            'priority_index': 0 if topic_id == PINNED_TOPIC else 1,
            'subtopic_count': len(sub_names),
        })
    
    # Step 3: Sort by review count descending
    matrix.sort(key=lambda x: x['reviews_count'], reverse=True)
    
    # Step 4: Ensure search_discovery is always included
    pinned_ids = {r['id'] for r in matrix}
    if PINNED_TOPIC not in pinned_ids:
        # Add an empty pinned row
        matrix.insert(0, {
            'id': PINNED_TOPIC,
            'label': _get_topic_label(PINNED_TOPIC),
            'reviews_count': 0,
            'avg_sentiment': 0.0,
            'pct_positive': 0,
            'pct_negative': 0,
            'trend': '0% change',
            'summary': 'No discovery-related reviews found for current filters.',
            'priority_index': 0,
            'subtopic_count': 0,
        })
    
    # Step 5: Limit to top 10 (but always keep the pinned topic)
    top_10 = []
    pinned_row = None
    for row in matrix:
        if row['id'] == PINNED_TOPIC:
            pinned_row = row
        else:
            top_10.append(row)
    
    top_10 = top_10[:9]  # Leave room for the pinned topic
    
    # Put pinned topic first
    result = []
    if pinned_row:
        result.append(pinned_row)
    result.extend(top_10)
    
    return result

def get_top_keywords(date_range: str, version: str, rating: str, platform: str, search: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Phase 5 (enhanced): Returns top keywords found in positive vs negative reviews.
    Now prefers issue-based buzzwords from Phase 1 'issues' field when available,
    falling back to raw-text word extraction for backward compatibility.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Phase 5: Check if reviews have issue data; if so, use issue-based buzzwords
    has_issues = any(r.get('issues') for r in filtered)

    if has_issues:
        from nlp.keywords import extract_frustration_keywords, extract_praise_keywords
        neg_sorted = extract_frustration_keywords(filtered, top_n=10)
        pos_sorted = extract_praise_keywords(filtered, top_n=10)
        # Normalize to the old {text, value} format for backward compat
        return {
            "positive": [{"text": b['text'], "value": b['count']} for b in pos_sorted] or [{"text": "great", "value": 1}],
            "negative": [{"text": b['text'], "value": b['count']} for b in neg_sorted] or [{"text": "issue", "value": 1}],
        }

    # Fallback: old regex-based word extraction
    stop_words = {
        # Articles / prepositions / conjunctions
        "the","and","a","an","of","to","is","in","it","i","this","my","app","for",
        "with","on","are","but","so","have","not","too","they","was","be","as","at",
        "by","from","or","an","if","its","that","into","than","then","there","these",
        "their","will","can","just","also","now","any","all","about","has","been",
        "would","could","should","does","did","do","get","got","like","very","more",
        "when","which","who","what","how","because","been","had","him","her","his",
        "she","he","we","you","your","our","us","me","up","out","no","yes","only",
        "even","over","after","before","use","used","using","make","made","way",
        "well","want","need","really","still","here","much","every","being","same",
        "some","one","two","three","time","day","year","new","old","good","great",
        "best","love","hate","nice","bad","poor","worst","ever","amazing","awesome",
        "terrible","horrible","perfect","wonderful","excellent","fantastic","okay",
        "ok","yeah","yes","please","thank","thanks","try","tried","since","while",
        "though","already","again","first","last","next","never","always","back",
        "long","little","bit","lot","many","most","per","other","another","each",
        "few","big","small","high","low","come","came","go","went","see","seen",
        "know","think","feel","felt","say","said","tell","told","give","gave",
        "take","took","find","found","keep","kept","let","call","put","run",
        "update","updated","version","yeu","hai","kar","nahi","bhi","kya","koi",
        "aur","toh","hum","tha","thi","woh","iss","par","bhai","ek","apna",
    }
    
    pos_words = {}
    neg_words = {}
    
    for r in filtered:
        words = re.findall(r'\b\w+\b', r["text"].lower())
        for w in words:
            if len(w) <= 3 or w in stop_words:
                continue
            if r["sentiment"] == "POSITIVE":
                pos_words[w] = pos_words.get(w, 0) + 1
            elif r["sentiment"] == "NEGATIVE":
                neg_words[w] = neg_words.get(w, 0) + 1
                
    pos_sorted = [{"text": k, "value": v} for k, v in sorted(pos_words.items(), key=lambda x: x[1], reverse=True)[:10]]
    neg_sorted = [{"text": k, "value": v} for k, v in sorted(neg_words.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    if not pos_sorted:
        pos_sorted = [{"text": "great", "value": 15}, {"text": "love", "value": 12}, {"text": "recommendations", "value": 8}, {"text": "playlists", "value": 7}, {"text": "best", "value": 5}]
    if not neg_sorted:
        neg_sorted = [{"text": "crashing", "value": 18}, {"text": "broken", "value": 14}, {"text": "repetitive", "value": 11}, {"text": "ads", "value": 10}, {"text": "slow", "value": 9}]
        
    return {
        "positive": pos_sorted,
        "negative": neg_sorted
    }

def get_anomaly_alerts(date_range: str, version: str, rating: str, platform: str, search: str) -> List[Dict[str, str]]:
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    alerts = []
    
    if not filtered:
        return [{"id": "alert-1", "severity": "INFO", "message": "No data available to detect anomalies.", "time": "Just now"}]
        
    total = len(filtered)
    neg_reviews = [r for r in filtered if r.get('sentiment') == 'NEGATIVE']
    neg_pct = (len(neg_reviews) / total) * 100
    
    # Alert 1: Overall Sentiment Spike
    if neg_pct > 35:
        alerts.append({
            "id": "alert-1",
            "severity": "CRITICAL",
            "message": f"Critical sentiment drop: {neg_pct:.1f}% of reviews in the current filter are negative.",
            "time": "Active"
        })
    elif neg_pct < 15:
        alerts.append({
            "id": "alert-1",
            "severity": "INFO",
            "message": f"Positive trend: Only {neg_pct:.1f}% of reviews are negative.",
            "time": "Active"
        })
        
    # Alert 2: Most problematic topic
    topic_counts = {}
    for r in neg_reviews:
        for t in r.get('topics', []):
            topic_counts[t] = topic_counts.get(t, 0) + 1
            
    if topic_counts:
        top_topic = max(topic_counts, key=topic_counts.get)
        top_topic_count = topic_counts[top_topic]
        if top_topic_count > (len(neg_reviews) * 0.3): # if > 30% of negatives are about one topic
            alerts.append({
                "id": "alert-2",
                "severity": "WARNING",
                "message": f"Spike detected: High volume of complaints regarding '{top_topic.replace('_', ' ')}' ({top_topic_count} recent reviews).",
                "time": "Active"
            })
            
    # Alert 3: Version specific (if not filtered by version)
    if version == "All":
        version_scores = {}
        for r in filtered:
            v = r.get('version', 'Unknown')
            if v not in version_scores:
                version_scores[v] = []
            version_scores[v].append(r.get('score', 0))
            
        for v, scores in version_scores.items():
            if len(scores) > 5:
                avg = sum(scores) / len(scores)
                if avg < -0.4:
                    alerts.append({
                        "id": f"alert-ver-{v}",
                        "severity": "CRITICAL",
                        "message": f"Severe performance on version {v}: Average sentiment score is deeply negative ({avg:.2f}).",
                        "time": "Active"
                    })
                    break
                    
    if not alerts:
        alerts.append({
            "id": "alert-ok",
            "severity": "INFO",
            "message": "Metrics look stable. No major anomalies detected in this batch.",
            "time": "Active"
        })
        
    return alerts[:3] # Return top 3 alerts

def get_reviews_list(date_range: str, version: str, rating: str, platform: str, search: str, topic: str = None, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    filtered = filter_mock_reviews(date_range, version, rating, platform, search, topic=topic)
    filtered.sort(key=lambda x: x["date"], reverse=True)
    
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "reviews": filtered[start:end]
    }

# =====================================================================
# PHASE 2: SUB-TOPIC DRILL-DOWN AGGREGATION
# =====================================================================
def get_subtopics_for_topic(topic_id: str, date_range: str = "All", version: str = "All",
                            rating: str = "All", platform: str = "All", search: str = "") -> Dict[str, Any]:
    """
    Phase 2: Returns sub-topic drill-down stats for a given parent topic.
    Each sub-topic row includes review count, avg sentiment, and pct negative.
    Works in both live DB and mock fallback modes.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Load taxonomy so we can restrict sub-topics to only those that actually
    # belong to this parent topic. Reviews tagged to multiple topics carry
    # sub-topics from all of them; we must filter to avoid cross-contamination.
    from nlp.topics.tagger import HierarchicalTopicTagger
    try:
        htagger = HierarchicalTopicTagger()
        valid_subs: set = set(htagger.get_subtopics_for(topic_id))
    except Exception:
        htagger = None
        valid_subs = set()

    # Filter to only reviews tagged with this topic
    topic_reviews = [r for r in filtered if topic_id in r.get('topics', [])]

    # Group by sub_topic — only count sub-topics that belong to this topic
    subtopic_buckets: Dict[str, List[Dict]] = {}
    untagged_reviews = []
    for r in topic_reviews:
        subs = [s for s in (r.get('sub_topics') or []) if s in valid_subs]
        if not subs:
            untagged_reviews.append(r)
        else:
            for sub in subs:
                subtopic_buckets.setdefault(sub, []).append(r)

    # Build response rows
    rows = []
    for sub_name, sub_reviews in subtopic_buckets.items():
        count = len(sub_reviews)
        avg_sent = sum(r['score'] for r in sub_reviews) / count if count else 0.0
        neg_cnt = sum(1 for r in sub_reviews if r['sentiment'] == 'NEGATIVE')
        pct_neg = round((neg_cnt / count) * 100) if count else 0
        rows.append({
            'sub_topic': sub_name,
            'reviews_count': count,
            'avg_sentiment': round(avg_sent, 2),
            'pct_negative': pct_neg,
        })

    # Sort by review count descending
    rows.sort(key=lambda x: x['reviews_count'], reverse=True)

    # Pad with taxonomy-defined sub-topics that had 0 matching reviews
    try:
        defined_subs = htagger.get_subtopics_for(topic_id) if htagger else []
        existing_names = {r['sub_topic'] for r in rows}
        for sub in defined_subs:
            if sub not in existing_names:
                rows.append({
                    'sub_topic': sub,
                    'reviews_count': 0,
                    'avg_sentiment': 0.0,
                    'pct_negative': 0,
                })
    except Exception:
        pass  # Taxonomy file not available; skip defined subtopics

    return {
        'topic_id': topic_id,
        'topic_label': _get_topic_label(topic_id),
        'total_reviews': len(topic_reviews),
        'subtopics': rows,
    }

# =====================================================================
# PHASE 3: TOPIC SUMMARY AGGREGATION
# =====================================================================

# Pre-computed mock summaries for offline development (Phase 3)
_MOCK_TOPIC_SUMMARIES = {
    "search_discovery": (
        "Discover Weekly praised for relevance but criticised for repetitive suggestions and lack of "
        "niche-genre variety, limiting algorithmic trust among indie music listeners."
    ),
    "playlists_library": (
        "Library layout changes confused users; custom playlists disappearing after updates is the "
        "top-critical issue, while collaborative features receive consistent praise."
    ),
    "offline_mode": (
        "Offline download reliability is the primary pain-point; users report tracks auto-deleting "
        "and cache corruption after app updates, undermining commute and travel use-cases."
    ),
    "ui_layout": (
        "v9 redesign triggered widespread negative feedback on dark mode readability and button "
        "placement, though long-term users gradually adapt to the new navigation patterns."
    ),
    "performance_crashes": (
        "v9.0.2 startup crashes dominate complaints; scroll lag and battery drain on mid-range "
        "Android devices signal a regression from the previously lightweight performance profile."
    ),
    "subscriptions_pricing": (
        "Family plan price hike perceived as poor value; student discount and UPI payment praised "
        "as accessible, but premium upsell popups irritate free-tier users."
    ),
    "content_availability": (
        "Regional content gaps and licensing-driven artist absences push Indian users toward YouTube "
        "Music; podcast exclusives partially offset catalog shortcomings."
    ),
    "social_sharing": (
        "Group Session / Jam feature well-received for live sharing; Instagram story integration "
        "fails intermittently, reducing social virality on India's dominant platform."
    ),
    "podcasts": (
        "Music-first users resent podcast clutter on the homepage; dedicated podcast listeners praise "
        "video support and episode discovery, indicating a segmentation opportunity."
    ),
    "ads_experience": (
        "Excessive ad frequency and unskippable interruptions drive free-tier frustration; loudness "
        "mismatch between ads and music is a recurring sensory complaint."
    ),
    "account_login": (
        "UPI authentication failures and delayed two-factor emails block onboarding for Indian users; "
        "password reset flow adds friction rather than reducing it."
    ),
    "audio_quality": (
        "Lossless/HiFi absence remains the most cited competitive gap vs Apple Music; equalizer and "
        "crossfade features praised by power users but under-discovered by casual listeners."
    ),
}

_TOPIC_ACTION_HINTS = {
    "ads_experience": "Review free-tier ad frequency, interruption timing, and premium upsell placement before tuning creative quality.",
    "subscriptions_pricing": "Separate price sensitivity from payment friction; test clearer plan value messaging and region-specific affordability checks.",
    "playlists_library": "Prioritize workflows that block listening continuity: queue control, playlist recovery, liked-song access, and shuffle/order restrictions.",
    "search_discovery": "Audit recommendation freshness and relevance by cohort, especially repeated tracks, language mismatch, and weak long-tail discovery.",
    "content_availability": "Quantify missing catalog demand by region/artist and separate licensing gaps from search/discovery failures.",
    "offline_mode": "Focus on reliability under no-network conditions: downloaded-track persistence, cache integrity, and offline playback state.",
    "audio_quality": "Separate genuine playback-quality complaints from positive sound-quality mentions in otherwise negative monetization reviews.",
    "performance_crashes": "Treat crashes, lag, and battery drain as release-quality regressions; segment by app version and device class.",
    "podcasts": "Distinguish podcast clutter for music-first users from podcast feature requests to avoid optimizing for the wrong segment.",
    "ui_layout": "Look for repeated navigation blockers rather than cosmetic dislike; prioritize tasks users can no longer complete quickly.",
}


def _build_hierarchy_insight_summary(topic_reviews: List[Dict], topic_id: str) -> Dict[str, Any]:
    label = _get_topic_label(topic_id)
    total = len(topic_reviews)
    if total == 0:
        return {
            "summary": f"No {label.lower()} reviews match the current filters.",
            "dominant_issues": [],
            "sentiment_distribution": {"positive": 0.0, "negative": 0.0, "neutral": 0.0},
            "insights": [],
        }

    pos = sum(1 for r in topic_reviews if r.get('sentiment') == 'POSITIVE')
    neg = sum(1 for r in topic_reviews if r.get('sentiment') == 'NEGATIVE')
    neu = total - pos - neg
    neg_pct = round((neg / total) * 100)
    pos_pct = round((pos / total) * 100)

    issue_counts, complaint_reviews = _collect_topic_complaint_issues(topic_reviews, topic_id)
    ranked = sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)
    top_issues = [{"issue": issue, "count": count} for issue, count in ranked[:5]]

    if top_issues:
        issue_phrase = ", ".join(item["issue"] for item in top_issues[:3])
        severity_counts: Dict[str, int] = {}
        for review in complaint_reviews:
            sev = review.get("severity") or "Medium"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        dominant_severity = max(severity_counts, key=severity_counts.get) if severity_counts else "Medium"
        summary = (
            f"{label} complaints concentrate around {issue_phrase}. "
            f"{neg_pct}% of {total} matching reviews are negative, with {dominant_severity.lower()} severity most common among complaint rows. "
            f"{_TOPIC_ACTION_HINTS.get(topic_id, 'Prioritize the repeated complaint themes before reading individual reviews.')}"
        )
    elif neg_pct >= 35:
        summary = (
            f"{label} has {neg_pct}% negative sentiment, but the current extraction does not reveal a single repeated complaint phrase. "
            "Use the sub-topic split and drill-down reviews to identify whether this is fragmented feedback or a taxonomy gap."
        )
    else:
        summary = (
            f"{label} does not show a dominant complaint pattern in the current filters. "
            f"Positive sentiment is {pos_pct}%, so treat this as monitoring context unless a sub-topic shows a sharper negative pocket."
        )

    insights = []
    if top_issues:
        insights.append(f"Top issue: {top_issues[0]['issue']} ({top_issues[0]['count']} mentions)")
    if neg_pct >= 45:
        insights.append(f"High negative concentration: {neg_pct}% negative")
    elif neg_pct >= 30:
        insights.append(f"Moderate negative concentration: {neg_pct}% negative")
    if len(top_issues) >= 3:
        insights.append("Complaint pattern is multi-cause, not a single isolated defect")

    return {
        "summary": summary,
        "dominant_issues": top_issues,
        "sentiment_distribution": {
            "positive": round(pos / total, 2),
            "negative": round(neg / total, 2),
            "neutral": round(neu / total, 2),
        },
        "insights": insights,
    }


def get_topic_summary(topic_id: str, date_range: str = "All", version: str = "All",
                      rating: str = "All", platform: str = "All", search: str = "") -> Dict[str, Any]:
    """
    Returns a filter-aware, drill-down summary for Topic Hierarchy Explorer.
    This is intentionally more detailed than the matrix row summary.
    """
    label = _get_topic_label(topic_id)
    filtered = filter_mock_reviews(date_range, version, rating, platform, search, topic=topic_id)
    insight = _build_hierarchy_insight_summary(filtered, topic_id)
    return {
        'topic_id': topic_id,
        'topic_label': label,
        'summary': insight['summary'],
        'review_count': len(filtered),
        'sentiment_distribution': insight['sentiment_distribution'],
        'dominant_issues': insight['dominant_issues'],
        'insights': insight['insights'],
        'generated_at': None,
        'source': 'live_filter_aggregation' if has_live_data() else 'mock_filter_aggregation',
    }

# =====================================================================
# PHASE 4: INTENT, SEVERITY & PRIORITY AGGREGATION
# =====================================================================

def get_intent_distribution(date_range: str = "All", version: str = "All",
                           rating: str = "All", platform: str = "All",
                           search: str = "") -> Dict[str, Any]:
    """
    Phase 4: Returns distribution of user intents across filtered reviews.
    Output: {"Complaint": 45, "Praise": 30, "Question": 15, "Suggestion": 10}
    Also includes a breakdown by topic.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    total = len(filtered) or 1

    # Global distribution
    intent_counts: Dict[str, int] = {"Complaint": 0, "Praise": 0, "Question": 0, "Suggestion": 0}
    for r in filtered:
        intent = r.get('user_intent', 'Complaint')
        if intent in intent_counts:
            intent_counts[intent] += 1
        else:
            intent_counts[intent] = 1

    # By-topic breakdown
    by_topic: Dict[str, Dict[str, int]] = {}
    for r in filtered:
        intent = r.get('user_intent', 'Complaint')
        for t in r.get('topics', []):
            if t not in by_topic:
                by_topic[t] = {"Complaint": 0, "Praise": 0, "Question": 0, "Suggestion": 0}
            by_topic[t][intent] = by_topic[t].get(intent, 0) + 1

    # Emotional tone distribution
    tone_counts: Dict[str, int] = {}
    for r in filtered:
        tone = r.get('emotional_tone', 'Neutral')
        tone_counts[tone] = tone_counts.get(tone, 0) + 1

    return {
        'total_reviews': len(filtered),
        'intent_distribution': intent_counts,
        'intent_percentages': {
            k: round((v / total) * 100, 1) for k, v in intent_counts.items()
        },
        'emotional_tone_distribution': tone_counts,
        'by_topic': by_topic,
        'source': 'database' if has_live_data() else 'mock',
    }


def get_severity_breakdown(date_range: str = "All", version: str = "All",
                          rating: str = "All", platform: str = "All",
                          search: str = "") -> Dict[str, Any]:
    """
    Phase 4: Returns severity distribution overall and by topic.
    Output: {"Critical": 10, "High": 25, "Medium": 40, "Low": 25}
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    total = len(filtered) or 1

    # Global distribution
    sev_counts: Dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for r in filtered:
        sev = r.get('severity', 'Medium')
        if sev in sev_counts:
            sev_counts[sev] += 1
        else:
            sev_counts[sev] = 1

    # By-topic severity
    by_topic: Dict[str, Dict[str, int]] = {}
    for r in filtered:
        sev = r.get('severity', 'Medium')
        for t in r.get('topics', []):
            if t not in by_topic:
                by_topic[t] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
            by_topic[t][sev] = by_topic[t].get(sev, 0) + 1

    # Severity + sentiment cross-tab
    cross_tab: Dict[str, Dict[str, int]] = {}
    for r in filtered:
        sev = r.get('severity', 'Medium')
        sent = r.get('sentiment', 'NEUTRAL')
        if sev not in cross_tab:
            cross_tab[sev] = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
        cross_tab[sev][sent] = cross_tab[sev].get(sent, 0) + 1

    # Weighted severity score
    from nlp.sentiment.analyzer import SEVERITY_WEIGHTS
    weighted_score = 0.0
    for r in filtered:
        sev = r.get('severity', 'Medium')
        weighted_score += SEVERITY_WEIGHTS.get(sev, 1.0)
    avg_weighted = round(weighted_score / total, 2)

    return {
        'total_reviews': len(filtered),
        'severity_distribution': sev_counts,
        'severity_percentages': {
            k: round((v / total) * 100, 1) for k, v in sev_counts.items()
        },
        'by_topic': by_topic,
        'severity_sentiment_crosstab': cross_tab,
        'avg_weighted_severity': avg_weighted,
        'source': 'database' if has_live_data() else 'mock',
    }


def get_priority_issues(date_range: str = "All", version: str = "All",
                       rating: str = "All", platform: str = "All",
                       search: str = "", limit: int = 10) -> Dict[str, Any]:
    """
    Phase 4: Returns top priority issues based on severity + volume + sentiment.
    Priority score = severity_weight * sentiment_amplifier * volume_multiplier.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT unnest(re.issues) as issue,
                       COUNT(*) as volume,
                       MODE() WITHIN GROUP (ORDER BY re.severity) as dominant_severity,
                       MODE() WITHIN GROUP (ORDER BY re.sentiment_label) as dominant_sentiment
                FROM reviews_enriched re
                WHERE re.issues IS NOT NULL
                {_mode_run_filter_re()}
                GROUP BY issue
                ORDER BY volume DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            from nlp.sentiment.analyzer import compute_priority_score
            results = []
            for row in rows:
                score = compute_priority_score(
                    row.get('dominant_sentiment', 'NEUTRAL'),
                    row.get('dominant_severity', 'Medium'),
                    row['volume']
                )
                results.append({
                    'issue': row['issue'],
                    'volume': row['volume'],
                    'severity': row.get('dominant_severity', 'Medium'),
                    'sentiment': row.get('dominant_sentiment', 'NEUTRAL'),
                    'priority_score': score,
                })
            results.sort(key=lambda x: x['priority_score'], reverse=True)
            return {
                'issues': results[:limit],
                'total_issues_analyzed': len(results),
                'source': 'database',
            }
        except Exception:
            pass

    # Fallback: use in-memory compute_priority_issues
    from nlp.sentiment.analyzer import compute_priority_issues
    results = compute_priority_issues(filtered, top_n=limit)
    return {
        'issues': results,
        'total_issues_analyzed': len(results),
        'source': 'database' if has_live_data() else 'mock',
    }


# =====================================================================
# PHASE 5: INTELLIGENT BUZZWORD EXTRACTION
# =====================================================================

def get_frustration_cloud(date_range: str = "All", version: str = "All",
                         rating: str = "All", platform: str = "All",
                         search: str = "", limit: int = 20) -> Dict[str, Any]:
    """
    Phase 5: Returns top frustration buzzwords from negative/high-severity reviews.
    Buzzwords are extracted from structured issues (not raw text adjectives).
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT unnest(issues) as issue, COUNT(*) as count
                FROM reviews_enriched
                WHERE sentiment_label = 'NEGATIVE'
                  AND severity IN ('High', 'Critical')
                  AND issues IS NOT NULL
                GROUP BY issue
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if rows:
                buzzwords = [
                    {'text': row['issue'], 'count': row['count'], 'sentiment': 'Negative'}
                    for row in rows
                ]
                return {
                    'buzzwords': buzzwords,
                    'total_issues': sum(b['count'] for b in buzzwords),
                    'source': 'database',
                }
        except Exception:
            pass

    # Fallback: use in-memory extractor
    from nlp.keywords import extract_frustration_keywords
    buzzwords = extract_frustration_keywords(filtered, top_n=limit)
    return {
        'buzzwords': buzzwords,
        'total_issues': sum(b['count'] for b in buzzwords),
        'source': 'database' if has_live_data() else 'mock',
    }


def get_positive_buzzwords(date_range: str = "All", version: str = "All",
                          rating: str = "All", platform: str = "All",
                          search: str = "", limit: int = 20) -> Dict[str, Any]:
    """
    Phase 5: Returns top positive buzzwords from positive reviews.
    Buzzwords are extracted from structured issues/praise (not raw text adjectives).
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT unnest(issues) as issue, COUNT(*) as count
                FROM reviews_enriched
                WHERE sentiment_label = 'POSITIVE'
                  AND issues IS NOT NULL
                GROUP BY issue
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if rows:
                buzzwords = [
                    {'text': row['issue'], 'count': row['count'], 'sentiment': 'Positive'}
                    for row in rows
                ]
                return {
                    'buzzwords': buzzwords,
                    'total_issues': sum(b['count'] for b in buzzwords),
                    'source': 'database',
                }
        except Exception:
            pass

    # Fallback: use in-memory extractor
    from nlp.keywords import extract_praise_keywords
    buzzwords = extract_praise_keywords(filtered, top_n=limit)
    return {
        'buzzwords': buzzwords,
        'total_issues': sum(b['count'] for b in buzzwords),
        'source': 'database' if has_live_data() else 'mock',
    }


def get_raw_csv_string(date_range: str = "All", version: str = "All", rating: str = "All", platform: str = "All", search: str = "") -> str:
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)
    lines = ["date,rating,sentiment,score,version,platform,source,text"]
    for r in filtered:
        safe_text = r["text"].replace('"', '""')
        lines.append(f"{r['date']},{r['rating']},{r['sentiment']},{r['score']},{r['version']},{r['platform']},{r['source']},\"{safe_text}\"")
    return "\n".join(lines)


# =====================================================================
# PHASE 6: CLUSTERING & TREND ANALYSIS
# =====================================================================

def get_issue_clusters(date_range: str = "All", version: str = "All",
                       rating: str = "All", platform: str = "All",
                       search: str = "") -> Dict[str, Any]:
    """
    Phase 6: Returns clustered issues with volume and sentiment distribution.
    Uses keyword-overlap agglomerative clustering on issue data.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT re.issues, re.sentiment_label, re.severity
                FROM reviews_enriched re
                WHERE re.issues IS NOT NULL
                {_mode_run_filter_re()}
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if rows:
                db_reviews = [
                    {'issues': row['issues'], 'sentiment': row['sentiment_label'], 'severity': row.get('severity', 'Medium')}
                    for row in rows
                ]
                from aggregation.clustering import IssueClusterer
                result = IssueClusterer().cluster_issues(db_reviews)
                result['source'] = 'database'
                return result
        except Exception:
            pass

    # Fallback: in-memory clustering
    from aggregation.clustering import IssueClusterer
    result = IssueClusterer().cluster_issues(filtered)
    result['source'] = 'database' if has_live_data() else 'mock'
    return result


def get_trends(date_range: str = "All", version: str = "All",
               rating: str = "All", platform: str = "All",
               search: str = "", lookback_days: int = 7) -> Dict[str, Any]:
    """
    Phase 6: Returns emerging/stable/declining issue trends.
    Compares current period vs previous period issue volumes.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        try:
            conn = get_connection()
            from aggregation.trends import TrendDetector
            result = TrendDetector().detect_trends_from_db(conn, lookback_days=lookback_days)
            conn.close()
            return result
        except Exception:
            pass

    # Fallback: in-memory trend detection
    from aggregation.trends import TrendDetector
    result = TrendDetector().detect_trends(filtered, lookback_days=lookback_days)
    result['source'] = 'database' if has_live_data() else 'mock'
    return result


def get_anomalies(date_range: str = "All", version: str = "All",
                  rating: str = "All", platform: str = "All",
                  search: str = "", window_days: int = 14) -> Dict[str, Any]:
    """
    Phase 6: Returns sentiment anomalies detected via z-score analysis.
    Flags unusual sentiment spikes/drops per topic.
    """
    filtered = filter_mock_reviews(date_range, version, rating, platform, search)

    # Try live DB first
    if has_live_data():
        conn = None
        try:
            conn = get_connection()
            from aggregation.anomalies import AnomalyDetector
            result = AnomalyDetector().detect_anomalies_from_db(
                conn, window_days=window_days,
                mode_filter=_mode_run_filter_re()
            )
            return result
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # Fallback: in-memory anomaly detection
    from aggregation.anomalies import AnomalyDetector
    result = AnomalyDetector().detect_anomalies(filtered, window_days=window_days)
    result['source'] = 'database' if has_live_data() else 'mock'
    return result


# =====================================================================
# PHASE 7: HYPOTHESIS GENERATION
# =====================================================================

def get_hypotheses(date_range: str = "All", version: str = "All",
                   rating: str = "All", platform: str = "All",
                   search: str = "") -> Dict[str, Any]:
    """
    Phase 7: Generates actionable product hypotheses from review intelligence.
    Feeds topic stats, priority issues, trends, and clusters to the HypothesisGenerator.
    Uses Groq LLM when available, falls back to rich mock hypotheses.
    Results are cached per (mode + filters) and cleared on mode switch or scrape.
    """
    cache_key = (_DATA_MODE, date_range, version, rating, platform, search)
    if cache_key in _hypotheses_cache:
        return _hypotheses_cache[cache_key]

    # Gather intelligence from existing Phase 4-6 functions
    stats = get_stats_aggregated(date_range, version, rating, platform, search)
    priority = get_priority_issues(date_range, version, rating, platform, search, limit=5)
    trends_result = get_trends(date_range, version, rating, platform, search, lookback_days=7)
    clusters_result = get_issue_clusters(date_range, version, rating, platform, search)

    top_issues = priority.get('issues', [])
    trends = trends_result.get('trends', [])
    clusters = clusters_result.get('clusters', [])

    total_reviews = stats.get('total_reviews', 0)
    if total_reviews == 0:
        return {
            'hypotheses': [],
            'intelligence_summary': {
                'total_reviews': 0,
                'priority_issues_count': 0,
                'trends_tracked': 0,
                'clusters_found': 0,
            },
            'source': 'none',
        }

    from nlp.hypothesis import HypothesisGenerator
    hypotheses = HypothesisGenerator().generate(
        topic_stats=stats,
        top_issues=top_issues,
        trends=trends,
        clusters=clusters,
        cache_key=cache_key,
    )

    # Check for error sentinel
    if hypotheses and hypotheses[0].get('_source') == 'error':
        return {
            'hypotheses': [],
            'intelligence_summary': {
                'total_reviews': stats.get('total_reviews', 0),
                'priority_issues_count': len(top_issues),
                'trends_tracked': trends_result.get('total_issues_tracked', 0),
                'clusters_found': len(clusters),
            },
            'source': 'error',
            'error': hypotheses[0].get('_error', 'LLM unavailable.'),
        }

    for h in hypotheses:
        h.pop('_source', None)

    result = {
        'hypotheses': hypotheses,
        'intelligence_summary': {
            'total_reviews': stats.get('total_reviews', 0),
            'priority_issues_count': len(top_issues),
            'trends_tracked': trends_result.get('total_issues_tracked', 0),
            'clusters_found': len(clusters),
        },
        'source': 'llm',
    }
    # Only cache successful LLM results
    _hypotheses_cache[cache_key] = result
    return result
