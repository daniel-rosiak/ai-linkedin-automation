import re
from typing import List, Union

import src.db.database as db
from src.curator.constants import SOURCE_CATEGORY_MAP
from src.curator.service import curate_all
from src.db.models import Article, Proposal

_STOPWORDS = frozenset(
    {
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "also",
        "and",
        "any",
        "are",
        "article",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "blog",
        "both",
        "build",
        "building",
        "but",
        "can",
        "could",
        "did",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "here",
        "how",
        "into",
        "its",
        "just",
        "like",
        "make",
        "making",
        "more",
        "most",
        "new",
        "nor",
        "not",
        "now",
        "off",
        "once",
        "only",
        "other",
        "our",
        "out",
        "over",
        "own",
        "post",
        "points",
        "published",
        "read",
        "same",
        "score",
        "should",
        "some",
        "such",
        "Submitted",
        "submitted",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "too",
        "under",
        "until",
        "use",
        "using",
        "very",
        "was",
        "way",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)


def _extract_tokens(text: str) -> List[str]:
    if not text:
        return []
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS and not w.isdigit()]


def _score_candidate(target: Union[Proposal, Article], candidate: Article) -> float:
    target_title_parts = [target.title or ""]
    target_body_parts = [target.summary or ""]
    if isinstance(target, Proposal):
        target_title_parts.append(target.proposed_title or "")
        target_body_parts.append(target.proposed_angle or "")

    target_title_tokens = set(_extract_tokens(" ".join(target_title_parts)))
    target_all_tokens = target_title_tokens | set(_extract_tokens(" ".join(target_body_parts)))

    cand_title_tokens = set(_extract_tokens(candidate.title or ""))
    cand_all_tokens = cand_title_tokens | set(_extract_tokens(candidate.summary or ""))

    if not target_all_tokens or not cand_all_tokens:
        return 0.0

    # Weighted token overlap: title matches count more than body matches
    shared_all = target_all_tokens & cand_all_tokens
    shared_title = target_title_tokens & cand_title_tokens

    if not shared_all:
        return 0.0

    union_size = len(target_all_tokens | cand_all_tokens)
    jaccard = len(shared_all) / union_size if union_size else 0.0
    title_bonus = 0.15 * len(shared_title)

    # Bigram overlap bonus for technical phrases (e.g. "distributed systems", "rust compiler")
    target_ordered = _extract_tokens(" ".join(target_title_parts + target_body_parts))
    cand_ordered = _extract_tokens(f"{candidate.title or ''} {candidate.summary or ''}")
    target_bigrams = set(zip(target_ordered, target_ordered[1:], strict=False))
    cand_bigrams = set(zip(cand_ordered, cand_ordered[1:], strict=False))
    bigram_bonus = 0.2 * len(target_bigrams & cand_bigrams)

    # Small category affinity tie-breaker when substantive keyword overlap already exists
    target_cat = SOURCE_CATEGORY_MAP.get((target.source or "").lower())
    cand_cat = SOURCE_CATEGORY_MAP.get((candidate.source or "").lower())
    category_bonus = 0.05 if (target_cat and target_cat == cand_cat) else 0.0

    return jaccard + title_bonus + bigram_bonus + category_bonus


def find_similar_articles(
    target: Union[Proposal, Article],
    candidates: List[Article],
    limit: int = 3,
) -> List[Article]:
    """
    Ranks candidate articles by topical similarity to the target proposal/article
    and returns up to `limit` best matches (excluding the target's own URL).
    """
    if limit <= 0 or not candidates:
        return []

    target_url = (target.url or "").strip()
    seen_urls = {target_url} if target_url else set()
    unique_candidates: List[Article] = []

    for article in candidates:
        url = (article.url or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_candidates.append(article)

    if not unique_candidates:
        return []

    scored = [(_score_candidate(target, cand), idx, cand) for idx, cand in enumerate(unique_candidates)]
    positive_matches = [item for item in scored if item[0] > 0.0]

    if positive_matches:
        # Sort by similarity descending, preserving original order on ties
        positive_matches.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in positive_matches[:limit]]

    # Fallback: if no candidate shared tokens (e.g. minimal test stubs), return top unique candidates
    return unique_candidates[:limit]


def gather_similar_articles(
    proposal: Proposal,
    limit: int = 3,
    limit_per_source: int = 2,
) -> List[Article]:
    """
    Gathers candidate articles from both saved database history and fresh curated feeds,
    then returns the top `limit` articles most similar to `proposal`.
    """
    candidates: List[Article] = []

    # 1. Load saved proposals from SQLite history
    try:
        history_items = db.get_all_history(limit=50)
        for item in history_items:
            if item.url and item.url != proposal.url:
                summary_text = item.summary or item.proposed_angle or ""
                candidates.append(
                    Article(
                        title=item.title or item.proposed_title or "Untitled",
                        url=item.url,
                        source=item.source or "unknown",
                        summary=summary_text,
                    )
                )
    except Exception as e:
        print(f"Warning: Failed to load history for similarity search: {e}")

    # 2. Fetch fresh curated articles across sources
    try:
        fresh_articles = curate_all(limit_per_source=limit_per_source)
        candidates.extend(fresh_articles)
    except Exception as e:
        print(f"Warning: Failed to curate fresh articles for similarity search: {e}")

    return find_similar_articles(proposal, candidates, limit=limit)
