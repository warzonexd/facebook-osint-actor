"""Apify Actor input schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from my_actor.utils.constants import DEFAULT_LIMIT, MAX_LIMIT, SUPPORTED_ACTIONS


class ActorInput(BaseModel):
    """Validated Actor input."""

    action: str = Field(..., description="Operation to perform")
    query: str = Field(default="", description="Search query or page identifier")
    url: str = Field(default="", description="Direct Facebook URL")
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    headless: bool = Field(default=True, description="Run browser headless")
    cookies: list[dict[str, Any]] | str | None = Field(
        default=None, description="Optional Facebook cookies"
    )
    max_age_days: int = Field(default=0, ge=0, description="Filter items newer than N days")

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unsupported action '{value}'. Supported: {', '.join(sorted(SUPPORTED_ACTIONS))}"
            )
        return value

    @field_validator("query", "url")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value
