"""General text and data helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


def truncate_text(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[<>]", "", text)
    return text.strip()


def format_timestamp(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if not dt:
        return ""
    return dt.strftime(fmt)


def normalize_url(url: str, base: str = "https://www.facebook.com") -> str:
    url = url.strip()
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return f"{base.rstrip('/')}/{url.lstrip('/')}"


def parse_cookies(cookies: str | list[dict] | dict | None) -> list[dict] | None:
    """Parse a cookie payload into a list of cookie dicts."""
    if cookies is None:
        return None
    try:
        raw: Any = json.loads(cookies) if isinstance(cookies, str) else cookies
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, list) and all(isinstance(c, dict) for c in raw):
            for c in raw:
                if c.get("sameSite") not in ("Strict", "Lax", "None"):
                    c["sameSite"] = "Lax"
            return raw
    except Exception:
        pass
    return None


def cookie_list_to_dict(cookies: list[dict] | None) -> dict[str, str]:
    if not cookies:
        return {}
    return {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
