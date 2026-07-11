"""DOM selectors and noise keywords for Facebook extraction."""

from __future__ import annotations

# Post container selectors, ordered from most specific to most generic.
POST_SELECTORS = [
    'div[data-pagelet^="FeedUnit"]',
    'div[data-pagelet="FeedUnit_0"]',
    'div[data-pagelet^="MinimalFeedUnit"]',
    '[role="article"]',
    '.x1yztbdb',
    '.x1n2onr6 > div.x1yztbdb',
    '.x1lliihq.x1n2onr6',
    '.x1c4vz4f',
    'div[aria-posinset]',
    'div.x1qjc9v5',
    'div.x9f619',
    'div[data-store*="top_level_post_id"]',
    'div[data-testid*="post"]',
    'div[data-testid*="feed"]',
    'div[role="feed"] > div',
]

# Selectors for extracting a post permalink from within a container.
URL_SELECTORS = [
    'a[href*="/posts/"]',
    'a[href*="/photos/"]',
    'a[href*="/videos/"]',
    'a[href*="/story.php"]',
    'a[href*="/permalink/"]',
    'a[href*="?story_fbid"]',
    'a[href*="?__xts__"]',
]

# Selectors for post text content.
TEXT_SELECTORS = [
    '[dir="auto"]',
    '.xdj266r.x11i5rnm.xat24cr.x1mh8g0r',
    '.x1heor9g',
    '.x193iq5w',
    '.x1lliihq',
    'div[data-ad-preview="message"]',
]

# UI noise keywords to filter out of extracted text.
UI_NOISE = [
    "beiträge", "info", "reels", "fotos", "gefolgt",
    "std.", "min.", "hrs", "mins", "ago", "shared with public",
    "posts", "videos", "photos", "about", "following", "followers",
    "interessiert", "gefällt mir", "kommentieren", "teilen",
    "منشورات", "فيديو", "صورة", "متابعة", "حول",
    "أعجبني", "تعليق", "مشاركة", "شارك", "المنشورات",
    "عرض المزيد", "عرض كافة", "show more", "see more",
    "إعجاب", "رد", "الردود", "كتب", "تعليقات",
]
