"""Route Apify Actor actions to the appropriate Facebook collector."""

from __future__ import annotations

from typing import Any

from loguru import logger

from my_actor.collectors import (
    FacebookCommentCollector,
    FacebookEventCollector,
    FacebookGroupCollector,
    FacebookPageCollector,
    FacebookPhotoCollector,
    FacebookPostCollector,
    FacebookProfileCollector,
    FacebookSearchCollector,
    FacebookVideoCollector,
)
from my_actor.config import ActorConfig, get_config
from my_actor.models.result import ActorOutput
from my_actor.schemas.input import ActorInput


class Dispatcher:
    """Dispatches a validated Actor input to the matching collector(s)."""

    def __init__(self, config: ActorConfig | None = None):
        self.config = config or get_config()

    async def dispatch(self, actor_input: ActorInput) -> ActorOutput:
        action = actor_input.action
        target = self._resolve_target(actor_input)

        logger.info(f"Dispatching action={action} target={target} limit={actor_input.limit}")

        if not target:
            return ActorOutput(
                success=False,
                action=action,
                message="Missing required 'query' or 'url' parameter.",
            )

        collector = self._build_collector(action, actor_input)
        try:
            items = await collector.collect(
                target,
                max_items=actor_input.limit,
                collect_type=self._collect_type(action),
            )
        except Exception as e:
            logger.exception(f"Collector failed for action={action}")
            return ActorOutput(
                success=False,
                action=action,
                query=actor_input.query,
                url=actor_input.url,
                message=f"Collector error: {e}",
            )

        return ActorOutput(
            success=True,
            items=items,
            count=len(items),
            action=action,
            query=actor_input.query,
            url=actor_input.url,
            message=f"Collected {len(items)} items",
        )

    def _resolve_target(self, actor_input: ActorInput) -> str:
        if actor_input.url:
            return actor_input.url.strip("/").split("/")[-1]
        return actor_input.query.strip()

    def _collect_type(self, action: str) -> str:
        mapping = {
            "search": "search",
            "posts": "posts",
            "comments": "comments",
        }
        return mapping.get(action, "posts")

    def _build_collector(self, action: str, actor_input: ActorInput) -> Any:
        cookies = actor_input.cookies
        headless = actor_input.headless
        max_age_days = actor_input.max_age_days
        debug_dir = str(self.config.debug_dir)

        if action == "posts":
            return FacebookPostCollector(
                cookies=cookies,
                headless=headless,
                max_age_days=max_age_days,
                debug_dir=debug_dir,
            )
        if action == "comments":
            return FacebookCommentCollector(
                cookies=cookies,
                headless=headless,
                max_age_days=max_age_days,
                debug_dir=debug_dir,
            )
        if action == "pages":
            return FacebookPageCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)
        if action == "profiles":
            return FacebookProfileCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)
        if action == "groups":
            return FacebookGroupCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)
        if action == "photos":
            return FacebookPhotoCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)
        if action == "videos":
            return FacebookVideoCollector(
                cookies=cookies,
                headless=headless,
                debug_dir=debug_dir,
                content_type="video",
            )
        if action == "reels":
            return FacebookVideoCollector(
                cookies=cookies,
                headless=headless,
                debug_dir=debug_dir,
                content_type="reel",
            )
        if action == "events":
            return FacebookEventCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)
        if action == "search":
            return FacebookSearchCollector(cookies=cookies, headless=headless, debug_dir=debug_dir)

        raise ValueError(f"Unsupported action: {action}")
