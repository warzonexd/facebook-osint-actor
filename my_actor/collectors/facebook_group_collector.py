"""Facebook group metadata collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import parse_cookies
from my_actor.utils.state import is_shutting_down


EXTRACT_GROUP_JS = r"""
() => {
    const getText = (sel) => {
        const el = document.querySelector(sel);
        return el ? el.innerText.trim() : '';
    };
    const title = document.title.replace(' | Facebook', '').trim();
    const name = getText('h1') || title;
    const bodyText = document.body?.innerText || '';
    const membersMatch = bodyText.match(/([\d.,]+\s*[KMBkmb]?)\s*(members|عضو)/i);
    const privacyMatch = bodyText.match(/(Public|Private) group|مجموعة (عامة|خاصة)/i);
    const desc = getText('div[data-pagelet="GroupCover"] + div span')
        || getText('div[role="main"] span.x193iq5w');
    return {
        name: name,
        description: desc,
        members_text: membersMatch ? membersMatch[0] : '',
        privacy: privacyMatch ? privacyMatch[1] : '',
    };
}
"""


class FacebookGroupCollector(BaseCollector):
    """Extract metadata from a public Facebook group."""

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

        group_id = target.strip("/").split("/")[-1]
        url = f"https://www.facebook.com/groups/{group_id}"
        debug = DebugManager(f"group_{group_id}", self.debug_dir)
        logger.info(f"[FB GroupCollector] Starting: {group_id}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)

                diagnosis = await navigator.safe_goto(url)
                await navigator.handle_popups()
                await debug.screenshot(page, "final")

                if diagnosis != "OK":
                    logger.warning(f"[FB GroupCollector] Page state: {diagnosis}")
                    debug.write_report(0, page.url, diagnosis)
                    return []

                data = await page.evaluate(EXTRACT_GROUP_JS)
                data.update({
                    "content_type": "group",
                    "group_id": group_id,
                    "url": url,
                    "source": "browser",
                })

                debug.write_report(1, page.url, "SUCCESS")
                return [data]
        except Exception as e:
            logger.error(f"[FB GroupCollector Error] {group_id}: {e}")
            return []
