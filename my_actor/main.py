from apify import Actor


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}

        await Actor.push_data({
            "status": "ok",
            "message": "Facebook OSINT Actor is running",
            "input": actor_input,
        })


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())