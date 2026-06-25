import json
import re
import time
from datetime import datetime, timezone
from typing import List

import requests

from .base import Review

_SPOTIFY_APP_ID = "324684580"
_SEE_ALL_URL = "https://apps.apple.com/{country}/app/spotify-music/id{app_id}?see-all=reviews"
_REQUEST_TIMEOUT = 20
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _extract_reviews_from_page(html: str) -> list[dict]:
    """Extract the pre-rendered review objects from Apple's SSR JSON blob."""
    for script_match in re.finditer(
        r"<script[^>]*>(.*?)</script>", html, re.DOTALL
    ):
        content = script_match.group(1).strip()
        if not (content.startswith('{"data":[{"intent"') and '"rating"' in content):
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue

        found: list[dict] = []

        def _walk(obj, depth=0):
            if depth > 25 or len(found) > 500:
                return
            if isinstance(obj, dict):
                if obj.get("$kind") == "Review" and "rating" in obj and "contents" in obj:
                    found.append(obj)
                    return
                for v in obj.values():
                    _walk(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item, depth + 1)

        _walk(data)
        if found:
            return found

    return []


def fetch_reviews(limit: int, country: str = "in") -> List[Review]:
    """
    Fetches App Store reviews from Apple's server-side rendered see-all page.
    Apple caps the pre-rendered batch at ~30 reviews; the pipeline's overflow
    logic fills the remainder from the Play Store.
    """
    country = country.lower()
    url = _SEE_ALL_URL.format(country=country, app_id=_SPOTIFY_APP_ID)
    print(f"Fetching App Store reviews from {url} ...")

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"App Store: request failed: {e}")
        return []

    raw = _extract_reviews_from_page(resp.text)
    if not raw:
        print("App Store: no reviews found in page — Apple may have changed page structure.")
        return []

    import hashlib as _hl

    parsed: List[Review] = []
    seen_ids: set = set()
    for entry in raw:
        if len(parsed) >= limit:
            break
        date_str = entry.get("date", "")
        created_at = None
        if date_str:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    created_at = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
        if created_at is None:
            created_at = datetime.now(timezone.utc)

        title = entry.get("title", "")
        body = entry.get("contents", "")
        full_text = f"{title}. {body}" if title and body else (body or title)

        # Deduplicate: Apple serves the same reviews across multiple shelf sections
        review_id = str(entry.get("id") or "").strip()
        if not review_id:
            review_id = _hl.md5(f"{full_text}{created_at.isoformat()}".encode()).hexdigest()
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)

        parsed.append(
            Review(
                platform_review_id=review_id,
                source="appstore",
                platform="ios",
                rating=int(entry.get("rating", 3)),
                text_original=full_text,
                created_at=created_at,
                country_code=country.upper(),
                app_version_string=entry.get("versionDisplay"),
                thumbs_up_count=0,
            )
        )

    print(f"App Store: fetched {len(parsed)} reviews.")
    return parsed
