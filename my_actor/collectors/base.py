"""Abstract base for all Facebook collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, target: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Collect items for the given target and return normalized dicts."""
        ...
