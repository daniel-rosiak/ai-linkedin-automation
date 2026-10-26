from unittest.mock import Mock, patch

import pytest

import src.db.database as db
from src.curator import (
    curate_all,
    fetch_arxiv,
    fetch_github_trending,
    fetch_hacker_news,
    fetch_infoq,
    fetch_lobsters,
    fetch_netflix_tech,
    fetch_reddit,
    fetch_shopify_blog,
    resolve_source,
)
from src.db.models import Article, Proposal


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    # Use a temporary database file for each test
    test_db_file = str(tmp_path / "test_curator_history.db")
    monkeypatch.setattr(db, "DATABASE_PATH", test_db_file)
    db.initialize_db()
    yield


def test_fetch_hacker_news_success():
    # Mock requests.get for top stories and item details
    # Hacker News Firebase API workflow:
    # 1. GET https://hacker-news.firebaseio.com/v0/topstories.json
    # 2. GET https://hacker-news.firebaseio.com/v0/item/{id}.json

    mock_top_stories_response = Mock()
    mock_top_stories_response.json.return_index = [12345]
    mock_top_stories_response.json.return_value = [12345]
    mock_top_stories_response.status_code = 200

    mock_item_response = Mock()
    mock_item_response.json.return_value = {
        "id": 12345,
        "title": "Quantum Computing breakthrough in 2026",
        "url": "https://example.com/quantum",
        "score": 150,
        "time": 1784841600,
    }
    mock_item_response.status_code = 200

    def side_effect(url, *args, **kwargs):
        if "topstories.json" in url:
            return mock_top_stories_response
        elif "item/12345.json" in url:
            return mock_item_response
        return Mock(status_code=404)

    with patch("requests.get", side_effect=side_effect):
        articles = fetch_hacker_news(limit=1)

        assert len(articles) == 1
        assert articles[0].title == "Quantum Computing breakthrough in 2026"
        assert articles[0].url == "https://example.com/quantum"
        assert articles[0].source == "hacker_news"
        assert "150 points" in articles[0].summary


def test_fetch_github_trending_success():
    mock_html = """
    <html>
      <body>
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/google/gemini-cli">
              google /
              gemini-cli
            </a>
          </h2>
          <p class="col-9 color-fg-muted my-1 pr-4">An interactive CLI agent specializing in software engineering tasks.</p>
          <div class="f6 color-fg-muted mt-2">
            <span class="d-inline-block mr-3">Python</span>
            <a href="/google/gemini-cli/stargazers" class="Link--muted d-inline-block mr-3">
              1,234 stars
            </a>
          </div>
        </article>
      </body>
    </html>
    """
    mock_response = Mock()
    mock_response.text = mock_html
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_github_trending(limit=1)

        assert len(articles) == 1
        assert articles[0].title == "google/gemini-cli"
        assert articles[0].url == "https://github.com/google/gemini-cli"
        assert articles[0].source == "github_trending"
        assert "CLI agent" in articles[0].summary
        assert articles[0].score == 1234.0


def test_fetch_arxiv_success():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2607.12345v1</id>
        <title>  Scaling Laws for Autonomous LinkedIn Posting Agents  </title>
        <summary>  In this paper, we present the scaling behavior of autonomous agents on social networks...  </summary>
        <published>2026-07-24T12:00:00Z</published>
      </entry>
    </feed>
    """
    mock_response = Mock()
    mock_response.text = mock_xml
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_arxiv(limit=1)

        assert len(articles) == 1
        assert articles[0].title == "Scaling Laws for Autonomous LinkedIn Posting Agents"
        assert articles[0].url == "http://arxiv.org/abs/2607.12345v1"
        assert articles[0].source == "arxiv"
        assert "scaling behavior" in articles[0].summary
        assert articles[0].date == "2026-07-24T12:00:00Z"


def test_fetch_reddit_success():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>New AI framework surpasses human performance on standard tasks</title>
        <link href="https://www.reddit.com/r/MachineLearning/comments/123/new_ai_framework/"/>
        <content type="html">&lt;p&gt;Check out this new framework that sets new state of the art results...&lt;/p&gt;</content>
        <published>2026-07-24T10:00:00Z</published>
      </entry>
    </feed>
    """
    mock_response = Mock()
    mock_response.text = mock_xml
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_reddit(limit=1, subreddits=["MachineLearning"])

        assert len(articles) == 1
        assert articles[0].title == "New AI framework surpasses human performance on standard tasks"
        assert articles[0].url == "https://www.reddit.com/r/MachineLearning/comments/123/new_ai_framework/"
        assert articles[0].source == "reddit"
        assert "new framework" in articles[0].summary
        assert articles[0].date == "2026-07-24T10:00:00Z"


def test_curate_all_success():
    # Save a dummy proposal in the database to simulate an existing/unseen article filter
    existing_p = Proposal(
        id=None,
        url="https://github.com/google/gemini-cli",
        title="google/gemini-cli",
        source="github_trending",
        summary="Description",
        proposed_title="Proposed",
        proposed_angle="Angle",
        status="approved",
    )
    db.save_proposal(existing_p)

    mock_hn = [Article(title="T1", url="https://news.ycombinator.com/item?id=1", source="hacker_news", summary="S1")]
    mock_gh = [
        Article(
            title="google/gemini-cli",
            url="https://github.com/google/gemini-cli",
            source="github_trending",
            summary="S2",
        )
    ]
    mock_arxiv = [Article(title="T3", url="http://arxiv.org/abs/1", source="arxiv", summary="S3")]
    mock_reddit = [Article(title="T4", url="https://reddit.com/r/ML/1", source="reddit", summary="S4")]

    mock_fetchers = {
        "hacker_news": lambda limit: mock_hn,
        "github_trending": lambda limit: mock_gh,
        "arxiv": lambda limit: mock_arxiv,
        "reddit": lambda limit: mock_reddit,
    }

    with patch("src.curator.get_source_fetchers", return_value=mock_fetchers):
        curated = curate_all(limit_per_source=1)

        assert len(curated) == 3
        urls = {a.url for a in curated}
        assert "https://news.ycombinator.com/item?id=1" in urls
        assert "http://arxiv.org/abs/1" in urls
        assert "https://reddit.com/r/ML/1" in urls
        assert "https://github.com/google/gemini-cli" not in urls  # Filtered out because it's in DB


def test_fetch_lobsters_success():
    mock_json = [
        {
            "title": "Why we rewrote our database in Zig",
            "url": "https://example.com/zig-db",
            "score": 45,
            "created_at": "2026-07-24T08:00:00Z",
        }
    ]
    mock_response = Mock()
    mock_response.json.return_value = mock_json
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_lobsters(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "Why we rewrote our database in Zig"
        assert articles[0].url == "https://example.com/zig-db"
        assert articles[0].source == "lobsters"
        assert "score of 45" in articles[0].summary
        assert articles[0].date == "2026-07-24T08:00:00Z"


def test_fetch_infoq_success():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>New Java features in JDK 27</title>
          <link>https://www.infoq.com/news/jdk-27/</link>
          <description>Exploring virtual thread optimizations in JDK 27.</description>
          <pubDate>Fri, 24 Jul 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    mock_response = Mock()
    mock_response.text = mock_xml
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_infoq(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "New Java features in JDK 27"
        assert articles[0].url == "https://www.infoq.com/news/jdk-27/"
        assert articles[0].source == "infoq"
        assert "JDK 27" in articles[0].summary
        assert articles[0].date == "Fri, 24 Jul 2026 12:00:00 GMT"


def test_fetch_netflix_tech_success():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Netflix's High-Scale Key-Value Store Migration</title>
          <link>https://netflixtechblog.com/kv-store-migration-123</link>
          <description>A behind the scenes look at migrating live cassandra workloads...</description>
          <pubDate>Thu, 23 Jul 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    mock_response = Mock()
    mock_response.text = mock_xml
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_netflix_tech(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "Netflix's High-Scale Key-Value Store Migration"
        assert articles[0].url == "https://netflixtechblog.com/kv-store-migration-123"
        assert articles[0].source == "netflix_tech"
        assert "cassandra workloads" in articles[0].summary
        assert articles[0].date == "Thu, 23 Jul 2026 10:00:00 GMT"


def test_fetch_shopify_blog_success():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Helix: The internal tool powering our Shopify app's native migration</title>
        <id>https://shopify.engineering/helix</id>
        <link rel="alternate" type="text/html" href="https://shopify.engineering/helix" />
        <published>2026-09-21T21:12:33.000Z</published>
        <summary>We built Helix to help LLMs rebuild the Shopify app in Swift and Kotlin, using small checkpoints and strict quality gates.</summary>
      </entry>
    </feed>
    """
    mock_response = Mock()
    mock_response.text = mock_xml
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        articles = fetch_shopify_blog(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "Helix: The internal tool powering our Shopify app's native migration"
        assert articles[0].url == "https://shopify.engineering/helix"
        assert articles[0].source == "shopify_blog"
        assert "Helix" in articles[0].summary
        assert articles[0].date == "2026-09-21T21:12:33.000Z"


def test_resolve_source():
    assert resolve_source("shopify") == "shopify_blog"
    assert resolve_source("shopify_blog") == "shopify_blog"
    assert resolve_source("Shopify-Engineering") == "shopify_blog"
    assert resolve_source("netflix") == "netflix_tech"
    assert resolve_source("hn") == "hacker_news"
    assert resolve_source("github") == "github_trending"
    assert resolve_source("arxiv") == "arxiv"
    assert resolve_source("reddit") == "reddit"
    assert resolve_source("lobsters") == "lobsters"
    assert resolve_source("infoq") == "infoq"
    # New engineering blogs
    assert resolve_source("cloudflare") == "cloudflare_blog"
    assert resolve_source("cf") == "cloudflare_blog"
    assert resolve_source("stripe") == "stripe_blog"
    assert resolve_source("meta") == "meta_engineering"
    assert resolve_source("facebook") == "meta_engineering"
    assert resolve_source("uber") == "uber_engineering"
    assert resolve_source("airbnb") == "airbnb_engineering"
    assert resolve_source("github_engineering") == "github_engineering"
    assert resolve_source("dropbox") == "dropbox_tech"
    assert resolve_source("atlassian") == "atlassian_engineering"
    assert resolve_source("slack") == "slack_engineering"
    assert resolve_source("spotify") == "spotify_engineering"
    assert resolve_source("linkedin") == "linkedin_engineering"
    assert resolve_source("pinterest") == "pinterest_engineering"
    assert resolve_source("google") == "google_developers"
    assert resolve_source("microsoft") == "microsoft_engineering"
    assert resolve_source("etsy") == "etsy_craft"
    assert resolve_source("square") == "square_corner"
    assert resolve_source("figma") == "figma_tech"
    assert resolve_source("stackoverflow") == "stackoverflow_engineering"
    assert resolve_source("unknown_xyz") is None
    assert resolve_source("") is None


def test_curate_all_with_specific_sources():
    mock_shopify = [
        Article(
            title="Shopify High Scale",
            url="https://shopify.engineering/high-scale",
            source="shopify_blog",
            summary="Shopify blog summary",
        )
    ]
    mock_netflix = [
        Article(
            title="Netflix CDN",
            url="https://netflixtechblog.com/cdn",
            source="netflix_tech",
            summary="Netflix tech summary",
        )
    ]

    with (
        patch("src.curator.fetch_shopify_blog", return_value=mock_shopify) as p_shopify,
        patch("src.curator.fetch_netflix_tech", return_value=mock_netflix) as p_netflix,
        patch("src.curator.fetch_hacker_news") as p_hn,
    ):
        curated = curate_all(limit_per_source=2, sources=["shopify", "netflix"])
        assert len(curated) == 2
        p_shopify.assert_called_once_with(limit=2)
        p_netflix.assert_called_once_with(limit=2)
        p_hn.assert_not_called()


def test_fetch_uber_engineering_success():
    mock_hn_response = Mock()
    mock_hn_response.status_code = 200
    mock_hn_response.json.return_value = {
        "hits": [
            {
                "title": "Zero-Growth Stack, Real Gains: Go at Uber",
                "url": "https://www.uber.com/us/en/blog/zero-growth-stack/",
                "author": "uber_eng",
                "created_at": "2026-05-07T12:00:00Z",
                "points": 340,
            },
            {
                "title": "Random irrelevant story",
                "url": "https://other.com/story",
                "author": "someone",
                "points": 50,
            },
        ]
    }

    with patch("requests.get", return_value=mock_hn_response):
        from src.curator import fetch_uber_engineering

        articles = fetch_uber_engineering(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "Zero-Growth Stack, Real Gains: Go at Uber"
        assert articles[0].url == "https://www.uber.com/us/en/blog/zero-growth-stack/"
        assert articles[0].source == "uber_engineering"
        assert articles[0].score == 340.0


def test_fetch_linkedin_engineering_fallback():
    mock_hn_response = Mock()
    mock_hn_response.status_code = 200
    mock_hn_response.json.return_value = {
        "hits": [
            {
                "title": "Reimagining LinkedIn Search Stack",
                "url": "https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack",
                "author": "linkedin_dev",
                "created_at": "2026-06-01T10:00:00Z",
                "points": 210,
            }
        ]
    }

    # Simulate Playwright raising exception so it exercises fallback
    with patch("playwright.sync_api.sync_playwright", side_effect=Exception("Playwright disabled in unit test")):
        with patch("requests.get", return_value=mock_hn_response):
            from src.curator import fetch_linkedin_engineering

            articles = fetch_linkedin_engineering(limit=1)
            assert len(articles) == 1
            assert articles[0].title == "Reimagining LinkedIn Search Stack"
            assert "linkedin.com/blog/engineering" in articles[0].url
            assert articles[0].source == "linkedin_engineering"


@pytest.mark.asyncio
async def test_fetch_linkedin_engineering_inside_asyncio_loop():
    import asyncio

    from src.curator import fetch_linkedin_engineering

    # Verify that when sync_playwright is invoked inside fetch_linkedin_engineering while an
    # asyncio event loop is active in the caller thread, it runs in a worker thread with NO running loop.
    def fake_sync_playwright():
        try:
            asyncio.get_running_loop()
            raise AssertionError("It looks like you are using Playwright Sync API inside the asyncio loop.")
        except RuntimeError:
            pass

        ctx = Mock()
        browser = Mock()
        page = Mock()
        page.evaluate.return_value = [
            {
                "title": "Scaling LinkedIn's Graph Database",
                "url": "https://www.linkedin.com/blog/engineering/data/scaling-graph-db",
            }
        ]
        browser.new_page.return_value = page
        ctx.chromium.launch.return_value = browser
        cm = Mock()
        cm.__enter__ = Mock(return_value=ctx)
        cm.__exit__ = Mock(return_value=False)
        return cm

    with patch("playwright.sync_api.sync_playwright", side_effect=fake_sync_playwright):
        articles = fetch_linkedin_engineering(limit=1)
        assert len(articles) == 1
        assert articles[0].title == "Scaling LinkedIn's Graph Database"
        assert articles[0].url == "https://www.linkedin.com/blog/engineering/data/scaling-graph-db"
        assert articles[0].source == "linkedin_engineering"


def test_find_similar_articles_ranks_and_deduplicates():
    from src.curator import find_similar_articles
    from src.db.models import Proposal

    target = Proposal(
        id=1,
        url="https://netflixtechblog.com/cassandra-migration",
        title="Netflix Cassandra Key-Value Store Migration",
        source="netflix_tech",
        summary="Migrating distributed Cassandra clusters with zero downtime and strict latency SLOs.",
        proposed_title="How Netflix Migrates Cassandra Clusters",
        proposed_angle="Zero-downtime distributed database migration lessons.",
        status="approved",
    )

    candidates = [
        # Exact same URL as target -> should be excluded
        Article(
            title="Netflix Cassandra Key-Value Store Migration",
            url="https://netflixtechblog.com/cassandra-migration",
            source="netflix_tech",
            summary="Same article",
        ),
        # High similarity (distributed database / Cassandra migration)
        Article(
            title="Zero-Downtime Cassandra Cluster Upgrades at Uber",
            url="https://uber.com/cassandra-upgrades",
            source="uber_engineering",
            summary="How Uber upgrades distributed Cassandra clusters while maintaining latency SLOs.",
        ),
        # Duplicate URL of the high-similarity candidate -> should be deduplicated
        Article(
            title="Zero-Downtime Cassandra Cluster Upgrades at Uber (Duplicate)",
            url="https://uber.com/cassandra-upgrades",
            source="hacker_news",
            summary="Duplicate link",
        ),
        # Medium similarity (database migration / latency)
        Article(
            title="Stripe's Zero-Downtime Database Migration Engine",
            url="https://stripe.com/blog/db-migration",
            source="stripe_blog",
            summary="Moving petabytes across shards without breaking API latency.",
        ),
        # Unrelated topic
        Article(
            title="CSS Grid Layout Techniques for Mobile",
            url="https://example.com/css-grid",
            source="infoq",
            summary="Styling responsive web interfaces with modern CSS.",
        ),
    ]

    similar = find_similar_articles(target, candidates, limit=2)
    assert len(similar) == 2
    assert similar[0].url == "https://uber.com/cassandra-upgrades"
    assert similar[1].url == "https://stripe.com/blog/db-migration"


def test_gather_similar_articles_combines_db_and_curated():
    from src.curator import gather_similar_articles
    from src.db.models import Proposal

    target = Proposal(
        id=10,
        url="https://cloudflare.com/rust-proxy",
        title="Replacing Nginx with a Rust Proxy at Cloudflare",
        source="cloudflare_blog",
        summary="Memory safety and tail latency improvements with Pingora in Rust.",
        proposed_title="Why Cloudflare Replaced Nginx with Rust",
        proposed_angle="Tail latency and memory safety in edge proxies.",
        status="approved",
    )

    saved_prop = Proposal(
        id=9,
        url="https://dropbox.tech/rust-sync",
        title="Rewriting our Sync Engine in Rust",
        source="dropbox_tech",
        summary="Improving memory safety and tail latency in Dropbox desktop clients.",
        proposed_title="Dropbox's Rust Rewrite",
        proposed_angle="Rust in production.",
        status="approved",
    )

    fresh_article = Article(
        title="Discord Switched from Go to Rust for Read States",
        url="https://discord.com/rust-read-states",
        source="hacker_news",
        summary="Eliminating GC latency spikes with Rust memory management.",
    )

    with (
        patch("src.db.database.get_all_history", return_value=[target, saved_prop]) as mock_hist,
        patch("src.curator.similarity.curate_all", return_value=[fresh_article]) as mock_curate,
    ):
        results = gather_similar_articles(target, limit=2, limit_per_source=1)
        mock_hist.assert_called_once_with(limit=50)
        mock_curate.assert_called_once_with(limit_per_source=1)
        assert len(results) == 2
        urls = {a.url for a in results}
        assert "https://dropbox.tech/rust-sync" in urls
        assert "https://discord.com/rust-read-states" in urls
        assert "https://cloudflare.com/rust-proxy" not in urls
