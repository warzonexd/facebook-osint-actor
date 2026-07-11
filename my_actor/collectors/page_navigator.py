"""Facebook page navigation and popup handling."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.utils.state import is_shutting_down


LOGIN_INDICATORS = [
    "login", "checkpoint", "identify", "两步验证", "confirm identity",
    "حماية", "تسجيل الدخول", "confirm your identity",
    "enter login code", "two-factor",
]

DISMISS_TEXTS = [
    "allow all cookies", "accept all", "accept cookies", "allow cookies",
    "السماح بكل", "قبول الكل", "موافق",
    "not now", "ليس الآن", "skip", "تخطي",
    "close", "إغلاق", "×",
    "got it", "حسناً", "understanding",
    "maybe later", "ربما لاحقاً",
]


class PageNavigator:
    """Handles Facebook page navigation with resilience and popup dismissal."""

    def __init__(self, page: Any, debug: Any | None = None):
        self.page = page
        self.debug = debug

    async def safe_goto(self, url: str, timeout: int = 30000) -> str:
        if is_shutting_down():
            return "SHUTTING_DOWN"

        logger.info(f"Navigating to {url}")
        status = 0
        try:
            resp = await self.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            status = resp.status if resp else 0
            logger.info(f"  HTTP status: {status}")
        except Exception as e:
            logger.warning(f"  goto failed: {e}")

        if status in (404, 403, 410, 500, 502, 503):
            return f"HTTP_{status}"

        await self._wait_for_page_settle()
        return await self._detect_page_state()

    async def _wait_for_page_settle(self, max_wait: int = 3) -> None:
        for _ in range(max_wait):
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=2000)
                break
            except Exception:
                pass

    async def _detect_page_state(self) -> str:
        current_url = self.page.url.lower()
        for indicator in LOGIN_INDICATORS:
            if indicator in current_url:
                return f"REDIRECTED_TO_LOGIN: URL contains '{indicator}'"
        try:
            body_text = await self.page.evaluate("document.body?.innerText?.toLowerCase() || ''")
            if body_text:
                for indicator in LOGIN_INDICATORS:
                    if indicator in body_text:
                        return f"LOGIN_PROMPT_DETECTED: page shows '{indicator}'"
        except Exception:
            pass
        return "OK"

    async def handle_popups(self) -> int:
        dismissed = 0
        for _ in range(2):
            try:
                found = await self.page.evaluate(
                    """
                    (dismissTexts) => {
                        let count = 0;
                        const buttons = document.querySelectorAll(
                            '[role="button"], button, a[role="button"], div[aria-label], span[role="button"]'
                        );
                        for (const btn of buttons) {
                            const txt = btn.textContent.trim().toLowerCase();
                            if (dismissTexts.some(d => txt.includes(d))) {
                                if (btn.offsetHeight > 0 && btn.offsetWidth > 0) {
                                    btn.click();
                                    count++;
                                }
                            }
                        }
                        return count;
                    }
                    """,
                    DISMISS_TEXTS,
                )
                dismissed += found
                if found > 0:
                    await self.page.wait_for_timeout(800)
            except Exception:
                break
        if dismissed > 0:
            logger.info(f"Dismissed {dismissed} popup(s)")
        return dismissed

    async def scroll_progressive(self, steps: int = 5, delay_ms: int = 2000) -> int:
        total_height = 0
        new_content_count = 0
        for i in range(steps):
            if is_shutting_down():
                break
            try:
                await self.page.evaluate("window.scrollBy(0, 2000)")
                await self.page.wait_for_timeout(delay_ms)
                current_height = await self.page.evaluate("document.body.scrollHeight")
                if current_height == total_height and i > 1:
                    logger.info(f"  Scroll stopped: no height change at step {i}")
                    break
                total_height = current_height
                try:
                    count = await self.page.evaluate(
                        'document.querySelectorAll(\'[role="article"]\').length'
                    )
                    if count > new_content_count:
                        new_content_count = count
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"  Scroll error at step {i}: {e}")
                break
        return new_content_count

    async def wait_for_content(self, selectors: list[str], timeout: int = 3000) -> tuple[str, bool]:
        top = selectors[:5]
        try:
            js = """
                (selectors) => {
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetHeight > 0) return sel;
                    }
                    return '';
                }
            """
            found = await self.page.evaluate(js, top)
            if found:
                logger.info(f"  Fast selector found: {found}")
                return found, True
        except Exception:
            pass

        for sel in selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=min(timeout, 3000))
                logger.info(f"  Selector found: {sel}")
                return sel, True
            except Exception:
                continue
        return "", False

    async def get_final_url(self) -> str:
        try:
            return self.page.url
        except Exception:
            return "unknown"

    async def get_page_title(self) -> str:
        try:
            return await self.page.title()
        except Exception:
            return "unknown"
