# Facebook OSINT Actor

Production-ready Apify Actor for Facebook OSINT scraping. Built on Playwright with anti-detection measures and multiple extraction strategies.

## Features

- Facebook Search
- Facebook Pages
- Facebook Profiles
- Facebook Groups
- Facebook Posts
- Facebook Comments
- Facebook Photos
- Facebook Videos
- Facebook Reels
- Facebook Events

## Technologies

- Python 3.11+
- Playwright (browser automation)
- Apify SDK (Actor lifecycle, dataset)
- httpx (HTTP/GraphQL extraction)
- BeautifulSoup4 + lxml (HTML parsing)
- Crawlee (PlaywrightCrawler fallback)
- AsyncIO throughout

## Project Structure

```
my_actor/
    main.py              # Apify Actor entrypoint
    dispatcher.py        # Routes actions to collectors
    config.py            # Actor and browser configuration
    browser/             # Playwright browser lifecycle
    collectors/          # Facebook scraping collectors
    facebook/            # Facebook-specific selectors
    parsers/             # HTML/JSON parsers
    models/              # Domain models (dataclasses)
    schemas/             # Pydantic input/output schemas
    utils/               # Helpers, constants, state
```

## Input

```json
{
    "action": "search",
    "query": "syria",
    "url": "",
    "limit": 20,
    "headless": true,
    "cookies": [],
    "max_age_days": 0
}
```

Supported `action` values: `search`, `pages`, `profiles`, `groups`, `posts`, `comments`, `photos`, `videos`, `reels`, `events`.

## Output

Normalized JSON pushed to the Apify dataset:

```json
{
    "success": true,
    "items": [...],
    "count": 1,
    "action": "pages",
    "query": "syrtelevision",
    "url": "",
    "message": "Collected 1 items"
}
```

## Build & Run

```bash
# Local run (requires dependencies installed + Playwright browsers)
apify run

# Or directly
python -m my_actor.main
```