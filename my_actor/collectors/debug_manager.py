"""Debug artifact manager for collector diagnostics."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class DebugManager:
    """Saves screenshots, HTML, and timing data for debugging extraction failures."""

    def __init__(self, page_name: str, debug_dir: str | Path = "debug"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = page_name.replace("/", "_").replace("\\", "_")
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in safe_name)
        safe_name = safe_name.strip("._ ") or "unknown"
        self.session_dir = Path(debug_dir) / f"{timestamp}_{safe_name}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._timings: list[dict[str, Any]] = []
        self._start = time.time()
        logger.info(f"Debug session: {self.session_dir}")

    def _step(self, name: str) -> float:
        elapsed = time.time() - self._start
        self._timings.append({"step": name, "elapsed_sec": round(elapsed, 2)})
        logger.info(f"  [{elapsed:6.2f}s] {name}")
        return elapsed

    async def screenshot(self, page: Any, name: str = "page") -> None:
        self._step(f"screenshot:{name}")
        path = self.session_dir / f"{name}.png"
        try:
            await page.screenshot(path=str(path), full_page=True)
            logger.debug(f"  Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"  Screenshot failed: {e}")

    async def save_html(self, page: Any, name: str = "page") -> None:
        self._step(f"html:{name}")
        path = self.session_dir / f"{name}.html"
        try:
            html = await page.content()
            path.write_text(html, encoding="utf-8")
            logger.debug(f"  HTML saved ({len(html)} bytes): {path}")
        except Exception as e:
            logger.warning(f"  HTML save failed: {e}")

    async def save_url(self, page: Any, name: str = "final") -> None:
        try:
            url = page.url
            self._step(f"url:{name}={url}")
            (self.session_dir / f"url_{name}.txt").write_text(url, encoding="utf-8")
        except Exception as e:
            logger.warning(f"  URL save failed: {e}")

    async def save_selector_result(self, selector: str, count: int, found: int) -> None:
        self._step(f"selector:{selector}={count} found, {found} usable")

    def write_report(self, posts_count: int, final_url: str, diagnosis: str) -> str:
        report = [
            "=" * 60,
            "COLLECTOR DEBUG REPORT",
            "=" * 60,
            f"Date: {datetime.now().isoformat()}",
            f"Items extracted: {posts_count}",
            f"Final URL: {final_url}",
            f"Diagnosis: {diagnosis}",
            "-" * 60,
            "Timeline:",
        ]
        for t in self._timings:
            report.append(f"  {t['elapsed_sec']:6.2f}s - {t['step']}")
        report.append("=" * 60)

        text = "\n".join(report)
        (self.session_dir / "report.txt").write_text(text, encoding="utf-8")
        logger.info(f"Debug report:\n{text}")
        return text

    def save_json(self, data: Any, name: str = "data") -> None:
        path = self.session_dir / f"{name}.json"
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"  JSON save failed: {e}")
