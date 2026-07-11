"""Facebook collector using Crawlee (PlaywrightCrawler)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from my_actor.collectors.base import BaseCollector
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


_IGNORE_STATUS = frozenset({301, 302, 303, 307, 308, 400, 401, 403, 404, 429, 500, 502, 503})


class FacebookCrawleeCollector(BaseCollector):
    """Facebook collector using Crawlee for posts, search, and comments."""

    MAX_TEXT_LENGTH = 5000

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        max_age_days: int = 7,
        headless: bool = True,
    ):
        self._cookies_list = parse_cookies(cookies)
        self.max_age_days = max_age_days
        self.headless = headless

    def _crawler_kwargs(self, max_requests: int = 2) -> dict[str, Any]:
        return dict(
            max_requests_per_crawl=max_requests,
            headless=self.headless,
            use_incognito_pages=True,
            ignore_http_error_status_codes=_IGNORE_STATUS,
            retry_on_blocked=True,
            max_request_retries=1,
            navigation_timeout=30_000,
            browser_new_context_options={
                "storage_state": {"cookies": self._cookies_list}
            } if self._cookies_list else None,
        )

    async def collect(self, target: str, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        collect_type = kwargs.get("collect_type", "posts")
        max_items = kwargs.get("max_items", 10)

        if collect_type == "posts":
            return await self._collect_posts(target, max_items)
        if collect_type == "search":
            return await self._collect_search(target, max_items)
        if collect_type == "comments":
            return await self._collect_comments(kwargs.get("post_url") or target, max_items)

        logger.warning(f"[Crawlee] Unknown type: {collect_type}")
        return []

    @staticmethod
    async def _extract_articles(page: Any) -> list[str]:
        return await page.evaluate("""
            () => {
                const out = [];
                document.querySelectorAll('div[role="article"]').forEach(a => {
                    let text = '';
                    a.querySelectorAll('span').forEach(s => {
                        const t = s.innerText?.trim();
                        if (t && t.length > 20) text += t + '\\n';
                    });
                    if (text.trim().length > 30) out.push(text.trim());
                });
                return [...new Set(out)];
            }
        """) or []

    @staticmethod
    async def _body_preview(page: Any, length: int = 300) -> str:
        return await page.evaluate(f"document.body?.innerText?.slice(0,{length}) || ''")

    @staticmethod
    def _item(text: str, url: str, ctype: str, page_name: str, source: str) -> dict[str, Any]:
        return {
            "text": text[:5000],
            "post_url": url,
            "content_type": ctype,
            "page_name": page_name,
            "time": datetime.now(timezone.utc),
            "source": source,
        }

    async def _collect_posts(self, page_name: str, max_posts: int) -> list[dict[str, Any]]:
        from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

        items: list[dict[str, Any]] = []
        crawler = PlaywrightCrawler(**self._crawler_kwargs(2))

        @crawler.router.default_handler
        async def handler(ctx: PlaywrightCrawlingContext) -> None:
            await ctx.page.wait_for_load_state("networkidle", timeout=20_000)
            await ctx.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await ctx.page.wait_for_timeout(3000)

            raw = await self._extract_articles(ctx.page)
            for t in raw[:max_posts]:
                items.append(self._item(t, ctx.request.url, "post", page_name, "crawlee"))

            if not raw:
                ctx.log.info(f"[Crawlee] 0 posts. body: {(await self._body_preview(ctx.page))[:200]}")

        try:
            await crawler.run([f"https://www.facebook.com/{page_name}"])
        except Exception as e:
            logger.error(f"[Crawlee] Posts error {page_name}: {e}")

        logger.info(f"[Crawlee] {len(items)} posts from {page_name}")
        return items

    async def _collect_search(self, query: str, max_items: int) -> list[dict[str, Any]]:
        from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

        items: list[dict[str, Any]] = []
        crawler = PlaywrightCrawler(**self._crawler_kwargs(2))

        @crawler.router.default_handler
        async def handler(ctx: PlaywrightCrawlingContext) -> None:
            await ctx.page.wait_for_load_state("networkidle", timeout=20_000)
            await ctx.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await ctx.page.wait_for_timeout(3000)

            raw = await self._extract_articles(ctx.page)
            for t in raw[:max_items]:
                items.append(self._item(t, ctx.request.url, "search_result", query, "crawlee_search"))

            if not raw:
                ctx.log.info(f"[Crawlee] 0 results. body: {(await self._body_preview(ctx.page))[:200]}")

        try:
            await crawler.run([
                f"https://www.facebook.com/search/top?q={query}",
                f"https://www.facebook.com/search/posts?q={query}",
            ])
        except Exception as e:
            logger.error(f"[Crawlee] Search error '{query}': {e}")

        logger.info(f"[Crawlee] {len(items)} results for '{query}'")
        return items

    async def _collect_comments(self, post_url: str, max_comments: int) -> list[dict[str, Any]]:
        from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

        items: list[dict[str, Any]] = []
        crawler = PlaywrightCrawler(**self._crawler_kwargs(1))

        @crawler.router.default_handler
        async def handler(ctx: PlaywrightCrawlingContext) -> None:
            await ctx.page.wait_for_load_state("networkidle", timeout=20_000)
            try:
                await ctx.page.wait_for_selector('div[role="article"]', timeout=10_000)
            except Exception:
                pass
            await ctx.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await ctx.page.wait_for_timeout(3000)

            raw = await ctx.page.evaluate("""
                () => {
                    const out = [];
                    for (const sel of [
                        'div[data-testid="UFI2Comment/body"]',
                        'div[role="article"] ul li',
                        'div[class*="comment"]',
                    ]) {
                        const els = document.querySelectorAll(sel);
                        if (els.length) {
                            els.forEach(el => {
                                const t = el.innerText?.trim();
                                if (t && t.length > 10) out.push(t);
                            });
                            break;
                        }
                    }
                    return [...new Set(out)];
                }
            """) or []

            for t in raw[:max_comments]:
                items.append(self._item(t, post_url, "comment", post_url, "crawlee_comments"))

        try:
            await crawler.run([post_url])
        except Exception as e:
            logger.error(f"[Crawlee] Comments error: {e}")

        logger.info(f"[Crawlee] {len(items)} comments")
        return items
