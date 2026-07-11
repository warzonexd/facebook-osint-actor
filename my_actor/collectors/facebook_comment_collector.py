"""Playwright-based Facebook comment collector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import normalize_url, parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_COMMENTS_JS = """
(cutoffMs) => {
    const results = [];
    const seen = new Set();

    const containers = document.querySelectorAll(
        '[role="article"], .x1n2onr6, div[data-pagelet*="Comment"], ul[data-pagelet] li'
    );

    for (const container of containers) {
        const dirEls = container.querySelectorAll('[dir="auto"]');
        let bestText = '';
        for (const el of dirEls) {
            const t = el.textContent.trim();
            if (t.length > 15 && t.length < 2000 && !seen.has(t)) {
                if (t.length > bestText.length) bestText = t;
            }
        }
        if (!bestText) continue;

        const lower = bestText.toLowerCase();
        if (lower.includes('عرض المزيد') || lower.includes('show more') ||
            lower.includes('see more') || lower.includes('إعجاب') ||
            lower.includes('like') || lower.includes('رد') ||
            lower.includes('reply') || lower.includes('·') ||
            bestText.split(' ').length <= 3) continue;

        let timestamp = 0;
        const abbr = container.querySelector('abbr[data-utime]');
        if (abbr) {
            timestamp = parseInt(abbr.getAttribute('data-utime'), 10) * 1000;
        }

        if (cutoffMs > 0 && timestamp > 0 && timestamp < cutoffMs) continue;

        seen.add(bestText);
        results.push({ text: bestText, timestamp: timestamp });
    }
    return results;
}
"""

CLICK_MORE_COMMENTS_JS = """
() => {
    let clicked = 0;
    const selectors = [
        'div[data-pagelet*="Comment"] span[role="button"]',
        'div[role="button"]',
        'span[role="button"]',
    ];
    let buttons = [];
    for (const sel of selectors) {
        buttons = document.querySelectorAll(sel);
        if (buttons.length > 0) break;
    }
    for (const btn of buttons) {
        const txt = btn.textContent.trim().toLowerCase();
        if ((txt.includes('عرض') || txt.includes('view') || txt.includes('more')) &&
            (txt.includes('تعليق') || txt.includes('comment') || txt.includes('رد') || txt.includes('reply'))) {
            try { btn.click(); clicked++; } catch(e) {}
        }
    }
    return clicked;
}
"""


class FacebookCommentCollector(BaseCollector):
    """Extract comments from a Facebook page or post URL."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        max_age_days: int = 0,
        headless: bool = True,
        debug_dir: str = "debug",
    ):
        self.cookies = parse_cookies(cookies)
        self.max_age_days = max_age_days
        self.headless = headless
        self.debug_dir = debug_dir

    async def collect(self, target: str, max_items: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        comments: list[dict[str, Any]] = []
        base_url = normalize_url(page_name)
        debug = DebugManager(f"comments_{page_name}", self.debug_dir)
        logger.info(f"[FB CommentCollector] Starting: {page_name}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                if is_shutting_down():
                    return comments

                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                debug._step("navigation")
                urls_to_try = [f"{base_url}/posts", base_url]
                diagnosis = "UNKNOWN"
                for url in urls_to_try:
                    if is_shutting_down():
                        return comments
                    diagnosis = await navigator.safe_goto(url)
                    if diagnosis == "OK":
                        break
                    logger.warning(f"  Comment nav: {diagnosis}")

                await navigator.handle_popups()
                await debug.screenshot(page, "initial")

                debug._step("scroll_and_expand")
                for i in range(10):
                    if is_shutting_down():
                        break
                    try:
                        await page.evaluate("window.scrollBy(0, 2000)")
                        await page.wait_for_timeout(2000)
                        if i % 2 == 0:
                            try:
                                await page.evaluate(CLICK_MORE_COMMENTS_JS)
                                await page.wait_for_timeout(1500)
                            except Exception:
                                pass
                    except Exception:
                        break

                debug._step("extraction")
                cutoff = 0
                if self.max_age_days > 0:
                    cutoff = (datetime.now(timezone.utc).timestamp() - (self.max_age_days * 86400)) * 1000
                raw_comments = await page.evaluate(EXTRACT_COMMENTS_JS, cutoff)

                seen = set()
                for item in raw_comments:
                    text = " ".join(item.get("text", "").split())
                    if len(text) > 20 and text not in seen:
                        seen.add(text)
                        ts = item.get("timestamp", 0)
                        post_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None
                        comments.append({
                            "text": text[:2000],
                            "post_url": f"{base_url}/posts",
                            "content_type": "comment",
                            "page_name": page_name,
                            "time": post_time,
                        })
                        if len(comments) >= max_items:
                            break

                await debug.screenshot(page, "final")
                await debug.save_html(page, "final")
                logger.info(f"[FB CommentCollector] {len(comments)} comments from {page_name}")

        except Exception as e:
            if "closed" not in str(e).lower():
                logger.error(f"[FB CommentCollector Error] {page_name}: {e}")

        debug.write_report(len(comments), base_url, "SUCCESS" if comments else "NO_COMMENTS_FOUND")
        return comments
