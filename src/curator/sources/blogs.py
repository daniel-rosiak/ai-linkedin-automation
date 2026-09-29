from typing import Dict, List

from src.curator.base import FeedSourceFetcher
from src.curator.constants import FEED_CONFIGS
from src.db.models import Article

# Pre-instantiate feed fetchers dynamically from FEED_CONFIGS
BLOG_FETCHERS: Dict[str, FeedSourceFetcher] = {
    source: FeedSourceFetcher(source_name=source, feed_url=url)
    for source, url in FEED_CONFIGS.items()
    if source != "infoq"  # infoq is categorized under aggregators
}


def fetch_netflix_tech(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["netflix_tech"].fetch(limit=limit)


def fetch_shopify_blog(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["shopify_blog"].fetch(limit=limit)


def fetch_cloudflare_blog(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["cloudflare_blog"].fetch(limit=limit)


def fetch_stripe_blog(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["stripe_blog"].fetch(limit=limit)


def fetch_meta_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["meta_engineering"].fetch(limit=limit)


def fetch_airbnb_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["airbnb_engineering"].fetch(limit=limit)


def fetch_github_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["github_engineering"].fetch(limit=limit)


def fetch_dropbox_tech(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["dropbox_tech"].fetch(limit=limit)


def fetch_atlassian_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["atlassian_engineering"].fetch(limit=limit)


def fetch_slack_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["slack_engineering"].fetch(limit=limit)


def fetch_spotify_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["spotify_engineering"].fetch(limit=limit)


def fetch_pinterest_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["pinterest_engineering"].fetch(limit=limit)


def fetch_google_developers(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["google_developers"].fetch(limit=limit)


def fetch_microsoft_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["microsoft_engineering"].fetch(limit=limit)


def fetch_etsy_craft(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["etsy_craft"].fetch(limit=limit)


def fetch_square_corner(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["square_corner"].fetch(limit=limit)


def fetch_figma_tech(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["figma_tech"].fetch(limit=limit)


def fetch_stackoverflow_engineering(limit: int = 5) -> List[Article]:
    return BLOG_FETCHERS["stackoverflow_engineering"].fetch(limit=limit)
