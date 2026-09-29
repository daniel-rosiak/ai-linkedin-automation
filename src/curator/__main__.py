import argparse

import src.db.database as db
from src.curator.service import curate_all


def main():
    parser = argparse.ArgumentParser(description="Run the news & tech article curation pipeline.")
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Target a specific source or comma-separated sources (e.g. shopify, netflix, hn, github).",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=2,
        help="Number of articles to fetch per source (default: 2).",
    )
    args = parser.parse_args()

    print("Initializing Database...")
    db.initialize_db()

    target_sources = [s.strip() for s in args.source.split(",")] if args.source else None
    sources_label = ", ".join(target_sources) if target_sources else "all configured sources"
    print(f"Running Tech Curation pipeline for {sources_label} (limit: {args.limit} per source)...")
    articles = curate_all(limit_per_source=args.limit, sources=target_sources)

    print(f"\n--- Curated {len(articles)} Fresh, Unseen Articles ---\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. [{article.source.upper()}] {article.title}")
        print(f"   URL: {article.url}")
        print(f"   Summary: {article.summary}")
        if article.date:
            print(f"   Date: {article.date}")
        print("-" * 50)


if __name__ == "__main__":
    main()
