from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Review:
    platform_review_id: str
    source: str           # 'appstore', 'playstore'
    platform: str         # 'ios', 'android'
    rating: int           # 1-5
    text_original: str
    created_at: datetime
    country_code: str
    app_version_string: Optional[str] = None
    thumbs_up_count: int = 0
