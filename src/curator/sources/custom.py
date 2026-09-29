from typing import List

import requests

from src.curator.base import BaseSourceFetcher
from src.db.models import Article


class UberEngineeringFetcher(BaseSourceFetcher):
    """
    Fetches latest engineering articles from Uber.
    Note: Uber website uses Cloudflare/Bot protection and has no public RSS feed.
    We query the Hacker News Algolia API for high-quality indexed Uber Engineering articles.
    """

    source_name = "uber_engineering"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        try:
            url = f"https://hn.algolia.com/api/v1/search?query=uber.com/blog/&tags=story&hitsPerPage={limit * 2}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                seen = set()
                for hit in response.json().get("hits", []):
                    hit_url = hit.get("url") or ""
                    if "uber.com" in hit_url and hit_url not in seen:
                        seen.add(hit_url)
                        author = hit.get("author") or "Uber Engineering"
                        score = float(hit.get("points") or 0.0)
                        articles.append(
                            Article(
                                title=hit.get("title", "").strip(),
                                url=hit_url,
                                source=self.source_name,
                                summary=f"Uber Engineering story by {author}. Score: {int(score)}",
                                score=score,
                                date=hit.get("created_at"),
                            )
                        )
                        if len(articles) >= limit:
                            break
        except Exception as e:
            print(f"Error fetching Uber Engineering via Algolia: {e}")
        return articles


class LinkedInEngineeringFetcher(BaseSourceFetcher):
    """
    Fetches latest engineering articles from LinkedIn Engineering blog.
    Uses Playwright to render the official blog index with an instant Algolia fallback.
    """

    source_name = "linkedin_engineering"

    def fetch(self, limit: int = 5) -> List[Article]:
        articles = []
        # Primary: Playwright scraper for official blog index
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("https://engineering.linkedin.com/blog", wait_until="domcontentloaded", timeout=12000)
                page.wait_for_timeout(2000)
                cards = page.evaluate(
                    """() => {
                    const res = [];
                    document.querySelectorAll('a').forEach(a => {
                        const h = a.querySelector('h3, h4, h5') || a;
                        const text = (h.innerText || '').trim();
                        const href = a.href || '';
                        if (href.includes('/blog/engineering/') && !href.endsWith('/engineering') && text.length > 20) {
                            const parts = href.replace('https://', '').replace('http://', '').split('/').filter(Boolean);
                            if (parts.length >= 5 && !res.some(r => r.url === href)) {
                                res.push({title: text, url: href});
                            }
                        }
                    });
                    return res;
                }"""
                )
                browser.close()
                for c in cards[:limit]:
                    articles.append(
                        Article(
                            title=c["title"],
                            url=c["url"],
                            source=self.source_name,
                            summary="Engineering and infrastructure insights from LinkedIn Engineering.",
                            score=0.0,
                            date=None,
                        )
                    )
        except Exception as e:
            print(f"Playwright scraping for LinkedIn Engineering failed ({e}), using Algolia fallback...")

        # Fallback: Query Hacker News Algolia if Playwright yielded no articles
        if not articles:
            try:
                url = f"https://hn.algolia.com/api/v1/search?query=linkedin.com/blog/engineering&tags=story&hitsPerPage={limit * 2}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    seen = set()
                    for hit in response.json().get("hits", []):
                        hit_url = hit.get("url") or ""
                        if "linkedin.com" in hit_url and hit_url not in seen:
                            seen.add(hit_url)
                            articles.append(
                                Article(
                                    title=hit.get("title", "").strip(),
                                    url=hit_url,
                                    source=self.source_name,
                                    summary="LinkedIn Engineering article.",
                                    score=float(hit.get("points") or 0.0),
                                    date=hit.get("created_at"),
                                )
                            )
                            if len(articles) >= limit:
                                break
            except Exception as e:
                print(f"Error fetching LinkedIn Engineering fallback: {e}")

        return articles


_uber_fetcher = UberEngineeringFetcher()
_linkedin_fetcher = LinkedInEngineeringFetcher()


def fetch_uber_engineering(limit: int = 5) -> List[Article]:
    return _uber_fetcher.fetch(limit=limit)


def fetch_linkedin_engineering(limit: int = 5) -> List[Article]:
    return _linkedin_fetcher.fetch(limit=limit)
