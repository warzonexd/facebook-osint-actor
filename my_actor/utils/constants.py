"""Actor-wide constants."""

from __future__ import annotations

from typing import Final

SOURCE_FACEBOOK: Final = "facebook"

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 200

SUPPORTED_ACTIONS: Final[frozenset[str]] = frozenset({
    "search",
    "pages",
    "profiles",
    "groups",
    "posts",
    "comments",
    "photos",
    "videos",
    "reels",
    "events",
})

LOGIN_INDICATORS: Final[list[str]] = [
    "login", "checkpoint", "identify", "two-factor",
    "confirm your identity", "enter login code",
    "حماية", "تسجيل الدخول", "تأكيد الهوية",
]
