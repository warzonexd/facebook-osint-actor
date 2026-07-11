"""Extract Facebook posts and comments from a rendered page."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from loguru import logger

from my_actor.facebook.selectors import UI_NOISE


def _is_ui_noise(text: str) -> bool:
    lower = text.lower()
    words = text.split()
    if len(words) <= 3:
        return True
    for kw in UI_NOISE:
        if kw in lower and len(text) < 100:
            return True
    return False


def _clean_text(text: str) -> str:
    text = " ".join(text.split())
    text = re.sub(r"\d+:\d+", "", text)
    text = re.sub(r"0:00", "", text)
    return text.strip()


EXTRACT_FULL_JS = r"""
() => {
    const results = [];
    const seen = new Set();

    let containers = document.querySelectorAll(
        'div[data-pagelet^="FeedUnit"], div[data-pagelet^="MinimalFeedUnit"]'
    );
    if (containers.length === 0) {
        containers = document.querySelectorAll('[role="article"]');
    }
    if (containers.length === 0) {
        containers = document.querySelectorAll('.x1yztbdb, .x1n2onr6 > div, [aria-posinset]');
    }

    for (const container of containers) {
        const textEls = container.querySelectorAll('[dir="auto"]');
        let bestText = '';
        for (const el of textEls) {
            const t = el.textContent.trim();
            if (t.length > 40 && !seen.has(t)) {
                if (t.length > bestText.length) bestText = t;
            }
        }

        if (!bestText) {
            const altEls = container.querySelectorAll(
                '.xdj266r, .x1heor9g, .x193iq5w, .x1lliihq, [data-ad-preview="message"]'
            );
            for (const el of altEls) {
                const t = el.textContent.trim();
                if (t.length > 50 && !seen.has(t)) {
                    if (t.length > bestText.length) bestText = t;
                }
            }
        }

        if (!bestText) continue;
        seen.add(bestText);

        let postUrl = '';
        const linkSelectors = [
            'a[href*="/posts/"]', 'a[href*="/photos/"]', 'a[href*="/videos/"]',
            'a[href*="/story.php"]', 'a[href*="/permalink/"]',
            'a[href*="?story_fbid"]', 'a[href*="?__xts__"]',
        ];
        for (const sel of linkSelectors) {
            const links = container.querySelectorAll(sel);
            for (const link of links) {
                const href = link.getAttribute('href') || '';
                if (href && href.length > 15) {
                    postUrl = href.startsWith('http') ? href : 'https://www.facebook.com' + href;
                    break;
                }
            }
            if (postUrl) break;
        }

        let postId = '';
        const idMatch = postUrl.match(/\/posts\/(\d+)/) || postUrl.match(/story_fbid=(\d+)/);
        if (idMatch) postId = idMatch[1];

        let timestamp = 0;
        let timestampText = '';
        const abbr = container.querySelector('abbr[data-utime]');
        if (abbr) {
            timestamp = parseInt(abbr.getAttribute('data-utime'), 10) * 1000;
            timestampText = abbr.getAttribute('data-shorten') ? '' : (abbr.textContent || '');
        }
        if (!timestamp) {
            const timeLink = container.querySelector(
                'a[href*="/story.php"] span, a[href*="/posts/"] > span, a[aria-label]'
            );
            if (timeLink) {
                timestampText = timeLink.textContent.trim() || timeLink.getAttribute('aria-label') || '';
            }
        }
        if (!timestampText && !timestamp) {
            const allSpans = container.querySelectorAll('span, a');
            for (const span of allSpans) {
                const t = (span.textContent || '').trim().toLowerCase();
                if (t.match(/(\d+)\s*(s|m|h|hr|min|sec|ث|د|س|أمس|yesterday|ساعة|دقيقة|ثانية)/i)
                    || t.match(/^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)/i)) {
                    timestampText = span.textContent.trim();
                    break;
                }
            }
        }

        const allText = container.textContent || '';
        const likeMatch = allText.match(/(\d+[,\d]*)\s*(إعجاب|like|likes)/i);
        const commentMatch = allText.match(/(\d+[,\d]*)\s*(تعليق|comment|comments)/i);
        const shareMatch = allText.match(/(\d+[,\d]*)\s*(مشاركة|share|shares)/i);

        const hasPhoto = !!container.querySelector('img, [data-pagelet^="Photo"], [data-media*="photo"]');
        const hasVideo = !!container.querySelector('video, [data-pagelet^="Video"]');

        results.push({
            text: bestText,
            url: postUrl,
            post_id: postId,
            timestamp: timestamp,
            timestamp_text: timestampText || '',
            likes: likeMatch ? likeMatch[1].replace(/,/g, '') : '0',
            comments_count: commentMatch ? commentMatch[1].replace(/,/g, '') : '0',
            shares: shareMatch ? shareMatch[1].replace(/,/g, '') : '0',
            has_photo: hasPhoto,
            has_video: hasVideo,
        });
    }
    return results;
}
"""


class ContentExtractor:
    """Extracts Facebook posts using multiple strategies."""

    def __init__(self, page: Any):
        self.page = page

    async def try_selectors(self, selectors: list[str]) -> dict[str, int]:
        result = {}
        for sel in selectors:
            try:
                count = await self.page.evaluate(
                    f"document.querySelectorAll('{sel.replace(chr(39), chr(92)+chr(39))}').length"
                )
                result[sel] = count
            except Exception:
                result[sel] = -1
        return result

    async def expand_content(self) -> int:
        clicked = 0
        try:
            clicked = await self.page.evaluate("""
                () => {
                    let c = 0;
                    const btns = document.querySelectorAll('[role="button"]');
                    for (const btn of btns) {
                        const txt = btn.textContent.trim().toLowerCase();
                        if ((txt.includes('عرض المزيد') || txt.includes('see more')
                            || txt.includes('show more')) && btn.offsetHeight > 0) {
                            btn.click();
                            c++;
                        }
                    }
                    return c;
                }
            """)
            if clicked > 0:
                await self.page.wait_for_timeout(1500)
        except Exception:
            pass
        return clicked

    async def extract_posts(self, page_url: str, max_age_days: int = 0) -> list[dict[str, Any]]:
        raw = await self.page.evaluate(EXTRACT_FULL_JS)
        if not isinstance(raw, list):
            logger.warning("JS extraction returned non-list")
            return []

        cutoff = datetime.now(timezone.utc).timestamp() * 1000
        if max_age_days > 0:
            cutoff = cutoff - (max_age_days * 86400 * 1000)

        posts = []
        seen_texts = set()
        skipped_old = 0
        no_date = 0

        for item in raw:
            text = _clean_text(item.get("text", ""))
            if not text or len(text) < 50 or text in seen_texts:
                continue
            if _is_ui_noise(text):
                continue

            seen_texts.add(text)

            post_time = None
            ts = item.get("timestamp", 0)
            if ts and isinstance(ts, (int, float)) and ts > 0:
                post_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

            if max_age_days > 0 and post_time:
                if post_time.timestamp() * 1000 < cutoff:
                    skipped_old += 1
                    continue
            elif not post_time:
                no_date += 1

            post_url = item.get("url", "")
            if post_url and not post_url.startswith("http"):
                post_url = urljoin("https://www.facebook.com", post_url)

            posts.append({
                "text": text[:5000],
                "post_url": post_url or page_url,
                "post_id": item.get("post_id", ""),
                "content_type": "post",
                "page_name": "",
                "time": post_time,
                "timestamp_text": item.get("timestamp_text", ""),
                "likes": item.get("likes", "0"),
                "comments_count": item.get("comments_count", "0"),
                "shares": item.get("shares", "0"),
                "has_photo": item.get("has_photo", False),
                "has_video": item.get("has_video", False),
            })

        if max_age_days > 0:
            logger.info(
                f"  Date filter: {len(posts)} kept, {skipped_old} skipped (old), "
                f"{no_date} without date"
            )

        return posts
