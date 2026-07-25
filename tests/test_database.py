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
