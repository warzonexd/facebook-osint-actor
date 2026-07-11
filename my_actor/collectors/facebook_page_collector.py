"""Facebook page metadata collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import normalize_url, parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_PAGE_JS = r"""
() => {
    const getText = (sel) => {
        const el = document.querySelector(sel);
        return el ? el.innerText.trim() : '';
    };
    const getAttr = (sel, attr) => {
        const el = document.querySelector(sel);
        return el ? el.getAttribute(attr) || '' : '';
    };
    const cover = getAttr('img[data-imgperflogname="profile_cover_photo"]', 'src')
        || getAttr('div[data-pagelet="ProfileCoverPhoto"] img', 'src')
        || getAttr('div[role="img"] img', 'src');
    const avatar = getAttr('svg image', 'xlink:href')
        || getAttr('img[alt*="profile picture"]', 'src')
        || getAttr('div[data-pagelet="ProfilePic"] img', 'src');
    const title = document.title.replace(' | Facebook', '').trim();
    const followersMatch = document.body.innerText.match(/([\d.,]+\s*[KMBkmb]?)\s*(followers|متابع)/i);
    const likesMatch = document.body.innerText.match(/([\d.,]+\s*[KMBkmb]?)\s*(likes|إعجاب)/i);
    return {
        title: title,
        description: getText('div[data-pagelet="ProfileHeader"] span') || getText('div[role="main"] span'),
        cover_url: cover,
        avatar_url: avatar,
        followers_text: followersMatch ? followersMatch[0] : '',
        likes_text: likesMatch ? likesMatch[0] : '',
    };
}
"""


class FacebookPageCollector(BaseCollector):
    """Extract metadata from a public Facebook page."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        headless: bool = True,
        debug_dir: str = "debug",
    ):
        self.cookies = parse_cookies(cookies)
        self.headless = headless
        self.debug_dir = debug_dir

    async def collect(self, target: str, max_items: int = 1, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        url = normalize_url(page_name)
        debug = DebugManager(f"page_{page_name}", self.debug_dir)
        logger.info(f"[FB PageCollector] Starting: {page_name}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()
                await debug.screenshot(page, "final")

                if diagnosis != "OK":
                    logger.warning(f"[FB PageCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                data = await page.evaluate(EXTRACT_PAGE_JS)
                data.update({
                    "content_type": "page",
                    "page_name": page_name,
                    "url": url,
                    "source": "browser",
                })

                debug.write_report(1, page.url, "SUCCESS")
                return [data]
        except Exception as e:
            logger.error(f"[FB PageCollector Error] {page_name}: {e}")
            return []
