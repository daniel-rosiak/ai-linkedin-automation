import sys
from typing import Callable, Dict, List

from src.curator.base import (
    BaseSourceFetcher,
    FeedSourceFetcher,
    _fetch_rss_or_atom,
    sanitize_html_summary,
)
from src.curator.constants import (
    FEED_CONFIGS,
    SOURCE_ALIASES,
    SOURCE_CATEGORY_MAP,
    SOURCE_DISPLAY_NAMES,
    resolve_source,
)
from src.curator.service import CurationService, curate_all
from src.curator.sources.aggregators import (
    ArxivFetcher,
    GitHubTrendingFetcher,
    HackerNewsFetcher,
    InfoQFetcher,
    LobstersFetcher,
    RedditFetcher,
    fetch_arxiv,
    fetch_github_trending,
    fetch_hacker_news,
    fetch_infoq,
    fetch_lobsters,
    fetch_reddit,
)
from src.curator.sources.blogs import (
    BLOG_FETCHERS,
    fetch_airbnb_engineering,
    fetch_atlassian_engineering,
    fetch_cloudflare_blog,
    fetch_dropbox_tech,
    fetch_etsy_craft,
    fetch_figma_tech,
    fetch_github_engineering,
    fetch_google_developers,
    fetch_meta_engineering,
    fetch_microsoft_engineering,
    fetch_netflix_tech,
    fetch_pinterest_engineering,
    fetch_shopify_blog,
    fetch_slack_engineering,
    fetch_spotify_engineering,
    fetch_square_corner,
    fetch_stackoverflow_engineering,
    fetch_stripe_blog,
)
from src.curator.sources.custom import (
    LinkedInEngineeringFetcher,
    UberEngineeringFetcher,
    fetch_linkedin_engineering,
    fetch_uber_engineering,
)


def get_source_fetchers() -> Dict[str, Callable[[int], List]]:
    """Returns dynamic mapping of canonical source names to fetcher functions in this package."""
    mod = sys.modules[__name__]
    return {
        "hacker_news": getattr(mod, "fetch_hacker_news"),
        "github_trending": getattr(mod, "fetch_github_trending"),
        "arxiv": getattr(mod, "fetch_arxiv"),
        "reddit": getattr(mod, "fetch_reddit"),
        "lobsters": getattr(mod, "fetch_lobsters"),
        "infoq": getattr(mod, "fetch_infoq"),
        "netflix_tech": getattr(mod, "fetch_netflix_tech"),
        "shopify_blog": getattr(mod, "fetch_shopify_blog"),
        "cloudflare_blog": getattr(mod, "fetch_cloudflare_blog"),
        "stripe_blog": getattr(mod, "fetch_stripe_blog"),
        "meta_engineering": getattr(mod, "fetch_meta_engineering"),
        "uber_engineering": getattr(mod, "fetch_uber_engineering"),
        "airbnb_engineering": getattr(mod, "fetch_airbnb_engineering"),
        "github_engineering": getattr(mod, "fetch_github_engineering"),
        "dropbox_tech": getattr(mod, "fetch_dropbox_tech"),
        "atlassian_engineering": getattr(mod, "fetch_atlassian_engineering"),
        "slack_engineering": getattr(mod, "fetch_slack_engineering"),
        "spotify_engineering": getattr(mod, "fetch_spotify_engineering"),
        "linkedin_engineering": getattr(mod, "fetch_linkedin_engineering"),
        "pinterest_engineering": getattr(mod, "fetch_pinterest_engineering"),
        "google_developers": getattr(mod, "fetch_google_developers"),
        "microsoft_engineering": getattr(mod, "fetch_microsoft_engineering"),
        "etsy_craft": getattr(mod, "fetch_etsy_craft"),
        "square_corner": getattr(mod, "fetch_square_corner"),
        "figma_tech": getattr(mod, "fetch_figma_tech"),
        "stackoverflow_engineering": getattr(mod, "fetch_stackoverflow_engineering"),
    }


__all__ = [
    # Base Abstractions & Utilities
    "BaseSourceFetcher",
    "FeedSourceFetcher",
    "_fetch_rss_or_atom",
    "sanitize_html_summary",
    # Constants & Resolvers
    "FEED_CONFIGS",
    "SOURCE_ALIASES",
    "SOURCE_CATEGORY_MAP",
    "SOURCE_DISPLAY_NAMES",
    "resolve_source",
    "get_source_fetchers",
    # Service & Pipeline
    "CurationService",
    "curate_all",
    # Aggregator Classes & Functions
    "HackerNewsFetcher",
    "GitHubTrendingFetcher",
    "ArxivFetcher",
    "RedditFetcher",
    "LobstersFetcher",
    "InfoQFetcher",
    "fetch_hacker_news",
    "fetch_github_trending",
    "fetch_arxiv",
    "fetch_reddit",
    "fetch_lobsters",
    "fetch_infoq",
    # Blog Functions
    "BLOG_FETCHERS",
    "fetch_netflix_tech",
    "fetch_shopify_blog",
    "fetch_cloudflare_blog",
    "fetch_stripe_blog",
    "fetch_meta_engineering",
    "fetch_airbnb_engineering",
    "fetch_github_engineering",
    "fetch_dropbox_tech",
    "fetch_atlassian_engineering",
    "fetch_slack_engineering",
    "fetch_spotify_engineering",
    "fetch_pinterest_engineering",
    "fetch_google_developers",
    "fetch_microsoft_engineering",
    "fetch_etsy_craft",
    "fetch_square_corner",
    "fetch_figma_tech",
    "fetch_stackoverflow_engineering",
    # Custom Scrapers
    "UberEngineeringFetcher",
    "LinkedInEngineeringFetcher",
    "fetch_uber_engineering",
    "fetch_linkedin_engineering",
]
