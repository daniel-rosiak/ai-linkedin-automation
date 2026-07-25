import re
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

import src.db.database as db
from src.db.models import Article


def fetch_hacker_news(limit: int = 5) -> List[Article]:
    """Fetches top articles from Hacker News using the Firebase API."""
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
                Article(title=title, url=url, source="hacker_news", summary=summary, score=float(score), date=date_str)
            )
    except Exception as e:
        print(f"Error fetching Hacker News: {e}")

    return articles


def fetch_github_trending(limit: int = 5) -> List[Article]:
    """Fetches trending repositories from GitHub Trending page."""
    articles = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = "https://github.com/trending?since=daily"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.find_all("article", class_="Box-row")

        for row in rows[:limit]:
            # Extract Repo Info
            title_tag = row.find("h2", class_="h3")
            if not title_tag:
                continue

            a_tag = title_tag.find("a")
            if not a_tag:
                continue

            # Clean repository name (e.g. "/google/gemini-cli" or "google / gemini-cli")
            repo_path = a_tag.get("href", "").strip("/")
            repo_name = "/".join([part.strip() for part in repo_path.split("/")])
            repo_url = f"https://github.com/{repo_path}"

            # Extract description
            desc_tag = row.find("p", class_=re.compile("col-9|color-fg-muted"))
            description = desc_tag.get_text().strip() if desc_tag else "No description available."

            # Extract stars
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
                    source="github_trending",
                    summary=description,
                    score=stars,
                    date=datetime.now().isoformat(),
                )
            )
    except Exception as e:
        print(f"Error fetching GitHub Trending: {e}")

    return articles


def fetch_arxiv(limit: int = 5) -> List[Article]:
    """Fetches recent AI and Machine Learning papers from ArXiv API."""
    articles = []
    try:
        url = f"http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
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

            # Clean text whitespaces
            title = re.sub(r"\s+", " ", title_tag.get_text().strip())
            url_str = id_tag.get_text().strip()
            summary = re.sub(r"\s+", " ", summary_tag.get_text().strip()) if summary_tag else "No abstract available."
            published = published_tag.get_text().strip() if published_tag else None

            articles.append(
                Article(title=title, url=url_str, source="arxiv", summary=summary, score=0.0, date=published)
            )
    except Exception as e:
        print(f"Error fetching ArXiv: {e}")

    return articles


def fetch_reddit(limit: int = 5, subreddits: Optional[List[str]] = None) -> List[Article]:
    """Fetches trending posts from specified subreddits using their RSS feeds."""
    if subreddits is None:
        subreddits = ["MachineLearning", "datascience"]
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

                # Extract clean text from HTML content if present
                summary = "No description available."
                if content_tag:
                    raw_content = content_tag.get_text()
                    content_soup = BeautifulSoup(raw_content, "html.parser")
                    summary = content_soup.get_text().strip()
                    # Clean up multiple whitespaces
                    summary = re.sub(r"\s+", " ", summary)
                    # Truncate summary if too long for preview
                    if len(summary) > 300:
                        summary = summary[:297] + "..."

                published = published_tag.get_text().strip() if published_tag else None

                articles.append(
                    Article(title=title, url=url_str, source="reddit", summary=summary, score=0.0, date=published)
                )
        except Exception as e:
            print(f"Error fetching Reddit r/{sub}: {e}")

    return articles[:limit]


def fetch_lobsters(limit: int = 5) -> List[Article]:
    """Fetches hottest posts from Lobsters JSON API."""
    articles = []
    try:
        url = "https://lobste.rs/hottest.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
                Article(title=title, url=url_str, source="lobsters", summary=summary, score=score, date=date_str)
            )
    except Exception as e:
        print(f"Error fetching Lobsters: {e}")
    return articles


def fetch_infoq(limit: int = 5) -> List[Article]:
    """Fetches latest software development news from InfoQ RSS feed."""
    articles = []
    try:
        url = "https://feed.infoq.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")

        for item in items[:limit]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            desc_tag = item.find("description")
            pub_tag = item.find("pubDate")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text().strip()
            url_str = link_tag.get_text().strip()

            # Clean description text
            raw_desc = desc_tag.get_text() if desc_tag else ""
            desc_soup = BeautifulSoup(raw_desc, "html.parser")
            summary = desc_soup.get_text().strip()
            summary = re.sub(r"\s+", " ", summary)
            if len(summary) > 300:
                summary = summary[:297] + "..."

            date_str = pub_tag.get_text().strip() if pub_tag else None

            articles.append(
                Article(title=title, url=url_str, source="infoq", summary=summary, score=0.0, date=date_str)
            )
    except Exception as e:
        print(f"Error fetching InfoQ: {e}")
    return articles


def fetch_netflix_tech(limit: int = 5) -> List[Article]:
    """Fetches latest engineering articles from Netflix Tech Blog RSS feed."""
    articles = []
    try:
        url = "https://netflixtechblog.com/feed"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")

        for item in items[:limit]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            desc_tag = item.find("description") or item.find("content:encoded")
            pub_tag = item.find("pubDate")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text().strip()
            url_str = link_tag.get_text().strip()

            # Clean description text
            raw_desc = desc_tag.get_text() if desc_tag else ""
            desc_soup = BeautifulSoup(raw_desc, "html.parser")
            summary = desc_soup.get_text().strip()
            summary = re.sub(r"\s+", " ", summary)
            if len(summary) > 300:
                summary = summary[:297] + "..."

            date_str = pub_tag.get_text().strip() if pub_tag else None

            articles.append(
                Article(title=title, url=url_str, source="netflix_tech", summary=summary, score=0.0, date=date_str)
            )
    except Exception as e:
        print(f"Error fetching Netflix Tech Blog: {e}")
    return articles


def curate_all(limit_per_source: int = 5) -> List[Article]:
    """Crates and aggregates unseen technical articles from all configured sources."""
    all_articles = []

    # 1. Fetch from Hacker News
    all_articles.extend(fetch_hacker_news(limit=limit_per_source))

    # 2. Fetch from GitHub Trending
    all_articles.extend(fetch_github_trending(limit=limit_per_source))

    # 3. Fetch from ArXiv
    all_articles.extend(fetch_arxiv(limit=limit_per_source))

    # 4. Fetch from Reddit
    all_articles.extend(fetch_reddit(limit=limit_per_source))

    # 5. Fetch from Lobsters
    all_articles.extend(fetch_lobsters(limit=limit_per_source))

    # 6. Fetch from InfoQ
    all_articles.extend(fetch_infoq(limit=limit_per_source))

    # 7. Fetch from Netflix Tech Blog
    all_articles.extend(fetch_netflix_tech(limit=limit_per_source))

    # 8. Filter duplicates and seen URLs in DB
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


if __name__ == "__main__":
    print("Initializing Database...")
    db.initialize_db()

    print("Running Daily Tech Curation pipeline (fetching 2 articles per source)...")
    articles = curate_all(limit_per_source=2)

    print(f"\n--- Curated {len(articles)} Fresh, Unseen Articles ---\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. [{article.source.upper()}] {article.title}")
        print(f"   URL: {article.url}")
        print(f"   Summary: {article.summary}")
        if article.date:
            print(f"   Date: {article.date}")
        print("-" * 50)
