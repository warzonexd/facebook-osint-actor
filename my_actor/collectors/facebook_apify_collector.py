"""Facebook collector using the Apify Facebook Posts Scraper actor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from my_actor.collectors.base import BaseCollector
from my_actor.utils.state import is_shutting_down


class FacebookApifyCollector(BaseCollector):
    """Facebook post collector using an upstream Apify actor."""

    ACTOR_ID = "apify/facebook-posts-scraper"

    def __init__(self, api_token: str | None = None, max_age_days: int = 7):
        self.api_token = api_token
        self.max_age_days = max_age_days

    async def collect(self, target: str, max_items: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]

        if not self.api_token:
            logger.warning("[FB Apify] No API token configured")
            return []

        try:
            from apify_client import ApifyClientAsync

            logger.info(f"[FB Apify] Scraping {page_name} via Apify...")
            client = ApifyClientAsync(self.api_token)

            run_input = {
                "startUrls": [{"url": f"https://www.facebook.com/{page_name}"}],
                "resultsLimit": min(max_items * 2, 50),
                "maxPostCount": max_items,
                "extractComments": False,
            }

            run = await client.actor(self.ACTOR_ID).call(run_input=run_input)
            dataset_id = run.default_dataset_id if hasattr(run, "default_dataset_id") else None
            if not dataset_id:
                logger.warning("[FB Apify] No dataset ID in run result")
                return []

            results = []
            async for item in client.dataset(dataset_id).iterate_items():
                if is_shutting_down():
                    break

                text = (item.get("text") or "").strip()
                if not text or len(text) < 30:
                    continue

                post_time = None
                timestamp = item.get("date") or item.get("timestamp") or item.get("createdAt")
                if timestamp:
                    try:
                        post_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        try:
                            ts = int(timestamp) if str(timestamp).isdigit() else 0
                            if ts > 0:
                                post_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                if self.max_age_days > 0 and post_time:
                    cutoff = datetime.now(timezone.utc).timestamp() - (self.max_age_days * 86400)
                    if post_time.timestamp() < cutoff:
                        continue

                post_url = item.get("url") or item.get("postUrl") or ""
                post_id = item.get("id") or item.get("postId") or ""

                results.append({
                    "text": text[:5000],
                    "post_url": post_url,
                    "post_id": str(post_id),
                    "content_type": "post",
                    "page_name": page_name,
                    "time": post_time or datetime.now(timezone.utc),
                    "likes": str(item.get("likesCount", item.get("likes", 0))),
                    "comments_count": str(item.get("commentsCount", item.get("comments", 0))),
                    "shares": str(item.get("sharesCount", item.get("shares", 0))),
                    "has_photo": bool(item.get("image") or item.get("images")),
                    "has_video": bool(item.get("video") or item.get("videos")),
                    "source": "apify",
                })

                if len(results) >= max_items:
                    break

            logger.info(f"[FB Apify] Got {len(results)} posts from {page_name}")
            return results

        except Exception as e:
            logger.error(f"[FB Apify] Error for {page_name}: {e}")
            return []
