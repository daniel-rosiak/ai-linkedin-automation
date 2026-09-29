import re
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.curator.base import BaseSourceFetcher, FeedSourceFetcher, sanitize_html_summary
from src.curator.constants import FEED_CONFIGS
from src.db.models import Article


class HackerNewsFetcher(BaseSourceFetcher):
    """Fetches top articles from Hacker News using the Firebase API."""

    source_name = "hacker_news"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            response = requests.get(top_stories_url, timeout=10)
            if response.status_code != 200:
                return []

            story_ids = response.json()[:limit]
            for story_id in story_ids:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                item_response = requests.get(item_url, timeout=5)
                if item_response.status_code != 200:
                    continue

                item_data = item_response.json()
                if not item_data:
                    continue

                title = item_data.get("title", "")
                url = item_data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                score = item_data.get("score", 0)
                time_val = item_data.get("time")
                date_str = datetime.fromtimestamp(time_val).isoformat() if time_val else None
                summary = f"Hacker News story with {score} points."

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=self.source_name,
                        summary=summary,
                        score=float(score),
                        date=date_str,
                    )
                )
        except Exception as e:
            print(f"Error fetching Hacker News: {e}")
        return articles


class GitHubTrendingFetcher(BaseSourceFetcher):
    """Fetches trending repositories from GitHub Trending page."""

    source_name = "github_trending"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            url = "https://github.com/trending?since=daily"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            rows = soup.find_all("article", class_="Box-row")

            for row in rows[:limit]:
                title_tag = row.find("h2", class_="h3")
                if not title_tag:
                    continue

                a_tag = title_tag.find("a")
                if not a_tag:
                    continue

                repo_path = a_tag.get("href", "").strip("/")
                repo_name = "/".join([part.strip() for part in repo_path.split("/")])
                repo_url = f"https://github.com/{repo_path}"

                desc_tag = row.find("p", class_=re.compile("col-9|color-fg-muted"))
                description = desc_tag.get_text().strip() if desc_tag else "No description available."

                stars = 0.0
                stars_tag = row.find("a", href=re.compile("stargazers"))
                if stars_tag:
                    stars_text = stars_tag.get_text().strip().replace(",", "")
                    try:
                        stars = float(re.findall(r"\d+", stars_text)[0])
                    except Exception:
                        pass

                articles.append(
                    Article(
                        title=repo_name,
                        url=repo_url,
                        source=self.source_name,
                        summary=description,
                        score=stars,
                        date=datetime.now().isoformat(),
                    )
                )
        except Exception as e:
            print(f"Error fetching GitHub Trending: {e}")
        return articles


class ArxivFetcher(BaseSourceFetcher):
    """Fetches recent AI and Machine Learning papers from ArXiv API."""

    source_name = "arxiv"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            url = (
                f"http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG"
                f"&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
            )
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "xml")
            entries = soup.find_all("entry")

            for entry in entries:
                id_tag = entry.find("id")
                title_tag = entry.find("title")
                summary_tag = entry.find("summary")
                published_tag = entry.find("published")

                if not id_tag or not title_tag:
                    continue

                title = re.sub(r"\s+", " ", title_tag.get_text().strip())
                url_str = id_tag.get_text().strip()
                summary = re.sub(r"\s+", " ", summary_tag.get_text().strip()) if summary_tag else "No abstract available."
                published = published_tag.get_text().strip() if published_tag else None

                articles.append(
                    Article(
                        title=title,
                        url=url_str,
                        source=self.source_name,
                        summary=summary,
                        score=0.0,
                        date=published,
                    )
                )
        except Exception as e:
            print(f"Error fetching ArXiv: {e}")
        return articles


class RedditFetcher(BaseSourceFetcher):
    """Fetches trending posts from specified subreddits using their RSS feeds."""

    source_name = "reddit"

    def fetch(self, limit: int = 5, subreddits: Optional[List[str]] = None) -> List[Article]:
        if subreddits is None:
            subreddits = [
                "MachineLearning",
                "datascience",
                "ArtificialIntelligence",
                "softwarearchitecture",
            ]
        articles = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}.rss"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "xml")
                entries = soup.find_all("entry")

                for entry in entries[:limit]:
                    title_tag = entry.find("title")
                    link_tag = entry.find("link")
                    content_tag = entry.find("content") or entry.find("summary")
                    published_tag = entry.find("published")

                    if not title_tag or not link_tag:
                        continue

                    title = title_tag.get_text().strip()
                    url_str = link_tag.get("href", "").strip()

                    summary = "No description available."
                    if content_tag:
                        raw_content = content_tag.get_text()
                        summary = sanitize_html_summary(raw_content, max_length=300)

                    published = published_tag.get_text().strip() if published_tag else None

                    articles.append(
                        Article(
                            title=title,
                            url=url_str,
                            source=self.source_name,
                            summary=summary,
                            score=0.0,
                            date=published,
                        )
                    )
            except Exception as e:
                print(f"Error fetching Reddit r/{sub}: {e}")

        return articles[:limit]


class LobstersFetcher(BaseSourceFetcher):
    """Fetches hottest posts from Lobsters JSON API."""

    source_name = "lobsters"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            url = "https://lobste.rs/hottest.json"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return []

            items = response.json()
            for item in items[:limit]:
                title = item.get("title", "").strip()
                url_str = item.get("url") or item.get("short_id_url")
                score = float(item.get("score", 0))
                date_str = item.get("created_at")
                summary = f"Lobsters story with a score of {int(score)}."

                articles.append(
                    Article(
                        title=title,
                        url=url_str,
                        source=self.source_name,
                        summary=summary,
                        score=score,
                        date=date_str,
                    )
                )
        except Exception as e:
            print(f"Error fetching Lobsters: {e}")
        return articles


class InfoQFetcher(FeedSourceFetcher):
    """Fetches latest software development news from InfoQ RSS feed."""

    def __init__(self):
        super().__init__(source_name="infoq", feed_url=FEED_CONFIGS["infoq"])


# Standalone function wrappers for direct invocation and backwards compatibility
_hn_fetcher = HackerNewsFetcher()
_gh_fetcher = GitHubTrendingFetcher()
_arxiv_fetcher = ArxivFetcher()
_reddit_fetcher = RedditFetcher()
_lobsters_fetcher = LobstersFetcher()
_infoq_fetcher = InfoQFetcher()


def fetch_hacker_news(limit: int = 5) -> List[Article]:
    return _hn_fetcher.fetch(limit=limit)


def fetch_github_trending(limit: int = 5) -> List[Article]:
    return _gh_fetcher.fetch(limit=limit)


def fetch_arxiv(limit: int = 5) -> List[Article]:
    return _arxiv_fetcher.fetch(limit=limit)


def fetch_reddit(limit: int = 5, subreddits: Optional[List[str]] = None) -> List[Article]:
    return _reddit_fetcher.fetch(limit=limit, subreddits=subreddits)


def fetch_lobsters(limit: int = 5) -> List[Article]:
    return _lobsters_fetcher.fetch(limit=limit)


def fetch_infoq(limit: int = 5) -> List[Article]:
    return _infoq_fetcher.fetch(limit=limit)
