from loguru import logger


class BrowserManager:
    """Manages Playwright browser lifecycle with anti-detection measures."""

    def __init__(self, cookies: list[dict] | None = None, debug_dir: str | None = None):
        self.cookies = cookies
        self.debug_dir = debug_dir
        self.browser = None
        self.context = None

    @property
    def user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().__aenter__()
        self.browser = await self._pw.chromium.launch(
            headless=True,
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
            viewport={"width": 1366, "height": 768},
            locale="ar-AR",
            timezone_id="Asia/Damascus",
            permissions=[],
            ignore_https_errors=True,
        )
        await self._apply_anti_detection()
        if self.cookies:
            await self._apply_cookies()
        return self

    async def __aexit__(self, *args):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            await self._pw.__aexit__(*args)
        except Exception:
            pass

    async def _apply_anti_detection(self):
        """Hide Playwright automation痕迹."""
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ar-SA', 'ar', 'en-US', 'en'],
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        """)

    async def _apply_cookies(self):
        """Add cookies to context, validating them first."""
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

    async def new_page(self):
        page = await self.context.new_page()

        # Intercept and dismiss dialogs automatically
        page.on("dialog", lambda dialog: dialog.dismiss())

        return page
