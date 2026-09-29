import pytest

import src.db.database as db
from src.db.models import Proposal


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    # Use a temporary database file for each test
    test_db_file = str(tmp_path / "test_history.db")
    monkeypatch.setattr(db, "DATABASE_PATH", test_db_file)

    # Initialize the database
    db.initialize_db()
    yield


def test_initialize_db():
    # Verify tables are created correctly
    with db.get_db_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proposals'")
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "proposals"


def test_url_exists():
    url = "https://example.com/ai-news"
    assert not db.url_exists(url)

    p = Proposal(
        id=None,
        url=url,
        title="AI Breakthrough",
        source="hacker_news",
        summary="A major AI breakthrough happened today.",
        proposed_title="The AI Revolution",
        proposed_angle="Discussing the impact of the breakthrough.",
        status="pending",
    )
    db.save_proposal(p)
    assert db.url_exists(url)


def test_save_and_get_proposal():
    url = "https://example.com/arxiv-paper"
    p = Proposal(
        id=None,
        url=url,
        title="Deep Learning Optimization",
        source="arxiv",
        summary="Optimizing deep learning models using quantum computation.",
        proposed_title="Quantum AI Optimization",
        proposed_angle="Why quantum-accelerated training is the future of deep learning.",
        status="pending",
    )

    proposal_id = db.save_proposal(p)
    assert proposal_id is not None

    fetched = db.get_proposal(proposal_id)
    assert fetched is not None
    assert fetched.id == proposal_id
    assert fetched.url == url
    assert fetched.title == "Deep Learning Optimization"
    assert fetched.proposed_title == "Quantum AI Optimization"
    assert fetched.proposed_angle == "Why quantum-accelerated training is the future of deep learning."
    assert fetched.status == "pending"


def test_update_proposal_status():
    url = "https://github.com/trending/ai-repo"
    p = Proposal(
        id=None,
        url=url,
        title="Awesome AI Framework",
        source="github",
        summary="A new framework that runs AI models 10x faster.",
        proposed_title="10x Faster AI Models",
        proposed_angle="A new framework breaks inference limits.",
        status="pending",
    )

    proposal_id = db.save_proposal(p)
    db.update_proposal_status(proposal_id, "approved")

    fetched = db.get_proposal(proposal_id)
    assert fetched.status == "approved"


def test_get_history():
    p1 = Proposal(
        id=None,
        url="url1",
        title="T1",
        source="hn",
        summary="S1",
        proposed_title="PT1",
        proposed_angle="PA1",
        status="approved",
    )
    p2 = Proposal(
        id=None,
        url="url2",
        title="T2",
        source="hn",
        summary="S2",
        proposed_title="PT2",
        proposed_angle="PA2",
        status="rejected",
    )
    p3 = Proposal(
        id=None,
        url="url3",
        title="T3",
        source="hn",
        summary="S3",
        proposed_title="PT3",
        proposed_angle="PA3",
        status="approved",
    )

    db.save_proposal(p1)
    db.save_proposal(p2)
    db.save_proposal(p3)

    approved_history = db.get_history("approved")
    assert len(approved_history) == 2
    # Verify in reverse chronological order (url3 saved last, so it should be first in descending order)
    assert approved_history[0].url == "url3"
    assert approved_history[1].url == "url1"

    rejected_history = db.get_history("rejected")
    assert len(rejected_history) == 1
    assert rejected_history[0].url == "url2"


def test_get_positive_history():
    p1 = Proposal(
        id=None,
        url="pos_url1",
        title="Pos T1",
        source="hn",
        summary="S1",
        proposed_title="Pos PT1",
        proposed_angle="PA1",
        status="approved",
    )
    p2 = Proposal(
        id=None,
        url="pos_url2",
        title="Pos T2",
        source="hn",
        summary="S2",
        proposed_title="Pos PT2",
        proposed_angle="PA2",
        status="posted",
    )
    p3 = Proposal(
        id=None,
        url="pos_url3",
        title="Pos T3",
        source="hn",
        summary="S3",
        proposed_title="Pos PT3",
        proposed_angle="PA3",
        status="rejected",
    )

    db.save_proposal(p1)
    db.save_proposal(p2)
    db.save_proposal(p3)

    positive_history = db.get_positive_history(limit=5)
    assert len(positive_history) == 2
    # Both approved and posted are loaded, rejected is omitted!
    urls = [p.url for p in positive_history]
    assert "pos_url2" in urls
    assert "pos_url1" in urls
    assert "pos_url3" not in urls


def test_manual_style_examples_only():
    db.initialize_db()
    db.clear_style_examples()

    # Save manual style entries
    db.add_style_example("manual sample 1", type="manual")
    db.add_style_example("manual sample 2", type="manual")

    # Save approved auto-cataloged style entries (e.g. leftover or legacy)
    db.add_style_example("approved sample 1", type="approved", proposal_id=111)
    db.add_style_example("approved sample 2", type="approved", proposal_id=222)

    # Retrieve with limit = 3
    examples = db.get_style_examples(limit=3)

    # Should ONLY return the 2 manual entries and strictly ignore approved entries to prevent AI Echo Drift!
    assert len(examples) == 2
    assert "manual sample 2" in examples
    assert "manual sample 1" in examples
    assert "approved sample 2" not in examples
    assert "approved sample 1" not in examples

    # Detailed list should also only return manual entries
    detailed = db.get_style_examples_detailed(limit=10)
    assert len(detailed) == 2
    assert detailed[0]["content"] == "manual sample 2"
    assert detailed[1]["content"] == "manual sample 1"


def test_get_style_examples_limit_5_freshest():
    db.clear_style_examples()
    for i in range(1, 8):
        db.add_style_example(f"sample {i}", type="manual")

    # Default call should return top 5 freshest
    examples = db.get_style_examples()
    assert len(examples) == 5
    # Order should be descending (most recent first)
    assert examples[0] == "sample 7"
    assert examples[1] == "sample 6"
    assert examples[2] == "sample 5"
    assert examples[3] == "sample 4"
    assert examples[4] == "sample 3"


def test_get_all_history_ordered_by_date_desc():
    # Insert proposals with explicitly different timestamps and statuses
    with db.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "https://old-approved.com",
                "Old Approved Title",
                "hn",
                "Summary 1",
                "PT1",
                "PA1",
                "approved",
                "2026-07-01 10:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "https://mid-rejected.com",
                "Mid Rejected Title",
                "reddit",
                "Summary 2",
                "PT2",
                "PA2",
                "rejected",
                "2026-08-15 12:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "https://new-pending.com",
                "New Pending Title",
                "shopify_blog",
                "Summary 3",
                "PT3",
                "PA3",
                "pending",
                "2026-09-29 08:00:00",
            ),
        )
        conn.commit()

    history = db.get_all_history(limit=10)
    assert len(history) == 3

    # Must be strictly ordered by created_at DESC:
    # 1. New Pending (2026-09-29)
    # 2. Mid Rejected (2026-08-15)
    # 3. Old Approved (2026-07-01)
    assert history[0].url == "https://new-pending.com"
    assert history[0].status == "pending"
    assert history[1].url == "https://mid-rejected.com"
    assert history[1].status == "rejected"
    assert history[2].url == "https://old-approved.com"
    assert history[2].status == "approved"


def test_get_all_history_with_status_filter():
    with db.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("https://app1.com", "App 1", "hn", "S", "PT", "PA", "approved", "2026-09-01 10:00:00"),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("https://app2.com", "App 2", "hn", "S", "PT", "PA", "approved", "2026-09-02 10:00:00"),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("https://rej1.com", "Rej 1", "reddit", "S", "PT", "PA", "rejected", "2026-09-03 10:00:00"),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("https://pend1.com", "Pend 1", "arxiv", "S", "PT", "PA", "pending", "2026-09-04 10:00:00"),
        )
        conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("https://post1.com", "Post 1", "shopify_blog", "S", "PT", "PA", "posted", "2026-09-05 10:00:00"),
        )
        conn.commit()

    # Filter by approved
    approved = db.get_all_history(limit=10, status="approved")
    assert len(approved) == 2
    assert approved[0].url == "https://app2.com"  # Newest approved first
    assert approved[1].url == "https://app1.com"

    # Filter by rejected
    rejected = db.get_all_history(limit=10, status="rejected")
    assert len(rejected) == 1
    assert rejected[0].url == "https://rej1.com"

    # Filter by pending
    pending = db.get_all_history(limit=10, status="pending")
    assert len(pending) == 1
    assert pending[0].url == "https://pend1.com"

    # Filter by posted
    posted = db.get_all_history(limit=10, status="posted")
    assert len(posted) == 1
    assert posted[0].url == "https://post1.com"

    # Filter by all
    all_items = db.get_all_history(limit=10, status="all")
    assert len(all_items) == 5
    assert all_items[0].url == "https://post1.com"  # Most recent


