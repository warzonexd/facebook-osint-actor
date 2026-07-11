"""Playwright browser lifecycle with anti-detection measures."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.config import BrowserConfig


class BrowserManager:
    """Manages Playwright browser lifecycle with anti-detection measures."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | None = None,
        headless: bool = True,
        config: BrowserConfig | None = None,
    ):
        self.cookies = cookies
        self.headless = headless
        self.config = config or BrowserConfig()
        self._pw: Any = None
        self.browser: Any = None
        self.context: Any = None

    @property
    def user_agent(self) -> str:
        return self.config.user_agent

    async def __aenter__(self) -> "BrowserManager":
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().__aenter__()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-setuid-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent=self.user_agent,
            viewport=self.config.viewport,
            locale=self.config.locale,
            timezone_id=self.config.timezone,
            permissions=[],
            ignore_https_errors=True,
        )
        await self._apply_anti_detection()
        if self.cookies:
            await self._apply_cookies()
        logger.debug("Browser context started")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.__aexit__(exc_type, exc_val, exc_tb)
        except Exception:
            pass
        logger.debug("Browser context closed")

    async def _apply_anti_detection(self) -> None:
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ar-SA', 'ar', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        """)

    async def _apply_cookies(self) -> None:
        try:
            cleaned = []
            for c in self.cookies:
                entry = dict(c)
                if entry.get("sameSite") not in ("Strict", "Lax", "None"):
                    entry["sameSite"] = "Lax"
                cleaned.append(entry)
            await self.context.add_cookies(cleaned)
            logger.debug(f"Applied {len(cleaned)} cookies")
        except Exception as e:
            logger.warning(f"Cookie application failed: {e}")

    async def new_page(self) -> Any:
        page = await self.context.new_page()
        page.on("dialog", lambda dialog: dialog.dismiss())
        return page
