"""Facebook photo collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_PHOTOS_JS = """
(maxItems) => {
    const results = [];
    const seen = new Set();
    const images = document.querySelectorAll('a[href*="/photo/"] img, a[href*="/photos/"] img');
    for (const img of images) {
        const src = img.src || img.getAttribute('data-src') || '';
        if (!src || seen.has(src) || src.includes('emoji')) continue;
        seen.add(src);
        const link = img.closest('a');
        const url = link ? (link.href.startsWith('http') ? link.href : 'https://www.facebook.com' + link.getAttribute('href')) : '';
        const alt = img.alt || '';
        results.push({ url: url, image_url: src, caption: alt });
        if (results.length >= maxItems) break;
    }
    return results;
}
"""


class FacebookPhotoCollector(BaseCollector):
    """Collect public photo URLs from a Facebook page or album."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        headless: bool = True,
        debug_dir: str = "debug",
    ):
        self.cookies = parse_cookies(cookies)
        self.headless = headless
        self.debug_dir = debug_dir

    async def collect(self, target: str, max_items: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        url = f"https://www.facebook.com/{page_name}/photos"
        debug = DebugManager(f"photos_{page_name}", self.debug_dir)
        logger.info(f"[FB PhotoCollector] Starting: {page_name}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()

                if diagnosis != "OK":
                    logger.warning(f"[FB PhotoCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                await navigator.scroll_progressive(steps=3)
                raw = await page.evaluate(EXTRACT_PHOTOS_JS, max_items)

                results = []
                for item in raw:
                    item.update({
                        "content_type": "photo",
                        "page_name": page_name,
                        "source": "browser",
                    })
                    results.append(item)
                    if len(results) >= max_items:
                        break

                await debug.screenshot(page, "final")
                debug.write_report(len(results), page.url, "SUCCESS" if results else "NO_PHOTOS_FOUND")
                logger.info(f"[FB PhotoCollector] {len(results)} photos from {page_name}")
                return results
        except Exception as e:
            logger.error(f"[FB PhotoCollector Error] {page_name}: {e}")
            return []
