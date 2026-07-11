"""Facebook profile metadata collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import normalize_url, parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_PROFILE_JS = """
() => {
    const getText = (sel) => {
        const el = document.querySelector(sel);
        return el ? el.innerText.trim() : '';
    };
    const getAttr = (sel, attr) => {
        const el = document.querySelector(sel);
        return el ? el.getAttribute(attr) || '' : '';
    };
    const title = document.title.replace(' | Facebook', '').trim();
    const name = getText('h1') || title;
    const bio = getText('div[data-pagelet="ProfileTilesFeed_0"] span')
        || getText('div[role="main"] span.x193iq5w');
    const avatar = getAttr('div[data-pagelet="ProfilePic"] img', 'src')
        || getAttr('img[alt*="profile picture"]', 'src');
    const bodyText = document.body?.innerText || '';
    const workMatch = bodyText.match(/Works at ([^\\n]+)/i);
    const eduMatch = bodyText.match(/Studied at ([^\\n]+)/i);
    const locMatch = bodyText.match(/Lives in ([^\\n]+)/i);
    return {
        name: name,
        bio: bio,
        avatar_url: avatar,
        work: workMatch ? workMatch[1].trim() : '',
        education: eduMatch ? eduMatch[1].trim() : '',
        location: locMatch ? locMatch[1].trim() : '',
    };
}
"""


class FacebookProfileCollector(BaseCollector):
    """Extract metadata from a public Facebook profile."""

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

        profile_id = target.strip("/").split("/")[-1]
        url = normalize_url(profile_id)
        debug = DebugManager(f"profile_{profile_id}", self.debug_dir)
        logger.info(f"[FB ProfileCollector] Starting: {profile_id}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()
                await debug.screenshot(page, "final")

                if diagnosis != "OK":
                    logger.warning(f"[FB ProfileCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                data = await page.evaluate(EXTRACT_PROFILE_JS)
                data.update({
                    "content_type": "profile",
                    "profile_id": profile_id,
                    "url": url,
                    "source": "browser",
                })

                debug.write_report(1, page.url, "SUCCESS")
                return [data]
        except Exception as e:
            logger.error(f"[FB ProfileCollector Error] {profile_id}: {e}")
            return []
