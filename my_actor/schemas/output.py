"""Apify Actor output schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActorResult(BaseModel):
    """Normalized Actor output."""

    success: bool = True
    items: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    action: str = ""
    query: str = ""
    url: str = ""
    message: str = ""
