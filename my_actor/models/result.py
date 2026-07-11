"""Standard result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FacebookItem:
    """A normalized Facebook content item."""

    content_type: str
    text: str = ""
    url: str = ""
    source_id: str = ""
    page_name: str = ""
    author: str = ""
    time: datetime | None = None
    likes: str = "0"
    comments_count: str = "0"
    shares: str = "0"
    has_photo: bool = False
    has_video: bool = False
    media: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_type": self.content_type,
            "text": self.text,
            "url": self.url,
            "source_id": self.source_id,
            "page_name": self.page_name,
            "author": self.author,
            "time": self.time.isoformat() if self.time else None,
            "likes": self.likes,
            "comments_count": self.comments_count,
            "shares": self.shares,
            "has_photo": self.has_photo,
            "has_video": self.has_video,
            "media": self.media,
            "source": self.source,
        }


@dataclass
class ActorOutput:
    """Top-level normalized output pushed to Apify dataset."""

    success: bool = True
    items: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    action: str = ""
    query: str = ""
    url: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "items": self.items,
            "count": self.count,
            "action": self.action,
            "query": self.query,
            "url": self.url,
            "message": self.message,
        }
