"""Actor configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ActorConfig:
    """Production Apify Actor configuration."""

    apify_token: str = field(default_factory=lambda: os.getenv("APIFY_API_TOKEN", ""))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    debug_dir: Path = field(default_factory=lambda: Path(os.getenv("DEBUG_DIR", "debug")))
    default_limit: int = 20
    max_limit: int = 200
    timezone: str = "Asia/Damascus"
    locale: str = "ar-AR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "debug_dir", Path(self.debug_dir))
        self.debug_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class BrowserConfig:
    """Playwright browser settings."""

    headless: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1366, "height": 768})
    locale: str = "ar-AR"
    timezone: str = "Asia/Damascus"


def get_config() -> ActorConfig:
    return ActorConfig()
