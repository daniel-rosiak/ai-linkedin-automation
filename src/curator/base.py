import re
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.db.models import Article


def sanitize_html_summary(raw_html: str, max_length: int = 300) -> str:
    """Strips HTML tags, collapses whitespaces, and truncates text to max_length."""
    if not raw_html:
        return "No description available."
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text().strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text or "No description available."


class BaseSourceFetcher(ABC):
    """Abstract base class for all technical news and blog fetchers."""

    source_name: str

    @abstractmethod
    def fetch(self, limit: int = 5) -> List[Article]:
        """Fetches up to `limit` articles from this source."""
        pass


class FeedSourceFetcher(BaseSourceFetcher):
    """Generic parser and fetcher for RSS 2.0 and Atom XML feeds."""

    def __init__(
        self,
        source_name: str,
        feed_url: str,
        custom_headers: Optional[dict] = None,
        timeout: int = 10,
    ):
        self.source_name = source_name
        self.feed_url = feed_url
        self.custom_headers = custom_headers
        self.timeout = timeout

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            }
            if self.custom_headers:
                headers.update(self.custom_headers)

            response = requests.get(self.feed_url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "xml")
            items = soup.find_all("item")
            if not items:
                items = soup.find_all("entry")

            for item in items[:limit]:
                title_tag = item.find("title")
                link_tag = item.find("link")
                guid_tag = item.find("guid") or item.find("id")
                desc_tag = (
                    item.find("description")
                    or item.find("summary")
                    or item.find("content:encoded")
                    or item.find("content")
                )
                pub_tag = (
                    item.find("pubDate")
                    or item.find("published")
                    or item.find("updated")
                    or item.find("dc:date")
                )

                if not title_tag:
                    continue

                title = title_tag.get_text().strip()
                url_str = ""
                if link_tag:
                    url_str = link_tag.get("href", "").strip() or link_tag.get_text().strip()
                if not url_str and guid_tag:
                    val = guid_tag.get_text().strip()
                    if val.startswith("http"):
                        url_str = val

                if not url_str:
                    continue

                raw_desc = desc_tag.get_text() if desc_tag else ""
                summary = sanitize_html_summary(raw_desc, max_length=300)
                date_str = pub_tag.get_text().strip() if pub_tag else None

                articles.append(
                    Article(
                        title=title,
                        url=url_str,
                        source=self.source_name,
                        summary=summary,
                        score=0.0,
                        date=date_str,
                    )
                )
        except Exception as e:
            print(f"Error fetching {self.source_name} feed ({self.feed_url}): {e}")
        return articles


def _fetch_rss_or_atom(
    url: str,
    source_name: str,
    limit: int = 5,
    custom_headers: Optional[dict] = None,
) -> List[Article]:
    """Helper function preserving previous RSS/Atom function interface."""
    return FeedSourceFetcher(source_name=source_name, feed_url=url, custom_headers=custom_headers).fetch(limit=limit)
