from typing import List, Optional

import src.config as config
import src.db.database as db
from src.curator import curate_all
from src.llm.factory import get_llm_provider


def run_generation(sources: Optional[List[str]] = None, count: int = 3):
    print("--- STEP 1: INITIALIZING DATABASE & RETRIEVING HISTORY ---")
    db.initialize_db()

    # Query learning history constraints from database
    approved_history = db.get_history("approved", limit=5)
    rejected_history = db.get_history("rejected", limit=5)
    global_feedback = db.get_preference("global_feedback")

    print(f"Loaded {len(approved_history)} approved positive styles.")
    print(f"Loaded {len(rejected_history)} rejected negative styles.")
    if global_feedback:
        print(f"Loaded Global Preference: '{global_feedback}'")

    print("\n--- STEP 2: RUNNING NEWS CURATION PIPELINE ---")
    sources_label = ", ".join(sources) if sources else "all configured sources"
    limit_per_source = max(4, count * 2) if sources else max(2, (count + 7) // 8 + 1)
    print(f"Curating articles targeting: {sources_label} (limit: {limit_per_source} per source)...")

    articles = curate_all(limit_per_source=limit_per_source, sources=sources)
    if not articles:
        print("No fresh, unseen articles found. Curation is up-to-date!")
        return

    print(f"Curated {len(articles)} fresh, unseen articles.")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. [{a.source.upper()}] {a.title}")

    print(f"\n--- STEP 3: INITIALIZING LLM PROVIDER ({config.LLM_PROVIDER.upper()}) ---")
    try:
        provider = get_llm_provider()
    except Exception as e:
        print(f"Error loading LLM provider: {e}")
        sys.exit(1)

    print(f"Generating {count} proposals via LLM...")
    try:
        proposals = provider.generate_proposals(
            articles=articles,
            approved_history=approved_history,
            rejected_history=rejected_history,
            global_feedback=global_feedback,
            count=count,
        )
    except Exception as e:
        print(f"Generation failed: {e}")
        sys.exit(1)

    print(f"\n--- SUCCESS: GENERATED {len(proposals)} POST PROPOSALS ---\n")
    for i, p in enumerate(proposals, 1):
        print(f"PROPOSAL {i}:")
        print(f"  Source Article: {p.title} ({p.url})")
        print(f"  Proposed Title: {p.proposed_title}")
        print(f"  Proposed Angle: {p.proposed_angle}")
        print("-" * 50)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Curate articles and generate LinkedIn post proposals.")
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Target specific source(s), e.g. shopify, netflix, hn, github (comma-separated).",
    )
    parser.add_argument(
        "--count",
        "-n",
        "-c",
        type=int,
        default=3,
        help="Number of proposals to generate (default: 3).",
    )
    args = parser.parse_args()

    target_sources = [s.strip() for s in args.source.split(",")] if args.source else None
    run_generation(sources=target_sources, count=args.count)
