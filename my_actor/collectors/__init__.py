"""Facebook scraping collectors."""

from my_actor.collectors.base import BaseCollector
from my_actor.collectors.facebook_post_collector import FacebookPostCollector
from my_actor.collectors.facebook_comment_collector import FacebookCommentCollector
from my_actor.collectors.facebook_graphql_collector import FacebookGraphQLCollector
from my_actor.collectors.facebook_apify_collector import FacebookApifyCollector
from my_actor.collectors.facebook_crawlee_collector import FacebookCrawleeCollector
from my_actor.collectors.facebook_page_collector import FacebookPageCollector
from my_actor.collectors.facebook_profile_collector import FacebookProfileCollector
from my_actor.collectors.facebook_group_collector import FacebookGroupCollector
from my_actor.collectors.facebook_photo_collector import FacebookPhotoCollector
from my_actor.collectors.facebook_video_collector import FacebookVideoCollector
from my_actor.collectors.facebook_event_collector import FacebookEventCollector
from my_actor.collectors.facebook_search_collector import FacebookSearchCollector

__all__ = [
    "BaseCollector",
    "FacebookPostCollector",
    "FacebookCommentCollector",
    "FacebookGraphQLCollector",
    "FacebookApifyCollector",
    "FacebookCrawleeCollector",
    "FacebookPageCollector",
    "FacebookProfileCollector",
    "FacebookGroupCollector",
    "FacebookPhotoCollector",
    "FacebookVideoCollector",
    "FacebookEventCollector",
    "FacebookSearchCollector",
]
