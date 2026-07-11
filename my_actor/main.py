"""Apify Actor entrypoint for the Facebook OSINT engine."""

from __future__ import annotations

import asyncio
import sys

from apify import Actor
from loguru import logger

from my_actor.dispatcher import Dispatcher
from my_actor.schemas.input import ActorInput
from my_actor.utils.state import set_shutting_down


async def main() -> None:
    async with Actor:
        actor_input_raw = await Actor.get_input() or {}
        Actor.log.info(f"Actor input: {actor_input_raw}")

        try:
            actor_input = ActorInput.model_validate(actor_input_raw)
        except Exception as e:
            Actor.log.error(f"Invalid input: {e}")
            await Actor.push_data({
                "success": False,
                "items": [],
                "count": 0,
                "message": f"Invalid input: {e}",
            })
            return

        dispatcher = Dispatcher()
        try:
            result = await dispatcher.dispatch(actor_input)
        except Exception as e:
            Actor.log.exception("Unhandled dispatcher error")
            await Actor.push_data({
                "success": False,
                "items": [],
                "count": 0,
                "action": actor_input.action,
                "query": actor_input.query,
                "url": actor_input.url,
                "message": f"Internal error: {e}",
            })
            return

        output = result.to_dict()
        Actor.log.info(f"Pushing {output['count']} items")
        await Actor.push_data(output)


def _configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


if __name__ == "__main__":
    _configure_logging()
    try:
        asyncio.run(main())
    finally:
        set_shutting_down(True)
