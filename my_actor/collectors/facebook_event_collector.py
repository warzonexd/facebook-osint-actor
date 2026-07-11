"""Facebook event search collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_EVENTS_JS = r"""
(maxItems) => {
    const results = [];
    const seen = new Set();
    const cards = document.querySelectorAll('a[href*="/events/"]');
    for (const el of cards) {
        const href = el.getAttribute('href') || '';
        if (!href || seen.has(href)) continue;
        seen.add(href);
        const text = el.innerText?.trim() || '';
        const title = text.split('\\n')[0];
        const lines = text.split('\\n');
        const date = lines.find(l => /\d/.test(l)) || '';
        const location = lines.slice(lines.indexOf(date) + 1).find(l => l.length > 3) || '';
        results.push({
            url: href.startsWith('http') ? href : 'https://www.facebook.com' + href,
            title: title,
            date_text: date,
            location: location,
        });
        if (results.length >= maxItems) break;
    }
    return results;
}
"""


class FacebookEventCollector(BaseCollector):
    """Search public Facebook events by query."""

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

        query = target.strip()
        url = f"https://www.facebook.com/events/search/?q={query.replace(' ', '+')}"
        debug = DebugManager(f"events_{query}", self.debug_dir)
        logger.info(f"[FB EventCollector] Searching: {query}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()

                if diagnosis != "OK":
                    logger.warning(f"[FB EventCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                await navigator.scroll_progressive(steps=3)
                raw = await page.evaluate(EXTRACT_EVENTS_JS, max_items)

                results = []
                for item in raw:
                    item.update({
                        "content_type": "event",
                        "query": query,
                        "source": "browser",
                    })
                    results.append(item)
                    if len(results) >= max_items:
                        break

                await debug.screenshot(page, "final")
                debug.write_report(len(results), page.url, "SUCCESS" if results else "NO_EVENTS_FOUND")
                logger.info(f"[FB EventCollector] {len(results)} events for '{query}'")
                return results
        except Exception as e:
            logger.error(f"[FB EventCollector Error] {query}: {e}")
            return []
