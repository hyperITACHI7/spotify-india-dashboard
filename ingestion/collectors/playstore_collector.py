from google_play_scraper import reviews, Sort
from typing import List
from .base import Review

def fetch_reviews(limit: int, country: str = "in") -> List[Review]:
    """
    Fetches the most recent reviews from the Google Play Store.
    Note: The google-play-scraper's `reviews` function returns up to `count` reviews.
    """
    print(f"Fetching up to {limit} Google Play reviews for country '{country}'...")
    
    result, _ = reviews(
        'com.spotify.music',
        lang='en',
        country=country,
        sort=Sort.NEWEST,
        count=limit
    )
    
    parsed_reviews = []
    for r in result:
        parsed_reviews.append(Review(
            platform_review_id=r.get('reviewId'),
            source='playstore',
            platform='android',
            rating=r.get('score'),
            text_original=r.get('content', ''),
            created_at=r.get('at'),
            country_code=country.upper(),
            app_version_string=r.get('reviewCreatedVersion'),
            thumbs_up_count=r.get('thumbsUpCount', 0)
        ))
        
    print(f"Play Store: Fetched {len(parsed_reviews)} reviews.")
    return parsed_reviews
