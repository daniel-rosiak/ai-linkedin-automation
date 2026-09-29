from typing import List, Optional

import src.db.database as db
from src.db.models import Article


class CurationService:
    """Orchestrates multi-source article curation, database deduplication, and filtering."""

    def __init__(self, fetchers_provider=None):
        self._fetchers_provider = fetchers_provider

    def curate(
        self,
        limit_per_source: int = 5,
        sources: Optional[List[str]] = None,
    ) -> List[Article]:
        from src.curator import get_source_fetchers, resolve_source

        fetchers = self._fetchers_provider() if self._fetchers_provider else get_source_fetchers()
        all_articles = []

        if sources:
            target_keys = []
            for s in sources:
                canonical = resolve_source(s)
                if canonical and canonical in fetchers:
                    if canonical not in target_keys:
                        target_keys.append(canonical)
                else:
                    print(f"Warning: Unknown source '{s}' skipped.")

            for key in target_keys:
                all_articles.extend(fetchers[key](limit=limit_per_source))
        else:
            for fetcher in fetchers.values():
                all_articles.extend(fetcher(limit=limit_per_source))

        # Filter duplicates and seen URLs in DB
        seen_urls = set()
        fresh_articles = []

        for article in all_articles:
            if article.url in seen_urls:
                continue

            # Check against database
            if db.url_exists(article.url):
                continue

            seen_urls.add(article.url)
            fresh_articles.append(article)

        return fresh_articles


_default_service = CurationService()


def curate_all(
    limit_per_source: int = 5,
    sources: Optional[List[str]] = None,
) -> List[Article]:
    """
    Curates and aggregates unseen technical articles from configured sources.

    :param limit_per_source: Maximum articles to fetch per active source.
    :param sources: Optional list of specific source identifiers or aliases to target.
                    If None or empty, all sources are fetched.
    """
    return _default_service.curate(limit_per_source=limit_per_source, sources=sources)
