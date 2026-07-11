"""Facebook video and reels collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_VIDEOS_JS = """
(maxItems) => {
    const results = [];
    const seen = new Set();
    const items = document.querySelectorAll('a[href*="/videos/"], a[href*="/reel/"], a[href*="/watch/"]');
    for (const el of items) {
        const href = el.getAttribute('href') || '';
        if (!href || seen.has(href)) continue;
        const text = el.innerText?.trim() || '';
        const img = el.querySelector('img');
        const thumb = img ? (img.src || img.getAttribute('data-src') || '') : '';
        const isReel = href.includes('/reel/');
        seen.add(href);
        results.push({
            url: href.startsWith('http') ? href : 'https://www.facebook.com' + href,
            title: text,
            thumbnail_url: thumb,
            is_reel: isReel,
        });
        if (results.length >= maxItems) break;
    }
    return results;
}
"""


class FacebookVideoCollector(BaseCollector):
    """Collect public video/reel URLs from a Facebook page."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        headless: bool = True,
        debug_dir: str = "debug",
        content_type: str = "video",
    ):
        self.cookies = parse_cookies(cookies)
        self.headless = headless
        self.debug_dir = debug_dir
        self.content_type = content_type

    async def collect(self, target: str, max_items: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        path = "reels" if self.content_type == "reel" else "videos"
        url = f"https://www.facebook.com/{page_name}/{path}"
        debug = DebugManager(f"{self.content_type}s_{page_name}", self.debug_dir)
        logger.info(f"[FB VideoCollector] Starting {self.content_type}: {page_name}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()

                if diagnosis != "OK":
                    logger.warning(f"[FB VideoCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                await navigator.scroll_progressive(steps=3)
                raw = await page.evaluate(EXTRACT_VIDEOS_JS, max_items)

                results = []
                for item in raw:
                    item.update({
                        "content_type": self.content_type,
                        "page_name": page_name,
                        "source": "browser",
                    })
                    results.append(item)
                    if len(results) >= max_items:
                        break

                await debug.screenshot(page, "final")
                debug.write_report(len(results), page.url, "SUCCESS" if results else f"NO_{self.content_type.upper()}S_FOUND")
                logger.info(f"[FB VideoCollector] {len(results)} {self.content_type}s from {page_name}")
                return results
        except Exception as e:
            logger.error(f"[FB VideoCollector Error] {page_name}: {e}")
            return []
