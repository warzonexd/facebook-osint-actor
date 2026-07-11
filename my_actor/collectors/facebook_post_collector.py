"""Playwright-based Facebook post collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from my_actor.browser import BrowserManager
from my_actor.collectors.base import BaseCollector
from my_actor.collectors.content_extractor import ContentExtractor
from my_actor.facebook.selectors import POST_SELECTORS
from my_actor.collectors.debug_manager import DebugManager
from my_actor.collectors.page_navigator import PageNavigator
from my_actor.utils.helpers import normalize_url, parse_cookies
from my_actor.utils.state import is_shutting_down


class _SkipExtraction(Exception):
    """Raised when navigation fails; skip to diagnostics report."""


class FacebookPostCollector(BaseCollector):
    """Professional Facebook post collector using Playwright with diagnostics."""

    def __init__(
        self,
        cookies: list[dict[str, Any]] | str | None = None,
        max_age_days: int = 0,
        headless: bool = True,
        debug_dir: str = "debug",
    ):
        self.cookies = parse_cookies(cookies)
        self.max_age_days = max_age_days
        self.headless = headless
        self.debug_dir = debug_dir

    async def collect(self, target: str, max_items: int = 12, **kwargs: Any) -> list[dict[str, Any]]:
        if is_shutting_down():
            return []

        page_name = target.strip("/").split("/")[-1]
        posts: list[dict[str, Any]] = []
        base_url = normalize_url(page_name)
        debug = DebugManager(page_name, self.debug_dir)
        diagnosis = "UNKNOWN"

        logger.info(f"[FB PostCollector] Starting: {page_name}")

        try:
            async with BrowserManager(self.cookies, headless=self.headless) as mgr:
                if is_shutting_down():
                    return posts

                page = await mgr.new_page()
                navigator = PageNavigator(page, debug)
                extractor = ContentExtractor(page)

                debug._step("navigation")
                urls_to_try = [f"{base_url}/posts", base_url]

                final_url = ""
                for idx, url in enumerate(urls_to_try):
                    if is_shutting_down():
                        return posts
                    diagnosis = await navigator.safe_goto(url)
                    await debug.save_url(page, f"after_goto_{idx}")

                    if diagnosis == "OK":
                        final_url = page.url
                        break
                    logger.warning(f"  Page state: {diagnosis}")

                debug._step("popup_handling")
                await navigator.handle_popups()
                await debug.screenshot(page, "after_popups")

                if not final_url:
                    diagnosis = f"ALL_URLS_FAILED: last state '{diagnosis}'"
                    logger.warning(f"  {diagnosis}")
                    await debug.screenshot(page, "final")
                    final_url = await navigator.get_final_url()
                    await debug.save_url(page, "final")
                    raise _SkipExtraction()

                debug._step("wait_for_content")
                found_selector, found = await navigator.wait_for_content(POST_SELECTORS)
                diagnosis = f"SELECTOR_FOUND: {found_selector}" if found else "SELECTOR_NOT_FOUND"

                debug._step("expand_content")
                expanded = await extractor.expand_content()
                if expanded:
                    logger.info(f"  Expanded {expanded} post(s)")

                debug._step("selector_audit")
                selector_counts = await extractor.try_selectors(POST_SELECTORS)
                total_candidates = sum(v for v in selector_counts.values() if v > 0)
                if total_candidates == 0:
                    diagnosis = "NO_ELEMENTS_FOUND: all selectors returned 0 elements"
                else:
                    diagnosis = f"{total_candidates} candidate elements from selectors"

                for sel, cnt in selector_counts.items():
                    if cnt > 0:
                        logger.info(f"  Selector '{sel[:60]}...' → {cnt} elements")

                if total_candidates > 0:
                    debug._step("scrolling")
                    await navigator.scroll_progressive(steps=5)
                    selector_counts2 = await extractor.try_selectors(POST_SELECTORS)
                else:
                    selector_counts2 = selector_counts

                debug._step("extraction")
                raw_posts = await extractor.extract_posts(
                    final_url or page.url,
                    max_age_days=self.max_age_days,
                )

                for p in raw_posts:
                    p["page_name"] = page_name
                    p["time"] = datetime.now()
                    posts.append(p)
                    if len(posts) >= max_items:
                        break

                await debug.screenshot(page, "final")
                await debug.save_html(page, "final")
                final_url = await navigator.get_final_url()
                await debug.save_url(page, "final")

                if len(posts) == 0:
                    final_title = await navigator.get_page_title()
                    diagnosis = await self._diagnose_zero_posts(
                        page, final_url, final_title, diagnosis,
                        selector_counts, selector_counts2,
                    )
                else:
                    diagnosis = f"SUCCESS: {len(posts)} posts extracted"

                await debug.screenshot(page, "diagnosis")
                logger.info(f"[FB PostCollector] {len(posts)} posts from {page_name}")

        except _SkipExtraction:
            pass
        except Exception as e:
            diagnosis = f"EXCEPTION: {e}"
            logger.error(f"[FB PostCollector Error] {page_name}: {e}")

        debug.write_report(len(posts), final_url if final_url else base_url, diagnosis)
        return posts

    async def _diagnose_zero_posts(
        self, page: Any, final_url: str, title: str, diagnosis: str,
        before_counts: dict[str, int], after_counts: dict[str, int],
    ) -> str:
        reasons = []
        try:
            body = await page.evaluate("document.body?.innerText?.toLowerCase() || ''")
        except Exception:
            body = ""

        login_signals = [
            ("login", "تسجيل الدخول"),
            ("checkpoint", "نقطة تفتيش"),
            ("identify", "تأكيد الهوية"),
            ("confirm your identity", "تأكيد هويتك"),
            ("two-factor", "المصادقة الثنائية"),
        ]

        for en, ar in login_signals:
            if en in final_url.lower() or en in body[:500]:
                reasons.append(f"صفحة تسجيل دخول ({en})")
                break
            if ar in body[:500]:
                reasons.append(f"صفحة تسجيل دخول ({ar})")
                break

        if final_url and "facebook.com" not in final_url:
            reasons.append(f"تم التحويل إلى رابط خارج فيسبوك: {final_url[:80]}")

        total_before = sum(v for v in before_counts.values() if v > 0)
        total_after = sum(v for v in after_counts.values() if v > 0)

        if total_before == 0 and total_after == 0:
            reasons.append("لم يتم العثور على أي عنصر بواسطة جميع selectors")
        elif total_before == 0 and total_after > 0:
            reasons.append("العناصر ظهرت فقط بعد التمرير (قد يحتاج تمرير أكثر)")
        else:
            reasons.append(f"تم العثور على {total_after} عنصر لكن لم يتم استخراج نصوص صالحة")

        if len(body) < 200:
            reasons.append("الصفحة تبدو فارغة (أقل من 200 حرف في الـ body)")

        if "log in" in title.lower() or "facebook" not in title.lower():
            reasons.append(f"عنوان الصفحة غير متوقع: {title[:60]}")

        if "page not found" in body[:300] or "هذه الصفحة غير متاحة" in body[:300]:
            reasons.append("الصفحة غير موجودة (404)")

        reasons.append(f"الـ diagnosis الأصلي: {diagnosis}")
        final_diagnosis = " | ".join(reasons)
        logger.warning(f"[FB PostCollector] 0 posts analysis: {final_diagnosis}")
        return final_diagnosis
