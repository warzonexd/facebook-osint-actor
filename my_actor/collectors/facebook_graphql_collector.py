"""Facebook collector using direct HTTP + GraphQL with stored cookies."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger

from my_actor.collectors.base import BaseCollector
from my_actor.utils.helpers import cookie_list_to_dict, parse_cookies
from my_actor.utils.state import is_shutting_down


class FacebookGraphQLCollector(BaseCollector):
    """Facebook post collector using HTTP + GraphQL (no browser)."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        max_age_days: int = 7,
    ):
        self.cookies_json = cookies
        self.max_age_days = max_age_days
        self._cookie_dict: dict[str, str] = {}

    async def collect(self, target: str, max_items: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        cookies = parse_cookies(self.cookies_json)
        self._cookie_dict = cookie_list_to_dict(cookies)
        if not self._cookie_dict:
            logger.warning(f"[FB GraphQL] No cookies available for {page_name}")
            return []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Accept-Encoding": "gzip",
        }

        async with httpx.AsyncClient(
            cookies=self._cookie_dict,
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            posts = await self._fetch_posts(client, page_name, max_items)
            return posts

    async def _fetch_posts(self, client: httpx.AsyncClient, page_name: str, max_posts: int) -> list[dict[str, Any]]:
        base_url = f"https://www.facebook.com/{page_name}"
        logger.info(f"[FB GraphQL] Fetching {base_url}")

        resp = await client.get(base_url)
        final_url = str(resp.url)
        html = resp.text

        if "login" in final_url.lower():
            logger.warning(f"[FB GraphQL] Cookies expired — redirected to login for {page_name}")
            return []

        cutoff = None
        if self.max_age_days > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - (self.max_age_days * 86400)

        posts = await self._extract_posts_from_html(page_name, html, cutoff, max_posts)
        if posts:
            logger.info(f"[FB GraphQL] Extracted {len(posts)} posts from HTML for {page_name}")
            return posts

        posts = await self._extract_posts_via_graphql(client, page_name, html, cutoff, max_posts)
        if posts:
            logger.info(f"[FB GraphQL] Extracted {len(posts)} posts via GraphQL for {page_name}")
            return posts

        posts = await self._extract_posts_via_bs4(html, page_name, cutoff, max_posts)
        logger.info(f"[FB GraphQL] Extracted {len(posts)} posts via BS4 for {page_name}")
        return posts

    async def _extract_posts_from_html(
        self, page_name: str, html: str, cutoff: Optional[float], max_posts: int
    ) -> list[dict[str, Any]]:
        results = []
        candidates = []

        patterns = [
            r'<script[^>]*>\s*bigPipe\s*\.\s*onPageletArrive\s*\(([\s\S]*?)\)\s*;',
            r'<script[^>]*>\s*__PRELOADED_STATE__\s*=\s*({[\s\S]*?});\s*</script>',
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        ]

        import html as html_mod

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for m in matches:
                try:
                    decoded = html_mod.unescape(m)
                    data = json.loads(decoded)
                    candidates.append(data)
                except (json.JSONDecodeError, ValueError):
                    try:
                        data = json.loads(m)
                        candidates.append(data)
                    except (json.JSONDecodeError, ValueError):
                        pass

        seen_ids = set()
        for data in candidates:
            extracted = self._traverse_for_posts(data, page_name, cutoff)
            for post in extracted:
                pid = post.get("post_id", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(post)
                    if len(results) >= max_posts:
                        return results

        return results

    def _traverse_for_posts(
        self, obj: Any, page_name: str, cutoff: Optional[float], depth: int = 0
    ) -> list[dict[str, Any]]:
        if depth > 8:
            return []
        results = []

        if isinstance(obj, dict):
            typename = obj.get("__typename", "")
            if typename in ("Story", "FeedEdgeStory", "CometFeedStory", "StoryRender"):
                post = self._parse_story_node(obj, page_name, cutoff)
                if post:
                    results.append(post)
                    return results

            for key in ("node", "story", "edge", "post", "data", "comet_sections"):
                if key in obj:
                    results.extend(self._traverse_for_posts(obj[key], page_name, cutoff, depth + 1))

            for key, val in obj.items():
                if isinstance(val, (dict, list)) and not key.startswith("_"):
                    results.extend(self._traverse_for_posts(val, page_name, cutoff, depth + 1))

        elif isinstance(obj, list):
            for item in obj:
                results.extend(self._traverse_for_posts(item, page_name, cutoff, depth + 1))

        return results

    def _parse_story_node(self, node: dict, page_name: str, cutoff: Optional[float]) -> Optional[dict[str, Any]]:
        try:
            text = ""
            message = node.get("message") or node.get("text") or {}
            if isinstance(message, dict):
                text = message.get("text", "")
            elif isinstance(message, str):
                text = message

            if not text or len(text.strip()) < 30:
                return None

            post_id = str(node.get("post_id") or node.get("id") or node.get("story_id") or "")
            url = ""
            if post_id:
                url = f"https://www.facebook.com/{page_name}/posts/{post_id}"

            timestamp = None
            time_node = node.get("created_time") or node.get("publish_time") or node.get("scheduled_publish_time")
            if time_node:
                if isinstance(time_node, dict):
                    time_node = time_node.get("time", 0)
                try:
                    ts = int(time_node)
                    if ts > 10000000000:
                        ts = ts // 1000
                    timestamp = ts
                    if cutoff and ts < cutoff:
                        return None
                except (ValueError, TypeError):
                    pass

            feedback = node.get("feedback") or node.get("feedback_context") or {}
            if isinstance(feedback, dict):
                like_count = self._extract_count(feedback.get("likers") or feedback.get("like_count"))
                comment_count = self._extract_count(feedback.get("comment_count") or feedback.get("commenters"))
                share_count = self._extract_count(feedback.get("share_count"))
            else:
                like_count = 0
                comment_count = 0
                share_count = 0

            media = []
            attachments = node.get("attachments") or node.get("media") or []
            if isinstance(attachments, dict):
                attachment_list = attachments.get("nodes", []) if isinstance(attachments.get("nodes"), list) else [attachments]
            elif isinstance(attachments, list):
                attachment_list = attachments
            else:
                attachment_list = []

            has_photo = False
            has_video = False
            for att in attachment_list:
                if isinstance(att, dict):
                    media_type = att.get("media_type") or att.get("__typename", "")
                    if "video" in str(media_type).lower():
                        has_video = True
                        src = att.get("video", {}).get("playable_url", "") or att.get("src", "")
                        if src:
                            media.append({"type": "video", "src": src})
                    elif "photo" in str(media_type).lower() or "image" in str(media_type).lower():
                        has_photo = True
                        src = att.get("image", {}).get("src", "") or att.get("src", "")
                        if src:
                            media.append({"type": "photo", "src": src})

            return {
                "text": text.strip()[:5000],
                "post_url": url,
                "post_id": post_id,
                "content_type": "post",
                "page_name": page_name,
                "time": datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc),
                "likes": str(like_count),
                "comments_count": str(comment_count),
                "shares": str(share_count),
                "has_photo": has_photo,
                "has_video": has_video,
                "media": media,
                "source": "graphql_html",
            }
        except Exception as e:
            logger.debug(f"[FB GraphQL] Error parsing story node: {e}")
            return None

    @staticmethod
    def _extract_count(val: Any) -> int:
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, dict):
            return int(val.get("count", val.get("total_count", 0)))
        if isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                pass
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    async def _extract_posts_via_graphql(
        self, client: httpx.AsyncClient, page_name: str, html: str, cutoff: Optional[float], max_posts: int
    ) -> list[dict[str, Any]]:
        dtsg = self._extract_token(html, "fb_dtsg")
        lsd = self._extract_token(html, "lsd")
        user_id = self._extract_token(html, "userID", r'"userID"\s*:\s*"(\d+)"')

        if not dtsg:
            logger.debug("[FB GraphQL] No fb_dtsg token found for GraphQL request")
            return []

        user_id = user_id or "0"
        results = []

        doc_ids_to_try = [
            "4752143242563128",
            "6142226429531631",
            "5194993692135311",
            "3585742745117528",
        ]

        for doc_id in doc_ids_to_try:
            if len(results) >= max_posts:
                break

            variables = json.dumps({
                "pageID": page_name,
                "first": min(max_posts * 2, 20),
                "after": None,
                "renderSurface": "Covid19PagePosts",
            })

            data = {
                "av": user_id,
                "__user": user_id,
                "__a": "1",
                "__dyn": "",
                "__csr": "",
                "__req": "1",
                "__hs": "",
                "dpr": "2",
                "__ccg": "",
                "__s": "",
                "__hsi": "",
                "__comet_req": "0",
                "fb_dtsg": dtsg,
                "jazoest": "2",
                "lsd": lsd or "",
                "__spin_r": "",
                "__spin_b": "",
                "__spin_t": "",
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": "CometPagePostsQuery",
                "variables": variables,
                "doc_id": doc_id,
            }

            try:
                resp = await client.post(
                    "https://www.facebook.com/api/graphql/",
                    data=data,
                    timeout=httpx.Timeout(15.0),
                )
                body = resp.text
                if not body:
                    continue

                resp_data = json.loads(body.lstrip("for (;;);"))
                extracted = self._traverse_for_posts(resp_data, page_name, cutoff)
                results.extend(extracted)
                if results:
                    break
            except Exception as e:
                logger.debug(f"[FB GraphQL] doc_id {doc_id} failed: {e}")
                continue

        seen = set()
        deduped = []
        for p in results:
            pid = p.get("post_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                deduped.append(p)
        return deduped[:max_posts]

    async def _extract_posts_via_bs4(
        self, html: str, page_name: str, cutoff: Optional[float], max_posts: int
    ) -> list[dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        results = []
        soup = BeautifulSoup(html, "html.parser")

        article_tags = soup.find_all("div", role="article")
        if not article_tags:
            article_tags = soup.find_all("div", class_=re.compile(r"(post|story|feed)", re.I))

        for article in article_tags:
            text = article.get_text(strip=True)
            if len(text) < 30:
                continue
            text = text[:5000]

            links = article.find_all("a", href=re.compile(r"/posts/"))
            post_url = ""
            post_id = ""
            if links:
                href = links[0].get("href", "")
                post_url = f"https://www.facebook.com{href}" if href.startswith("/") else href
                pid_match = re.search(r"/posts/(\d+)", href)
                if pid_match:
                    post_id = pid_match.group(1)

            results.append({
                "text": text,
                "post_url": post_url or f"https://www.facebook.com/{page_name}",
                "post_id": post_id,
                "content_type": "post",
                "page_name": page_name,
                "time": datetime.now(timezone.utc),
                "likes": "0",
                "comments_count": "0",
                "shares": "0",
                "has_photo": bool(article.find("img")),
                "has_video": bool(article.find("video")),
                "media": [],
                "source": "bs4",
            })
            if len(results) >= max_posts:
                break

        return results

    @staticmethod
    def _extract_token(html: str, name: str, custom_pattern: Optional[str] = None) -> str:
        if custom_pattern:
            m = re.search(custom_pattern, html)
            if m:
                return m.group(1)
        pattern = rf'"name":"{re.escape(name)}","value":"([^"]+)"'
        m = re.search(pattern, html)
        if m:
            return m.group(1)
        pattern2 = rf'"name":"{re.escape(name)}"[^}}]*?"value"\s*:\s*"([^"]+)"'
        m = re.search(pattern2, html, re.DOTALL)
        return m.group(1) if m else ""
