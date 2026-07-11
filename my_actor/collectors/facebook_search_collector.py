"""Facebook search results collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_SEARCH_JS = """
(maxItems) => {
    const results = [];
    const seen = new Set();
    const articles = document.querySelectorAll('[role="article"]');
    for (const art of articles) {
        const text = art.innerText?.trim();
        if (!text || seen.has(text) || text.split('\\n').length < 2) continue;
        seen.add(text);
        const link = art.querySelector('a[href*="/"]');
        const url = link ? (link.href.startsWith('http') ? link.href : 'https://www.facebook.com' + link.getAttribute('href')) : '';
        const lines = text.split('\\n').filter(l => l.trim());
        results.push({
            title: lines[0] || '',
            snippet: lines.slice(1, 4).join('\\n'),
            url: url,
        });
        if (results.length >= maxItems) break;
    }
    return results;
}
"""


class FacebookSearchCollector(BaseCollector):
    """Perform a Facebook search and return result snippets."""

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
        url = f"https://www.facebook.com/search/top?q={query.replace(' ', '+')}"
        debug = DebugManager(f"search_{query}", self.debug_dir)
        logger.info(f"[FB SearchCollector] Searching: {query}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()

                if diagnosis != "OK":
                    logger.warning(f"[FB SearchCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                await navigator.scroll_progressive(steps=3)
                raw = await page.evaluate(EXTRACT_SEARCH_JS, max_items)

                results = []
                for item in raw:
                    item.update({
                        "content_type": "search_result",
                        "query": query,
                        "source": "browser",
                    })
                    results.append(item)
                    if len(results) >= max_items:
                        break

                await debug.screenshot(page, "final")
                debug.write_report(len(results), page.url, "SUCCESS" if results else "NO_RESULTS_FOUND")
                logger.info(f"[FB SearchCollector] {len(results)} results for '{query}'")
                return results
        except Exception as e:
            logger.error(f"[FB SearchCollector Error] {query}: {e}")
            return []
